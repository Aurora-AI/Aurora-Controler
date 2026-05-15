"""
EXRS Phase A4 — Excel Formula Evaluator
Cobertura: ~450 funções Excel → Python determinístico.
Segurança: eval() com __builtins__={} — sandbox explícito.
"""
import re
import math
import cmath
import statistics
import datetime
from typing import Any

try:
    from openpyxl.formula import Tokenizer
    from openpyxl.utils import column_index_from_string
    _HAS_TOKENIZER = True
except ImportError:
    _HAS_TOKENIZER = False
    def column_index_from_string(s): return ord(s.upper()) - 64  # fallback A=1


class ExcelError:
    """Sentinel para erros Excel — não lança exceção em aritmética (lazy propagation)."""
    __slots__ = ('code',)
    def __init__(self, code='#VALUE!'): self.code = code
    def __repr__(self): return self.code
    def __str__(self): return self.code
    def __add__(self, o): return self
    def __radd__(self, o): return self
    def __sub__(self, o): return self
    def __rsub__(self, o): return self
    def __mul__(self, o): return self
    def __rmul__(self, o): return self
    def __truediv__(self, o): return self
    def __rtruediv__(self, o): return self
    def __floordiv__(self, o): return self
    def __rfloordiv__(self, o): return self
    def __pow__(self, o): return self
    def __rpow__(self, o): return self
    def __neg__(self): return self
    def __pos__(self): return self
    def __bool__(self): return False
    def __eq__(self, o): return isinstance(o, ExcelError) and o.code == self.code
    def __lt__(self, o): return False
    def __gt__(self, o): return False
    def __le__(self, o): return False
    def __ge__(self, o): return False
    def __hash__(self): return hash(self.code)

_DIV0 = ExcelError('#DIV/0!')
_VAL  = ExcelError('#VALUE!')
_NA   = ExcelError('#N/A')
_NUM  = ExcelError('#NUM!')
_REF  = ExcelError('#REF!')


class _Blank(float):
    """Célula vazia: comporta-se como 0 mas divisão por ela retorna #DIV/0!."""
    def __rtruediv__(self, other): return _DIV0
    def __truediv__(self, other): return _DIV0 if other == 0 or isinstance(other, _Blank) else 0

_XL_BLANK = _Blank(0)

def _sdiv(a, b):
    """Divisão segura: retorna ExcelError em vez de lançar ZeroDivisionError."""
    if isinstance(b, (int, float)) and b == 0:
        return _DIV0
    if isinstance(b, ExcelError):
        return b
    if isinstance(a, ExcelError):
        return a
    try:
        return a / b
    except ZeroDivisionError:
        return _DIV0
    except TypeError:
        return _VAL

# ── Mapa função Excel → nome Python interno ────────────────────────────────
EXCEL_FUNC_MAP = {
    # Lógicas
    'IF': '_xl_if', 'IFS': '_xl_ifs', 'IFERROR': '_xl_iferror', 'IFNA': '_xl_ifna',
    'AND': '_xl_and', 'OR': '_xl_or', 'NOT': '_xl_not', 'XOR': '_xl_xor',
    'TRUE': '_xl_true', 'FALSE': '_xl_false', 'SWITCH': '_xl_switch',
    # Matemáticas básicas
    'SUM': '_xl_sum', 'SUMIF': '_xl_sumif', 'SUMIFS': '_xl_sumifs',
    'SUMPRODUCT': '_xl_sumproduct', 'SUMSQ': '_xl_sumsq',
    'SUMX2MY2': '_xl_sumx2my2', 'SUMX2PY2': '_xl_sumx2py2', 'SUMXMY2': '_xl_sumxmy2',
    'PRODUCT': '_xl_product', 'QUOTIENT': '_xl_quotient',
    'ABS': 'abs', 'INT': '_xl_int', 'TRUNC': '_xl_trunc',
    'MOD': '_xl_mod', 'SIGN': '_xl_sign',
    'ROUND': '_xl_round', 'ROUNDUP': '_xl_roundup', 'ROUNDDOWN': '_xl_rounddown',
    'CEILING': '_xl_ceiling', 'CEILING.MATH': '_xl_ceiling', 'CEILING.PRECISE': '_xl_ceiling',
    'FLOOR': '_xl_floor', 'FLOOR.MATH': '_xl_floor', 'FLOOR.PRECISE': '_xl_floor',
    'MROUND': '_xl_mround', 'EVEN': '_xl_even', 'ODD': '_xl_odd',
    'POWER': '_xl_power', 'SQRT': '_xl_sqrt', 'SQRTPI': '_xl_sqrtpi',
    'EXP': '_xl_exp', 'LN': '_xl_ln', 'LOG': '_xl_log', 'LOG10': '_xl_log10',
    'FACT': '_xl_fact', 'FACTDOUBLE': '_xl_factdouble',
    'COMBIN': '_xl_combin', 'COMBINA': '_xl_combina',
    'PERMUT': '_xl_permut', 'PERMUTATIONA': '_xl_permutationa',
    'GCD': '_xl_gcd', 'LCM': '_xl_lcm',
    'PI': '_xl_pi', 'RAND': '_xl_rand', 'RANDBETWEEN': '_xl_randbetween',
    'DEGREES': '_xl_degrees', 'RADIANS': '_xl_radians',
    'SIN': '_xl_sin', 'COS': '_xl_cos', 'TAN': '_xl_tan',
    'ASIN': '_xl_asin', 'ACOS': '_xl_acos', 'ATAN': '_xl_atan', 'ATAN2': '_xl_atan2',
    'SINH': '_xl_sinh', 'COSH': '_xl_cosh', 'TANH': '_xl_tanh',
    'ASINH': '_xl_asinh', 'ACOSH': '_xl_acosh', 'ATANH': '_xl_atanh',
    'SEC': '_xl_sec', 'CSC': '_xl_csc', 'COT': '_xl_cot',
    'SECH': '_xl_sech', 'CSCH': '_xl_csch', 'COTH': '_xl_coth',
    'ACOT': '_xl_acot', 'ACOTH': '_xl_acoth',
    'SERIESSUM': '_xl_seriessum', 'MULTINOMIAL': '_xl_multinomial',
    'BASE': '_xl_base', 'DECIMAL': '_xl_decimal', 'ARABIC': '_xl_arabic',
    'ROMAN': '_xl_roman',
    # Estatísticas
    'AVERAGE': '_xl_avg', 'AVERAGEA': '_xl_avga', 'AVERAGEIF': '_xl_avgif', 'AVERAGEIFS': '_xl_avgifs',
    'COUNT': '_xl_count', 'COUNTA': '_xl_counta', 'COUNTBLANK': '_xl_countblank',
    'COUNTIF': '_xl_countif', 'COUNTIFS': '_xl_countifs',
    'MIN': '_xl_min', 'MAX': '_xl_max', 'MINA': '_xl_mina', 'MAXA': '_xl_maxa',
    'LARGE': '_xl_large', 'SMALL': '_xl_small',
    'MAXIFS': '_xl_maxifs', 'MINIFS': '_xl_minifs',
    'RANK': '_xl_rank', 'RANK.EQ': '_xl_rank', 'RANK.AVG': '_xl_rank_avg',
    'PERCENTILE': '_xl_percentile', 'PERCENTILE.INC': '_xl_percentile', 'PERCENTILE.EXC': '_xl_percentile_exc',
    'PERCENTRANK': '_xl_percentrank', 'PERCENTRANK.INC': '_xl_percentrank', 'PERCENTRANK.EXC': '_xl_percentrank_exc',
    'QUARTILE': '_xl_quartile', 'QUARTILE.INC': '_xl_quartile', 'QUARTILE.EXC': '_xl_quartile_exc',
    'MEDIAN': '_xl_median', 'MODE': '_xl_mode', 'MODE.SNGL': '_xl_mode', 'MODE.MULT': '_xl_mode',
    'STDEV': '_xl_stdev', 'STDEV.S': '_xl_stdev', 'STDEV.P': '_xl_stdevp',
    'STDEVA': '_xl_stdev', 'STDEVPA': '_xl_stdevp',
    'VAR': '_xl_var', 'VAR.S': '_xl_var', 'VAR.P': '_xl_varp',
    'VARA': '_xl_var', 'VARPA': '_xl_varp',
    'AVEDEV': '_xl_avedev', 'DEVSQ': '_xl_devsq',
    'CORREL': '_xl_correl', 'COVAR': '_xl_covar', 'COVARIANCE.P': '_xl_covar', 'COVARIANCE.S': '_xl_covars',
    'PEARSON': '_xl_correl',
    'SLOPE': '_xl_slope', 'INTERCEPT': '_xl_intercept', 'RSQ': '_xl_rsq',
    'STEYX': '_xl_steyx', 'FORECAST': '_xl_forecast', 'FORECAST.LINEAR': '_xl_forecast',
    'SKEW': '_xl_skew', 'SKEW.P': '_xl_skewp', 'KURT': '_xl_kurt',
    'GEOMEAN': '_xl_geomean', 'HARMEAN': '_xl_harmean', 'TRIMMEAN': '_xl_trimmean',
    'STANDARDIZE': '_xl_standardize', 'NORM.DIST': '_xl_normdist', 'NORMDIST': '_xl_normdist',
    'NORM.S.DIST': '_xl_normsdist', 'NORMSDIST': '_xl_normsdist',
    'NORM.INV': '_xl_norminv', 'NORMINV': '_xl_norminv',
    'NORM.S.INV': '_xl_normsinv', 'NORMSINV': '_xl_normsinv',
    'T.DIST': '_xl_tdist', 'T.DIST.2T': '_xl_tdist2t', 'T.DIST.RT': '_xl_tdistrt', 'TDIST': '_xl_tdist',
    'T.INV': '_xl_tinv', 'T.INV.2T': '_xl_tinv2t', 'TINV': '_xl_tinv2t',
    'T.TEST': '_xl_passthrough', 'TTEST': '_xl_passthrough',
    'CHISQ.DIST': '_xl_passthrough', 'CHISQ.DIST.RT': '_xl_passthrough',
    'CHISQ.INV': '_xl_passthrough', 'CHISQ.INV.RT': '_xl_passthrough',
    'CHISQ.TEST': '_xl_passthrough', 'CHITEST': '_xl_passthrough',
    'F.DIST': '_xl_passthrough', 'F.DIST.RT': '_xl_passthrough',
    'F.INV': '_xl_passthrough', 'F.INV.RT': '_xl_passthrough',
    'F.TEST': '_xl_passthrough', 'FTEST': '_xl_passthrough',
    'BINOM.DIST': '_xl_binomdist', 'BINOMDIST': '_xl_binomdist',
    'BINOM.INV': '_xl_binomdist_inv', 'CRITBINOM': '_xl_binomdist_inv',
    'BINOM.DIST.RANGE': '_xl_passthrough',
    'NEGBINOM.DIST': '_xl_passthrough', 'NEGBINOMDIST': '_xl_passthrough',
    'POISSON.DIST': '_xl_poisson', 'POISSON': '_xl_poisson',
    'EXPON.DIST': '_xl_passthrough', 'EXPONDIST': '_xl_passthrough',
    'GAMMA.DIST': '_xl_passthrough', 'GAMMADIST': '_xl_passthrough',
    'GAMMA.INV': '_xl_passthrough', 'GAMMAINV': '_xl_passthrough',
    'GAMMA': '_xl_gamma', 'GAMMALN': '_xl_gammaln', 'GAMMALN.PRECISE': '_xl_gammaln',
    'BETA.DIST': '_xl_passthrough', 'BETADIST': '_xl_passthrough',
    'BETA.INV': '_xl_passthrough', 'BETAINV': '_xl_passthrough',
    'LOGNORM.DIST': '_xl_passthrough', 'LOGNORMDIST': '_xl_passthrough',
    'LOGNORM.INV': '_xl_passthrough', 'LOGINV': '_xl_passthrough',
    'WEIBULL.DIST': '_xl_passthrough', 'WEIBULL': '_xl_passthrough',
    'HYPGEOM.DIST': '_xl_passthrough', 'HYPGEOMDIST': '_xl_passthrough',
    'FISHER': '_xl_fisher', 'FISHERINV': '_xl_fisherinv',
    'CONFIDENCE': '_xl_confidence', 'CONFIDENCE.NORM': '_xl_confidence', 'CONFIDENCE.T': '_xl_confidence',
    'PROB': '_xl_passthrough', 'FREQUENCY': '_xl_passthrough',
    'GAUSS': '_xl_gauss', 'PHI': '_xl_phi',
    'Z.TEST': '_xl_passthrough', 'ZTEST': '_xl_passthrough',
    'LINEST': '_xl_passthrough', 'LOGEST': '_xl_passthrough',
    'TREND': '_xl_passthrough', 'GROWTH': '_xl_passthrough',
    # Texto
    'LEN': '_xl_len', 'LENB': '_xl_len',
    'LEFT': '_xl_left', 'LEFTB': '_xl_left',
    'RIGHT': '_xl_right', 'RIGHTB': '_xl_right',
    'MID': '_xl_mid', 'MIDB': '_xl_mid',
    'UPPER': '_xl_upper', 'LOWER': '_xl_lower', 'PROPER': '_xl_proper', 'TRIM': '_xl_trim',
    'TEXT': '_xl_text', 'VALUE': '_xl_value', 'NUMBERVALUE': '_xl_value',
    'CONCATENATE': '_xl_concat', 'CONCAT': '_xl_concat', 'TEXTJOIN': '_xl_textjoin',
    'FIND': '_xl_find', 'FINDB': '_xl_find', 'SEARCH': '_xl_search', 'SEARCHB': '_xl_search',
    'SUBSTITUTE': '_xl_substitute', 'REPLACE': '_xl_replace', 'REPLACEB': '_xl_replace',
    'REPT': '_xl_rept', 'CHAR': '_xl_char', 'CODE': '_xl_code',
    'CLEAN': '_xl_clean', 'ASC': '_xl_passthrough', 'DBCS': '_xl_passthrough',
    'EXACT': '_xl_exact', 'DOLLAR': '_xl_dollar', 'FIXED': '_xl_fixed',
    'UNICODE': '_xl_unicode', 'UNICHAR': '_xl_unichar',
    'T': '_xl_t', 'N': '_xl_n',
    'BAHTTEXT': '_xl_passthrough', 'PHONETIC': '_xl_passthrough', 'JIS': '_xl_passthrough',
    'ARRAYTOTEXT': '_xl_passthrough', 'VALUETOTEXT': '_xl_passthrough',
    'TEXTAFTER': '_xl_textafter', 'TEXTBEFORE': '_xl_textbefore', 'TEXTSPLIT': '_xl_passthrough',
    'REGEXTEST': '_xl_passthrough', 'REGEXEXTRACT': '_xl_passthrough', 'REGEXREPLACE': '_xl_passthrough',
    # Data/hora
    'DATE': '_xl_date', 'DATEVALUE': '_xl_datevalue', 'TIMEVALUE': '_xl_timevalue',
    'TIME': '_xl_time', 'NOW': '_xl_now', 'TODAY': '_xl_today',
    'DAY': '_xl_day', 'MONTH': '_xl_month', 'YEAR': '_xl_year',
    'HOUR': '_xl_hour', 'MINUTE': '_xl_minute', 'SECOND': '_xl_second',
    'WEEKDAY': '_xl_weekday', 'WEEKNUM': '_xl_weeknum', 'ISOWEEKNUM': '_xl_isoweeknum',
    'DAYS': '_xl_days', 'DAYS360': '_xl_days360',
    'EDATE': '_xl_edate', 'EOMONTH': '_xl_eomonth', 'DATEDIF': '_xl_datedif',
    'NETWORKDAYS': '_xl_networkdays', 'NETWORKDAYS.INTL': '_xl_networkdays',
    'WORKDAY': '_xl_workday', 'WORKDAY.INTL': '_xl_workday',
    'YEARFRAC': '_xl_yearfrac',
    # Lookup
    'VLOOKUP': '_xl_vlookup', 'HLOOKUP': '_xl_hlookup',
    'INDEX': '_xl_index', 'MATCH': '_xl_match',
    'XLOOKUP': '_xl_xlookup', 'XMATCH': '_xl_xmatch',
    'LOOKUP': '_xl_lookup',
    'OFFSET': '_xl_passthrough', 'INDIRECT': '_xl_passthrough',
    'ADDRESS': '_xl_address', 'ROW': '_xl_row', 'ROWS': '_xl_rows',
    'COLUMN': '_xl_column', 'COLUMNS': '_xl_columns',
    'AREAS': '_xl_passthrough', 'CHOOSE': '_xl_choose',
    'TRANSPOSE': '_xl_passthrough', 'GETPIVOTDATA': '_xl_passthrough',
    'FORMULATEXT': '_xl_passthrough', 'HYPERLINK': '_xl_passthrough',
    'RTD': '_xl_passthrough',
    # Array/Dinâmicas
    'FILTER': '_xl_passthrough', 'SORT': '_xl_passthrough', 'SORTBY': '_xl_passthrough',
    'UNIQUE': '_xl_passthrough', 'SEQUENCE': '_xl_passthrough', 'RANDARRAY': '_xl_passthrough',
    'TOCOL': '_xl_passthrough', 'TOROW': '_xl_passthrough',
    'HSTACK': '_xl_passthrough', 'VSTACK': '_xl_passthrough',
    'TAKE': '_xl_passthrough', 'DROP': '_xl_passthrough',
    'CHOOSEROWS': '_xl_passthrough', 'CHOOSECOLS': '_xl_passthrough',
    'EXPAND': '_xl_passthrough', 'TRIMRANGE': '_xl_passthrough',
    'MAKEARRAY': '_xl_passthrough', 'BYCOL': '_xl_passthrough', 'BYROW': '_xl_passthrough',
    'SCAN': '_xl_passthrough', 'REDUCE': '_xl_passthrough', 'MAP': '_xl_passthrough',
    'LAMBDA': '_xl_passthrough', 'LET': '_xl_let',
    'GROUPBY': '_xl_passthrough', 'PIVOTBY': '_xl_passthrough',
    # IS/Info
    'ISBLANK': '_xl_isblank', 'ISERROR': '_xl_iserror', 'ISERR': '_xl_iserr',
    'ISNA': '_xl_isna', 'ISNUMBER': '_xl_isnumber', 'ISTEXT': '_xl_istext',
    'ISNONTEXT': '_xl_isnontext', 'ISLOGICAL': '_xl_islogical', 'ISREF': '_xl_passthrough',
    'ISEVEN': '_xl_iseven', 'ISODD': '_xl_isodd', 'ISFORMULA': '_xl_passthrough',
    'ISOMITTED': '_xl_passthrough', 'NA': '_xl_na',
    'TYPE': '_xl_type', 'ERROR.TYPE': '_xl_passthrough',
    'CELL': '_xl_passthrough', 'INFO': '_xl_passthrough',
    'N': '_xl_n', 'SHEET': '_xl_passthrough', 'SHEETS': '_xl_passthrough',
    # Financeiras
    'PMT': '_xl_pmt', 'IPMT': '_xl_ipmt', 'PPMT': '_xl_ppmt',
    'FV': '_xl_fv', 'PV': '_xl_pv', 'NPER': '_xl_nper', 'RATE': '_xl_rate',
    'NPV': '_xl_npv', 'XNPV': '_xl_xnpv', 'IRR': '_xl_irr', 'XIRR': '_xl_xirr', 'MIRR': '_xl_mirr',
    'SLN': '_xl_sln', 'SYD': '_xl_syd', 'DDB': '_xl_ddb',
    'FVSCHEDULE': '_xl_passthrough', 'PDURATION': '_xl_pduration', 'RRI': '_xl_rri',
    'EFFECT': '_xl_effect', 'NOMINAL': '_xl_nominal',
    'DURATION': '_xl_passthrough', 'MDURATION': '_xl_passthrough',
    'DISC': '_xl_passthrough', 'INTRATE': '_xl_passthrough',
    'RECEIVED': '_xl_passthrough', 'TBILLEQ': '_xl_passthrough',
    'TBILLPRICE': '_xl_passthrough', 'TBILLYIELD': '_xl_passthrough',
    'PRICE': '_xl_passthrough', 'PRICEDISC': '_xl_passthrough', 'PRICEMAT': '_xl_passthrough',
    'YIELD': '_xl_passthrough', 'YIELDDISC': '_xl_passthrough', 'YIELDMAT': '_xl_passthrough',
    'ACCRINT': '_xl_passthrough', 'ACCRINTM': '_xl_passthrough',
    'COUPDAYBS': '_xl_passthrough', 'COUPDAYS': '_xl_passthrough',
    'COUPDAYSNC': '_xl_passthrough', 'COUPNCD': '_xl_passthrough',
    'COUPNUM': '_xl_passthrough', 'COUPPCD': '_xl_passthrough',
    'CUMIPMT': '_xl_passthrough', 'CUMPRINC': '_xl_passthrough',
    'ODDFPRICE': '_xl_passthrough', 'ODDFYIELD': '_xl_passthrough',
    'ODDLPRICE': '_xl_passthrough', 'ODDLYIELD': '_xl_passthrough',
    'AMORDEGRC': '_xl_passthrough', 'AMORLINC': '_xl_passthrough',
    'DOLLARDE': '_xl_dollarde', 'DOLLARFR': '_xl_dollarfr',
    'ISPMT': '_xl_ispmt',
    # Engenharia / Conversão
    'BIN2DEC': '_xl_bin2dec', 'BIN2HEX': '_xl_bin2hex', 'BIN2OCT': '_xl_bin2oct',
    'DEC2BIN': '_xl_dec2bin', 'DEC2HEX': '_xl_dec2hex', 'DEC2OCT': '_xl_dec2oct',
    'HEX2BIN': '_xl_hex2bin', 'HEX2DEC': '_xl_hex2dec', 'HEX2OCT': '_xl_hex2oct',
    'OCT2BIN': '_xl_oct2bin', 'OCT2DEC': '_xl_oct2dec', 'OCT2HEX': '_xl_oct2hex',
    'BITAND': '_xl_bitand', 'BITOR': '_xl_bitor', 'BITXOR': '_xl_bitxor',
    'BITLSHIFT': '_xl_bitlshift', 'BITRSHIFT': '_xl_bitrshift',
    'CONVERT': '_xl_convert',
    'DELTA': '_xl_delta', 'GESTEP': '_xl_gestep',
    'ERF': '_xl_erf', 'ERF.PRECISE': '_xl_erf', 'ERFC': '_xl_erfc', 'ERFC.PRECISE': '_xl_erfc',
    'BESSELI': '_xl_passthrough', 'BESSELJ': '_xl_passthrough',
    'BESSELK': '_xl_passthrough', 'BESSELY': '_xl_passthrough',
    'COMPLEX': '_xl_complex',
    'IMABS': '_xl_imabs', 'IMAGINARY': '_xl_imaginary', 'IMARGUMENT': '_xl_imargument',
    'IMCONJUGATE': '_xl_imconjugate', 'IMCOS': '_xl_imcos', 'IMCOSH': '_xl_imcosh',
    'IMCOT': '_xl_imcot', 'IMCSC': '_xl_imcsc', 'IMCSCH': '_xl_imcsch',
    'IMDIV': '_xl_imdiv', 'IMEXP': '_xl_imexp', 'IMLN': '_xl_imln',
    'IMLOG10': '_xl_imlog10', 'IMLOG2': '_xl_imlog2',
    'IMPOWER': '_xl_impower', 'IMPRODUCT': '_xl_improduct',
    'IMREAL': '_xl_imreal', 'IMSEC': '_xl_imsec', 'IMSECH': '_xl_imsech',
    'IMSIN': '_xl_imsin', 'IMSINH': '_xl_imsinh',
    'IMSQRT': '_xl_imsqrt', 'IMSUB': '_xl_imsub', 'IMSUM': '_xl_imsum',
    'IMTAN': '_xl_imtan',
    # Subtotal/Agregado
    'SUBTOTAL': '_xl_subtotal', 'AGGREGATE': '_xl_aggregate',
    # DB functions
    'DAVERAGE': '_xl_passthrough', 'DCOUNT': '_xl_passthrough', 'DCOUNTA': '_xl_passthrough',
    'DGET': '_xl_passthrough', 'DMAX': '_xl_passthrough', 'DMIN': '_xl_passthrough',
    'DPRODUCT': '_xl_passthrough', 'DSTDEV': '_xl_passthrough', 'DSTDEVP': '_xl_passthrough',
    'DSUM': '_xl_passthrough', 'DVAR': '_xl_passthrough', 'DVARP': '_xl_passthrough',
    # Cubo
    'CUBEVALUE': '_xl_passthrough', 'CUBEMEMBER': '_xl_passthrough',
    'CUBESET': '_xl_passthrough', 'CUBESETCOUNT': '_xl_passthrough',
    'CUBEMEMBERPROPERTY': '_xl_passthrough', 'CUBERANKEDMEMBER': '_xl_passthrough',
    'CUBEKPIMEMBER': '_xl_passthrough',
    # Web
    'ENCODEURL': '_xl_encodeurl', 'FILTERXML': '_xl_passthrough',
    'WEBSERVICE': '_xl_passthrough',
    # AI/novidades
    'COPILOT': '_xl_passthrough', 'TRANSLATE': '_xl_passthrough',
    'DETECTLANGUAGE': '_xl_passthrough',
    'IMAGE': '_xl_passthrough',
    'STOCKHISTORY': '_xl_passthrough',
    'PERCENTOF': '_xl_passthrough',
    # Português (aliases)
    'SOMA': '_xl_sum', 'SOMASE': '_xl_sumif', 'SOMASES': '_xl_sumifs',
    'SOMARPRODUTO': '_xl_sumproduct',
    'MÉDIA': '_xl_avg', 'MÉDIASE': '_xl_avgif', 'MÉDIASES': '_xl_avgifs',
    'CONT.NÚM': '_xl_count', 'CONT.VALORES': '_xl_counta', 'CONTAR.VAZIO': '_xl_countblank',
    'CONT.SE': '_xl_countif', 'CONT.SES': '_xl_countifs',
    'MÍNIMO': '_xl_min', 'MÁXIMO': '_xl_max', 'MAIOR': '_xl_large', 'MENOR': '_xl_small',
    'MÁXIMOSES': '_xl_maxifs', 'MÍNIMOSES': '_xl_minifs',
    'SE': '_xl_if', 'SES': '_xl_ifs', 'SEERRO': '_xl_iferror', 'SENÃODISP': '_xl_ifna',
    'E': '_xl_and', 'OU': '_xl_or', 'NÃO': '_xl_not',
    'PARÂMETRO': '_xl_switch',
    'PROCV': '_xl_vlookup', 'PROCH': '_xl_hlookup',
    'ÍNDICE': '_xl_index', 'CORRESP': '_xl_match',
    'PROCX': '_xl_xlookup', 'PROC': '_xl_lookup',
    'DESLOC': '_xl_passthrough', 'INDIRETO': '_xl_passthrough',
    'ENDEREÇO': '_xl_address', 'LIN': '_xl_row', 'LINS': '_xl_rows',
    'COL': '_xl_column', 'COLS': '_xl_columns', 'ESCOLHER': '_xl_choose',
    'TRANSPOR': '_xl_passthrough',
    'ANO': '_xl_year', 'MÊS': '_xl_month', 'DIA': '_xl_day',
    'HORA': '_xl_hour', 'MINUTO': '_xl_minute', 'SEGUNDO': '_xl_second',
    'HOJE': '_xl_today', 'AGORA': '_xl_now',
    'DATA': '_xl_date', 'TEMPO': '_xl_time',
    'DIAS': '_xl_days', 'DATAM': '_xl_edate', 'FIMMÊS': '_xl_eomonth',
    'DATADIF': '_xl_datedif', 'DIAS360': '_xl_days360',
    'DIA.DA.SEMANA': '_xl_weekday', 'NÚM.SEMANA': '_xl_weeknum',
    'DIATRABALHOTOTAL': '_xl_networkdays', 'DIAÚTIL': '_xl_workday',
    'MAIÚSCULA': '_xl_upper', 'MINÚSCULA': '_xl_lower', 'PRI.MAIÚSCULA': '_xl_proper',
    'ARRUMAR': '_xl_trim', 'TIRAR': '_xl_clean',
    'ESQUERDA': '_xl_left', 'DIREITA': '_xl_right', 'EXT.TEXTO': '_xl_mid',
    'NÚM.CARACT': '_xl_len', 'CONCATENAR': '_xl_concat', 'UNIRTEXTO': '_xl_textjoin',
    'PROCURAR': '_xl_find', 'PESQUISAR': '_xl_search', 'LOCALIZAR': '_xl_search',
    'SUBSTITUIR': '_xl_substitute', 'REPT': '_xl_rept',
    'CARACT': '_xl_char', 'CÓDIGO': '_xl_code', 'TEXTO': '_xl_text', 'VALOR': '_xl_value',
    'EXATO': '_xl_exact', 'MOEDA': '_xl_dollar',
    'MULT': '_xl_product', 'POTÊNCIA': '_xl_power', 'RAIZ': '_xl_sqrt',
    'ARRED': '_xl_round', 'ARREDONDAR.PARA.CIMA': '_xl_roundup',
    'ARREDONDAR.PARA.BAIXO': '_xl_rounddown',
    'TETO': '_xl_ceiling', 'PISO': '_xl_floor', 'MARRED': '_xl_mround',
    'PAR': '_xl_even', 'ÍMPAR': '_xl_odd', 'TRUNCAR': '_xl_trunc',
    'SINAL': '_xl_sign', 'ABS': 'abs',
    'FATORIAL': '_xl_fact', 'COMBIN': '_xl_combin',
    'GRAUS': '_xl_degrees', 'RADIANOS': '_xl_radians',
    'SEN': '_xl_sin', 'COS': '_xl_cos', 'TAN': '_xl_tan',
    'ASEN': '_xl_asin', 'ACOS': '_xl_acos', 'ATAN': '_xl_atan', 'ATAN2': '_xl_atan2',
    'SENH': '_xl_sinh', 'COSH': '_xl_cosh', 'TANH': '_xl_tanh',
    'RAIZPI': '_xl_sqrtpi', 'ORDEM': '_xl_rank', 'ORDEM.EQ': '_xl_rank', 'ORDEM.MÉD': '_xl_rank_avg',
    'PERCENTIL': '_xl_percentile', 'QUARTIL': '_xl_quartile',
    'MED': '_xl_median', 'MODO': '_xl_mode',
    'DESVPAD': '_xl_stdev', 'DESVPAD.A': '_xl_stdev', 'DESVPAD.P': '_xl_stdevp',
    'DESVPADP': '_xl_stdevp',
    'VAR': '_xl_var', 'VAR.A': '_xl_var', 'VAR.P': '_xl_varp', 'VARP': '_xl_varp',
    'DESV.MÉDIO': '_xl_avedev', 'DESVQ': '_xl_devsq',
    'MÉDIA.GEOMÉTRICA': '_xl_geomean', 'MÉDIA.HARMÔNICA': '_xl_harmean',
    'MÉDIA.INTERNA': '_xl_trimmean',
    'DIST.NORM': '_xl_normdist', 'DIST.NORMP': '_xl_normsdist',
    'INV.NORM': '_xl_norminv', 'INV.NORMP': '_xl_normsinv',
    'DISTR.BINOM': '_xl_binomdist', 'CRIT.BINOM': '_xl_binomdist_inv',
    'DISTR.POISSON': '_xl_poisson',
    'PGTO': '_xl_pmt', 'IPGTO': '_xl_ipmt', 'PPGTO': '_xl_ppmt',
    'VF': '_xl_fv', 'VP': '_xl_pv', 'NPER': '_xl_nper', 'TAXA': '_xl_rate',
    'VPL': '_xl_npv', 'TIR': '_xl_irr', 'MTIR': '_xl_mirr',
    'DPD': '_xl_sln', 'SDA': '_xl_syd', 'BDD': '_xl_ddb',
    'EFETIVA': '_xl_effect', 'NOMINAL': '_xl_nominal',
    'SUBTOTAL': '_xl_subtotal', 'AGREGAR': '_xl_aggregate',
    'ÉCÉL.VAZIA': '_xl_isblank', 'ÉERRO': '_xl_iserr', 'ÉERROS': '_xl_iserror',
    'ÉLÓGICO': '_xl_islogical', 'ÉNÚMERO': '_xl_isnumber', 'ÉTEXTO': '_xl_istext',
    'É.NÃO.TEXTO': '_xl_isnontext', 'É.NÃO.DISP': '_xl_isna', 'ÉREF': '_xl_passthrough',
    'ÉPAR': '_xl_iseven', 'ÉIMPAR': '_xl_isodd', 'ÉFÓRMULA': '_xl_passthrough',
    'NÃO.DISP': '_xl_na',
    'INT.CONFIANÇA': '_xl_confidence', 'PADRONIZAR': '_xl_standardize',
    'FISHER': '_xl_fisher', 'FISHERINV': '_xl_fisherinv',
    'FREQUÊNCIA': '_xl_passthrough', 'CRESCIMENTO': '_xl_passthrough', 'TENDÊNCIA': '_xl_passthrough',
    'PROJ.LIN': '_xl_passthrough', 'PROJ.LOG': '_xl_passthrough',
    'BINADEC': '_xl_bin2dec', 'BINAHEX': '_xl_bin2hex', 'BINAOCT': '_xl_bin2oct',
    'DECABIN': '_xl_dec2bin', 'DECAHEX': '_xl_dec2hex', 'DECAOCT': '_xl_dec2oct',
    'HEXABIN': '_xl_hex2bin', 'HEXADEC': '_xl_hex2dec', 'HEXAOCT': '_xl_hex2oct',
    'OCTABIN': '_xl_oct2bin', 'OCTADEC': '_xl_oct2dec', 'OCTAHEX': '_xl_oct2hex',
    'CONVERTER': '_xl_convert',
    'DEGRAU': '_xl_gestep', 'DELTA': '_xl_delta',
    'FUNERRO': '_xl_erf', 'FUNERROCOMPL': '_xl_erfc',
    'COMPLEXO': '_xl_complex',
    'BDSOMA': '_xl_passthrough', 'BDMÉDIA': '_xl_passthrough',
    'BDCONTAR': '_xl_passthrough', 'BDCONTARA': '_xl_passthrough',
    'BDMÁX': '_xl_passthrough', 'BDMÍN': '_xl_passthrough',
    'BDEXTRAIR': '_xl_passthrough', 'BDMULTIPL': '_xl_passthrough',
    'BDEST': '_xl_passthrough', 'BDDESVPA': '_xl_passthrough',
    'BDVAREST': '_xl_passthrough', 'BDVARP': '_xl_passthrough',
    'ALEATÓRIO': '_xl_rand', 'ALEATÓRIOENTRE': '_xl_randbetween',
    'MATRIZALEATÓRIA': '_xl_passthrough',
    'SEQUÊNCIA': '_xl_passthrough', 'FILTRO': '_xl_passthrough',
    'CLASSIFICAR': '_xl_passthrough', 'CLASSIFICARPOR': '_xl_passthrough',
    'ÚNICO': '_xl_passthrough',
    'PREVISÃO': '_xl_forecast', 'INCLINAÇÃO': '_xl_slope',
    'INTERCEPTAÇÃO': '_xl_intercept',
    'ROMANO': '_xl_roman', 'ÁRABE': '_xl_arabic',
    'NUMÉRICO': '_xl_value', 'DEF.NÚM.DEC': '_xl_fixed',
    'FÓRMULATEXTO': '_xl_passthrough',
    'CODIFURL': '_xl_encodeurl',
    'INFODADOSTABELADINÂMICA': '_xl_passthrough',
    # _xlfn aliases para funções modernas
    '_XLFN.XLOOKUP': '_xl_xlookup', '_XLFN.PROCX': '_xl_xlookup',
    '_XLFN.XMATCH': '_xl_xmatch',
    '_XLFN.IFS': '_xl_ifs', '_XLFN.SES': '_xl_ifs',
    '_XLFN.MAXIFS': '_xl_maxifs', '_XLFN.MINIFS': '_xl_minifs',
    '_XLFN.MÁXIMOSES': '_xl_maxifs', '_XLFN.MÍNIMOSES': '_xl_minifs',
    '_XLFN.TEXTJOIN': '_xl_textjoin', '_XLFN.UNIRTEXTO': '_xl_textjoin',
    '_XLFN.CONCAT': '_xl_concat',
    '_XLFN.UNIQUE': '_xl_passthrough', '_XLFN.ÚNICO': '_xl_passthrough',
    '_XLFN.FILTER': '_xl_passthrough', '_XLFN.FILTRO': '_xl_passthrough',
    '_XLFN.SORT': '_xl_passthrough', '_XLFN.SORTBY': '_xl_passthrough',
    '_XLFN.SEQUENCE': '_xl_passthrough', '_XLFN.SEQUÊNCIA': '_xl_passthrough',
    '_XLFN.RANDARRAY': '_xl_passthrough', '_XLFN.MATRIZALEATÓRIA': '_xl_passthrough',
    '_XLFN.LET': '_xl_let', '_XLFN.LAMBDA': '_xl_passthrough',
    '_XLFN.BYCOL': '_xl_passthrough', '_XLFN.BYROW': '_xl_passthrough',
    '_XLFN.MAKEARRAY': '_xl_passthrough',
    '_XLFN.SCAN': '_xl_passthrough', '_XLFN.REDUCE': '_xl_passthrough',
    '_XLFN.MAP': '_xl_passthrough',
    '_XLFN.TOCOL': '_xl_passthrough', '_XLFN.TOROW': '_xl_passthrough',
    '_XLFN.HSTACK': '_xl_passthrough', '_XLFN.VSTACK': '_xl_passthrough',
    '_XLFN.TAKE': '_xl_passthrough', '_XLFN.DROP': '_xl_passthrough',
    '_XLFN.CHOOSECOLS': '_xl_passthrough', '_XLFN.CHOOSEROWS': '_xl_passthrough',
    '_XLFN.EXPAND': '_xl_passthrough', '_XLFN.TRIMRANGE': '_xl_passthrough',
    '_XLFN.GROUPBY': '_xl_passthrough', '_XLFN.PIVOTBY': '_xl_passthrough',
    '_XLFN.PERCENTOF': '_xl_passthrough',
    '_XLFN.STOCKHISTORY': '_xl_passthrough',
    '_XLFN.IMAGE': '_xl_passthrough', '_XLFN.IMAGEM': '_xl_passthrough',
    '_XLFN.TRANSLATE': '_xl_passthrough', '_XLFN.DETECTLANGUAGE': '_xl_passthrough',
    '_XLFN.COPILOT': '_xl_passthrough',
    '_XLFN.TEXTAFTER': '_xl_textafter', '_XLFN.TEXTBEFORE': '_xl_textbefore',
    '_XLFN.TEXTSPLIT': '_xl_passthrough',
    '_XLFN.REGEXTEST': '_xl_passthrough', '_XLFN.REGEXEXTRACT': '_xl_passthrough',
    '_XLFN.REGEXREPLACE': '_xl_passthrough',
    '_XLFN.ARRAYTOTEXT': '_xl_passthrough',
    '_XLFN.ISOMITTED': '_xl_passthrough',
    '_XLFN.SWITCH': '_xl_switch', '_XLFN.PARÂMETRO': '_xl_switch',
    '_XLFN.ISOWEEKNUM': '_xl_isoweeknum',
    '_XLFN.NETWORKDAYS.INTL': '_xl_networkdays',
    '_XLFN.WORKDAY.INTL': '_xl_workday',
    '_XLFN.PDURATION': '_xl_pduration', '_XLFN.RRI': '_xl_rri',
    '_XLFN.GAMMA': '_xl_gamma', '_XLFN.GAUSS': '_xl_gauss', '_XLFN.PHI': '_xl_phi',
    '_XLFN.SKEW.P': '_xl_skewp', '_XLFN.MODE.MULT': '_xl_mode',
    '_XLFN.FORECAST.ETS': '_xl_passthrough',
    '_XLFN.FORECAST.ETS.CONFINT': '_xl_passthrough',
    '_XLFN.FORECAST.ETS.SEASONALITY': '_xl_passthrough',
    '_XLFN.FORECAST.ETS.STAT': '_xl_passthrough',
    '_XLFN.FORECAST.LINEAR': '_xl_forecast',
    '_XLFN.ACOT': '_xl_acot', '_XLFN.ACOTH': '_xl_acoth',
    '_XLFN.COT': '_xl_cot', '_XLFN.COTH': '_xl_coth',
    '_XLFN.SEC': '_xl_sec', '_XLFN.CSC': '_xl_csc',
    '_XLFN.SECH': '_xl_sech', '_XLFN.CSCH': '_xl_csch',
    '_XLFN.IMCOT': '_xl_imcot', '_XLFN.IMCSC': '_xl_imcsc', '_XLFN.IMCSCH': '_xl_imcsch',
    '_XLFN.IMTAN': '_xl_imtan', '_XLFN.IMSEC': '_xl_imsec', '_XLFN.IMSECH': '_xl_imsech',
    '_XLFN.IMCOSH': '_xl_imcosh', '_XLFN.IMSINH': '_xl_imsinh',
    '_XLFN.NUMBERVALUE': '_xl_value',
    '_XLFN.UNICHAR': '_xl_unichar', '_XLFN.UNICODE': '_xl_unicode',
    '_XLFN.ISFORMULA': '_xl_passthrough',
    '_XLFN.FORMULATEXT': '_xl_passthrough',
    '_XLFN.IFNA': '_xl_ifna',
    '_XLFN.SENÃODISP': '_xl_ifna',
    '_XLFN.XOR': '_xl_xor',
    '_XLFN.MUNIT': '_xl_passthrough',
    '_XLFN.SHEET': '_xl_passthrough', '_XLFN.SHEETS': '_xl_passthrough',
    '_XLFN.ENCODEURL': '_xl_encodeurl',
    '_XLFN.FILTERXML': '_xl_passthrough',
    '_XLFN.WEBSERVICE': '_xl_passthrough',
    '_XLFN.DURAÇÃOP': '_xl_pduration',
}


# ── helpers internos ───────────────────────────────────────────────────────

def _flat(args):
    """Recursively flatten nested lists (handles 2D ranges from multi-column _ref)."""
    out = []
    stack = list(args)
    while stack:
        a = stack.pop(0)
        if isinstance(a, list):
            stack[0:0] = a
        else:
            out.append(a)
    return out

def _nums(args):
    """Flatten args to list of numbers (recursive, skips non-numeric)."""
    return [v for v in _flat(args) if isinstance(v, (int, float)) and not isinstance(v, bool)]

def _crit_match(v, criteria):
    if isinstance(criteria, str):
        m = re.match(r'^([><=!]{1,2})(.+)$', criteria.strip())
        if m:
            op, rhs = m.group(1), m.group(2)
            try: rhs = float(rhs)
            except ValueError: pass
            ops = {'>': lambda a,b: a>b, '<': lambda a,b: a<b, '>=': lambda a,b: a>=b,
                   '<=': lambda a,b: a<=b, '<>': lambda a,b: a!=b, '!=': lambda a,b: a!=b,
                   '=': lambda a,b: a==b}
            fn = ops.get(op, lambda a,b: a==b)
            if v is None: return False
            try: return fn(v, rhs)
            except TypeError: return False
        # wildcard: * e ?
        pat = re.escape(criteria).replace(r'\*', '.*').replace(r'\?', '.')
        try: return bool(re.fullmatch(pat, str(v), re.IGNORECASE))
        except: return v == criteria
    return v == criteria

def _to_complex(s):
    if isinstance(s, complex): return s
    if isinstance(s, (int, float)): return complex(s)
    s = str(s).replace('i', 'j')
    try: return complex(s)
    except: return complex(0)

def _excel_date(v):
    """Serial date → datetime."""
    if isinstance(v, (int, float)):
        return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(v))
    return v

def _to_serial(d):
    if isinstance(d, (int, float)): return d
    if isinstance(d, (datetime.date, datetime.datetime)):
        return (d - datetime.date(1899, 12, 30)).days
    return 0


# ── Implementações ─────────────────────────────────────────────────────────

# Lógicas
def _is_err(v): return isinstance(v, ExcelError) or (isinstance(v, str) and v.startswith('#'))
def _if_err(v): return isinstance(v, ExcelError) or (isinstance(v, str) and v.startswith('#'))

def _xl_if(cond, t_val=0, f_val=0): return t_val if cond else f_val
def _xl_ifs(*args):
    it = iter(args)
    for cond, val in zip(it, it):
        if cond: return val
    return None
def _xl_iferror(expr, fallback): return fallback if _if_err(expr) else expr
def _xl_ifna(expr, fallback): return fallback if (isinstance(expr, ExcelError) and expr.code == '#N/A') or expr == '#N/A' else expr
def _xl_and(*args): return all(bool(a) for a in _flat(args))
def _xl_or(*args): return any(bool(a) for a in _flat(args))
def _xl_not(a): return not bool(a)
def _xl_xor(*args): return sum(bool(a) for a in _flat(args)) % 2 == 1
def _xl_true(): return True
def _xl_false(): return False
def _xl_switch(val, *args):
    it = iter(args)
    pairs = list(zip(it, it))
    default = args[-1] if len(args) % 2 == 1 else None
    for k, v in pairs:
        if val == k: return v
    return default
def _xl_let(*args): return args[-1] if args else None
def _xl_na(): return '#N/A'

# Matemáticas
def _xl_int(n):
    if not isinstance(n, (int, float)): return '#VALUE!'
    return math.floor(n)
def _xl_trunc(n, d=0):
    f = 10**int(d); return math.trunc(n*f)/f
def _xl_mod(a, b): return a % b if b else '#DIV/0!'
def _xl_sign(n): return (1 if n > 0 else -1 if n < 0 else 0)
def _xl_round(n, d=0): return round(float(n), int(d))
def _xl_roundup(n, d=0):
    f = 10**int(d); return math.ceil(n*f)/f
def _xl_rounddown(n, d=0):
    f = 10**int(d); return math.floor(n*f)/f
def _xl_ceiling(n, sig=1):
    if sig == 0: return 0
    return math.ceil(n/sig)*sig
def _xl_floor(n, sig=1):
    if sig == 0: return 0
    return math.floor(n/sig)*sig
def _xl_mround(n, m):
    if m == 0: return 0
    return round(n/m)*m
def _xl_even(n): return math.ceil(n/2)*2 if n >= 0 else math.floor(n/2)*2
def _xl_odd(n):
    c = math.ceil(abs(n)); c = c+1 if c%2==0 else c
    return c if n >= 0 else -c
def _xl_power(base, exp): return base**exp
def _xl_sqrt(n): return math.sqrt(abs(n)) if isinstance(n, (int,float)) else '#VALUE!'
def _xl_sqrtpi(n): return math.sqrt(n * math.pi)
def _xl_exp(n): return math.exp(n)
def _xl_ln(n): return math.log(n) if n > 0 else '#NUM!'
def _xl_log(n, base=10): return math.log(n, base) if n > 0 else '#NUM!'
def _xl_log10(n): return math.log10(n) if n > 0 else '#NUM!'
def _xl_fact(n):
    try: return math.factorial(int(n))
    except: return '#NUM!'
def _xl_factdouble(n):
    n = int(n)
    if n <= 0: return 1
    return n * _xl_factdouble(n-2)
def _xl_combin(n, k):
    try: return math.comb(int(n), int(k))
    except: return '#NUM!'
def _xl_combina(n, k):
    try: return math.comb(int(n)+int(k)-1, int(k))
    except: return '#NUM!'
def _xl_permut(n, k):
    try: n,k=int(n),int(k); return math.factorial(n)//math.factorial(n-k)
    except: return '#NUM!'
def _xl_permutationa(n, k):
    try: return int(n)**int(k)
    except: return '#NUM!'
def _xl_gcd(*args):
    vals = [int(v) for v in _nums(args)]
    return math.gcd(*vals) if vals else 0
def _xl_lcm(*args):
    vals = [int(v) for v in _nums(args)]
    r = vals[0] if vals else 0
    for v in vals[1:]: r = r * v // math.gcd(r, v)
    return r
def _xl_pi(): return math.pi
def _xl_rand(): return 0.5  # determinístico para validação
def _xl_randbetween(lo, hi): return int((lo+hi)//2)
def _xl_degrees(r): return math.degrees(r)
def _xl_radians(d): return math.radians(d)
def _xl_sin(x): return math.sin(x)
def _xl_cos(x): return math.cos(x)
def _xl_tan(x):
    try: return math.tan(x)
    except: return '#DIV/0!'
def _xl_asin(x): return math.asin(max(-1,min(1,x)))
def _xl_acos(x): return math.acos(max(-1,min(1,x)))
def _xl_atan(x): return math.atan(x)
def _xl_atan2(x, y): return math.atan2(y, x)  # Excel: ATAN2(x,y) = atan(y/x)
def _xl_sinh(x): return math.sinh(x)
def _xl_cosh(x): return math.cosh(x)
def _xl_tanh(x): return math.tanh(x)
def _xl_asinh(x): return math.asinh(x)
def _xl_acosh(x): return math.acosh(x) if x >= 1 else '#NUM!'
def _xl_atanh(x): return math.atanh(x) if -1 < x < 1 else '#NUM!'
def _xl_sec(x): c=math.cos(x); return 1/c if c else '#DIV/0!'
def _xl_csc(x): s=math.sin(x); return 1/s if s else '#DIV/0!'
def _xl_cot(x): t=math.tan(x); return 1/t if t else '#DIV/0!'
def _xl_sech(x): c=math.cosh(x); return 1/c if c else '#DIV/0!'
def _xl_csch(x): s=math.sinh(x); return 1/s if s else '#DIV/0!'
def _xl_coth(x): t=math.tanh(x); return 1/t if t else '#DIV/0!'
def _xl_acot(x): return math.pi/2 - math.atan(x)
def _xl_acoth(x): return math.atanh(1/x) if abs(x) > 1 else '#NUM!'
def _xl_seriessum(x, n, m, coeffs):
    if not isinstance(coeffs, list): coeffs = [coeffs]
    return sum(c * x**(n+i*m) for i,c in enumerate(coeffs))
def _xl_multinomial(*args):
    nums = _nums(args)
    n = sum(int(v) for v in nums)
    r = math.factorial(n)
    for v in nums: r //= math.factorial(int(v))
    return r
def _xl_base(n, radix, minlen=0):
    digits='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    n,radix=int(n),int(radix)
    if n==0: return '0'.zfill(minlen)
    r=''
    while n: r=digits[n%radix]+r; n//=radix
    return r.zfill(minlen)
def _xl_decimal(text, radix):
    try: return int(str(text), int(radix))
    except: return '#NUM!'
def _xl_arabic(s):
    vals={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
    r,prev=0,0
    for c in reversed(str(s).upper()):
        v=vals.get(c,0)
        r+=v if v>=prev else -v; prev=v
    return r
def _xl_roman(n, form=0):
    n=int(n)
    pairs=[(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),
           (50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
    r=''
    for val,sym in pairs:
        while n>=val: r+=sym; n-=val
    return r
def _xl_product(*args):
    r=1
    for v in _nums(args): r*=v
    return r
def _xl_quotient(n,d): return int(n/d) if d else '#DIV/0!'
def _xl_sumproduct(*args):
    lists=[a if isinstance(a,list) else [a] for a in args]
    n=min(len(l) for l in lists)
    return sum(math.prod(lists[j][i] for j in range(len(lists))
               if isinstance(lists[j][i],(int,float)))
               for i in range(n))
def _xl_sumsq(*args): return sum(v**2 for v in _nums(args))
def _xl_sumx2my2(ax,bx):
    ax=ax if isinstance(ax,list) else [ax]; bx=bx if isinstance(bx,list) else [bx]
    return sum(a**2-b**2 for a,b in zip(ax,bx) if isinstance(a,(int,float)) and isinstance(b,(int,float)))
def _xl_sumx2py2(ax,bx):
    ax=ax if isinstance(ax,list) else [ax]; bx=bx if isinstance(bx,list) else [bx]
    return sum(a**2+b**2 for a,b in zip(ax,bx) if isinstance(a,(int,float)) and isinstance(b,(int,float)))
def _xl_sumxmy2(ax,bx):
    ax=ax if isinstance(ax,list) else [ax]; bx=bx if isinstance(bx,list) else [bx]
    return sum((a-b)**2 for a,b in zip(ax,bx) if isinstance(a,(int,float)) and isinstance(b,(int,float)))

# Agregação
def _xl_sum(*args):
    return sum(_nums(args))
def _xl_avg(*args):
    v=_nums(args); return statistics.mean(v) if v else 0
def _xl_avga(*args):
    flat=_flat(args); vals=[float(v) if isinstance(v,bool) else (v if isinstance(v,(int,float)) else 0) for v in flat if v is not None]
    return statistics.mean(vals) if vals else 0
def _xl_count(*args): return sum(1 for v in _flat(args) if isinstance(v,(int,float)))
def _xl_counta(*args): return sum(1 for v in _flat(args) if v is not None and v != '')
def _xl_countblank(*args): return sum(1 for v in _flat(args) if v is None or v == '')
def _xl_min(*args): v=_nums(args); return min(v) if v else 0
def _xl_max(*args): v=_nums(args); return max(v) if v else 0
def _xl_mina(*args):
    vals=[float(v) if isinstance(v,bool) else v for v in _flat(args) if isinstance(v,(int,float,bool))]
    return min(vals) if vals else 0
def _xl_maxa(*args):
    vals=[float(v) if isinstance(v,bool) else v for v in _flat(args) if isinstance(v,(int,float,bool))]
    return max(vals) if vals else 0

def _xl_countif(range_vals, criteria):
    if not isinstance(range_vals, list): range_vals=[range_vals]
    return sum(1 for v in range_vals if _crit_match(v, criteria))

def _xl_countifs(*args):
    it=iter(args); pairs=list(zip(it,it))
    if not pairs: return 0
    first_range=pairs[0][0] if isinstance(pairs[0][0],list) else [pairs[0][0]]
    n=len(first_range)
    count=0
    for i in range(n):
        if all(_crit_match((r[i] if isinstance(r,list) and i<len(r) else r), c) for r,c in pairs):
            count+=1
    return count

def _xl_sumif(range_vals, criteria, sum_vals=None):
    if not isinstance(range_vals, list): range_vals=[range_vals]
    if sum_vals is None: sum_vals=range_vals
    elif not isinstance(sum_vals, list): sum_vals=[sum_vals]
    return sum(s for r,s in zip(range_vals,sum_vals) if _crit_match(r,criteria) and isinstance(s,(int,float)))

def _xl_sumifs(sum_range, *args):
    if not isinstance(sum_range,list): sum_range=[sum_range]
    it=iter(args); pairs=list(zip(it,it))
    n=len(sum_range)
    total=0
    for i in range(n):
        if not isinstance(sum_range[i],(int,float)): continue
        if all(_crit_match((r[i] if isinstance(r,list) and i<len(r) else r),c) for r,c in pairs):
            total+=sum_range[i]
    return total

def _xl_avgif(range_vals, criteria, avg_range=None):
    if not isinstance(range_vals,list): range_vals=[range_vals]
    if avg_range is None: avg_range=range_vals
    elif not isinstance(avg_range,list): avg_range=[avg_range]
    vals=[s for r,s in zip(range_vals,avg_range) if _crit_match(r,criteria) and isinstance(s,(int,float))]
    return statistics.mean(vals) if vals else 0

def _xl_avgifs(avg_range, *args):
    if not isinstance(avg_range,list): avg_range=[avg_range]
    it=iter(args); pairs=list(zip(it,it))
    n=len(avg_range)
    vals=[]
    for i in range(n):
        if not isinstance(avg_range[i],(int,float)): continue
        if all(_crit_match((r[i] if isinstance(r,list) and i<len(r) else r),c) for r,c in pairs):
            vals.append(avg_range[i])
    return statistics.mean(vals) if vals else 0

def _xl_maxifs(max_range, *args):
    if not isinstance(max_range,list): max_range=[max_range]
    it=iter(args); pairs=list(zip(it,it))
    n=len(max_range)
    vals=[max_range[i] for i in range(n) if isinstance(max_range[i],(int,float))
          and all(_crit_match((r[i] if isinstance(r,list) and i<len(r) else r),c) for r,c in pairs)]
    return max(vals) if vals else 0

def _xl_minifs(min_range, *args):
    if not isinstance(min_range,list): min_range=[min_range]
    it=iter(args); pairs=list(zip(it,it))
    n=len(min_range)
    vals=[min_range[i] for i in range(n) if isinstance(min_range[i],(int,float))
          and all(_crit_match((r[i] if isinstance(r,list) and i<len(r) else r),c) for r,c in pairs)]
    return min(vals) if vals else 0

def _xl_large(arr, k):
    if not isinstance(arr,list): arr=[arr]
    v=sorted([x for x in arr if isinstance(x,(int,float))],reverse=True)
    k=int(k); return v[k-1] if 0<k<=len(v) else '#NUM!'
def _xl_small(arr, k):
    if not isinstance(arr,list): arr=[arr]
    v=sorted([x for x in arr if isinstance(x,(int,float))])
    k=int(k); return v[k-1] if 0<k<=len(v) else '#NUM!'
def _xl_rank(val, arr, order=0):
    if not isinstance(arr,list): arr=[arr]
    v=sorted([x for x in arr if isinstance(x,(int,float))],reverse=(order==0))
    try: return v.index(val)+1
    except ValueError: return '#N/A'
def _xl_rank_avg(val, arr, order=0):
    if not isinstance(arr,list): arr=[arr]
    v=sorted([x for x in arr if isinstance(x,(int,float))],reverse=(order==0))
    indices=[i+1 for i,x in enumerate(v) if x==val]
    return statistics.mean(indices) if indices else '#N/A'

def _xl_percentile(arr, k):
    v=sorted(_nums([arr]))
    if not v: return 0
    k=float(k); idx=k*(len(v)-1)
    lo,hi=int(idx),min(int(idx)+1,len(v)-1)
    return v[lo]+(idx-lo)*(v[hi]-v[lo])
def _xl_percentile_exc(arr, k):
    v=sorted(_nums([arr]))
    if not v: return 0
    k=float(k); n=len(v)
    idx=k*(n+1)-1
    lo,hi=int(idx),min(int(idx)+1,n-1)
    if lo<0: return v[0]
    if hi>=n: return v[-1]
    return v[lo]+(idx-lo)*(v[hi]-v[lo])
def _xl_percentrank(arr, x, sig=3):
    v=sorted(_nums([arr]))
    if not v or x<v[0] or x>v[-1]: return '#N/A'
    count=sum(1 for vv in v if vv<=x)-1
    return round(count/(len(v)-1),sig)
def _xl_percentrank_exc(arr, x, sig=3):
    v=sorted(_nums([arr])); n=len(v)
    if not v: return '#N/A'
    count=sum(1 for vv in v if vv<x)
    return round(count/(n+1),sig)
def _xl_quartile(arr, q):
    return _xl_percentile(arr, int(q)/4)
def _xl_quartile_exc(arr, q):
    return _xl_percentile_exc(arr, int(q)/4)
def _xl_median(*args): v=_nums(args); return statistics.median(v) if v else 0
def _xl_mode(*args):
    v=_flat(args)
    nums=[x for x in v if isinstance(x,(int,float))]
    if not nums: return '#N/A'
    try: return statistics.mode(nums)
    except: return '#N/A'
def _xl_stdev(*args): v=_nums(args); return statistics.stdev(v) if len(v)>1 else 0
def _xl_stdevp(*args): v=_nums(args); return statistics.pstdev(v) if v else 0
def _xl_var(*args): v=_nums(args); return statistics.variance(v) if len(v)>1 else 0
def _xl_varp(*args): v=_nums(args); return statistics.pvariance(v) if v else 0
def _xl_avedev(*args):
    v=_nums(args)
    if not v: return 0
    m=statistics.mean(v); return sum(abs(x-m) for x in v)/len(v)
def _xl_devsq(*args):
    v=_nums(args)
    if not v: return 0
    m=statistics.mean(v); return sum((x-m)**2 for x in v)
def _xl_correl(arr1, arr2):
    a=_nums([arr1]); b=_nums([arr2])
    if len(a)<2 or len(a)!=len(b): return '#N/A'
    try: return statistics.correlation(a,b)
    except: return '#N/A'
def _xl_covar(arr1, arr2):
    a=_nums([arr1]); b=_nums([arr2]); n=min(len(a),len(b))
    if n<1: return '#N/A'
    ma=sum(a[:n])/n; mb=sum(b[:n])/n
    return sum((a[i]-ma)*(b[i]-mb) for i in range(n))/n
def _xl_covars(arr1, arr2):
    a=_nums([arr1]); b=_nums([arr2]); n=min(len(a),len(b))
    if n<2: return '#N/A'
    ma=sum(a[:n])/n; mb=sum(b[:n])/n
    return sum((a[i]-ma)*(b[i]-mb) for i in range(n))/(n-1)
def _xl_slope(ys, xs):
    y=_nums([ys]); x=_nums([xs]); n=min(len(y),len(x))
    if n<2: return '#N/A'
    mx=sum(x[:n])/n; my=sum(y[:n])/n
    num=sum((x[i]-mx)*(y[i]-my) for i in range(n))
    den=sum((x[i]-mx)**2 for i in range(n))
    return num/den if den else '#DIV/0!'
def _xl_intercept(ys, xs):
    y=_nums([ys]); x=_nums([xs]); n=min(len(y),len(x))
    if n<2: return '#N/A'
    mx=sum(x[:n])/n; my=sum(y[:n])/n
    return my - _xl_slope(ys,xs)*mx
def _xl_rsq(ys, xs):
    c=_xl_correl(ys,xs)
    return c**2 if isinstance(c,(int,float)) else '#N/A'
def _xl_steyx(ys, xs):
    y=_nums([ys]); x=_nums([xs]); n=min(len(y),len(x))
    if n<3: return '#N/A'
    sl=_xl_slope(ys,xs); ic=_xl_intercept(ys,xs)
    return math.sqrt(sum((y[i]-ic-sl*x[i])**2 for i in range(n))/(n-2))
def _xl_forecast(x, ys, xs):
    sl=_xl_slope(ys,xs); ic=_xl_intercept(ys,xs)
    return ic+sl*x if isinstance(sl,(int,float)) else '#N/A'
def _xl_skew(*args):
    v=_nums(args); n=len(v)
    if n<3: return '#DIV/0!'
    m=statistics.mean(v); s=statistics.stdev(v)
    if s==0: return '#DIV/0!'
    return n/((n-1)*(n-2))*sum(((x-m)/s)**3 for x in v)
def _xl_skewp(*args):
    v=_nums(args); n=len(v)
    if n<2: return '#DIV/0!'
    m=statistics.mean(v); s=statistics.pstdev(v)
    if s==0: return '#DIV/0!'
    return sum(((x-m)/s)**3 for x in v)/n
def _xl_kurt(*args):
    v=_nums(args); n=len(v)
    if n<4: return '#DIV/0!'
    m=statistics.mean(v); s=statistics.stdev(v)
    if s==0: return '#DIV/0!'
    k=sum(((x-m)/s)**4 for x in v)
    return n*(n+1)/((n-1)*(n-2)*(n-3))*k - 3*(n-1)**2/((n-2)*(n-3))
def _xl_geomean(*args):
    v=_nums(args)
    if not v or any(x<=0 for x in v): return '#NUM!'
    return math.exp(sum(math.log(x) for x in v)/len(v))
def _xl_harmean(*args):
    v=_nums(args)
    if not v or any(x<=0 for x in v): return '#NUM!'
    return len(v)/sum(1/x for x in v)
def _xl_trimmean(arr, pct):
    v=sorted(_nums([arr])); n=len(v)
    cut=int(n*pct/2)
    v=v[cut:n-cut] if cut else v
    return statistics.mean(v) if v else 0
def _xl_standardize(x, mean, sd): return (x-mean)/sd if sd else '#DIV/0!'
def _xl_normdist(x, mean, sd, cumulative=True):
    if not cumulative: return math.exp(-0.5*((x-mean)/sd)**2)/(sd*math.sqrt(2*math.pi))
    import statistics as st; return st.NormalDist(mean,sd).cdf(x)
def _xl_normsdist(x, cumulative=True):
    return _xl_normdist(x, 0, 1, cumulative)
def _xl_norminv(p, mean=0, sd=1):
    import statistics as st
    try: return st.NormalDist(mean,sd).inv_cdf(p)
    except: return '#NUM!'
def _xl_normsinv(p): return _xl_norminv(p, 0, 1)
def _xl_tdist(x, df, tails=1):
    try:
        import scipy.stats as ss; return ss.t.cdf(x,df)*(2 if tails==2 else 1)
    except ImportError:
        return '#N/A'
def _xl_tdist2t(x, df): return _xl_tdist(x, df, 2)
def _xl_tdistrt(x, df): return 1-_xl_tdist(x, df, 1) if isinstance(_xl_tdist(x,df,1),(int,float)) else '#N/A'
def _xl_tinv(p, df): return _xl_tdist(p, df)
def _xl_tinv2t(p, df):
    try:
        import scipy.stats as ss; return ss.t.ppf(1-p/2, df)
    except ImportError: return '#N/A'
def _xl_binomdist(x, n, p, cumulative=False):
    try:
        import scipy.stats as ss
        return ss.binom.cdf(x,n,p) if cumulative else ss.binom.pmf(x,n,p)
    except ImportError:
        k=int(x); n=int(n)
        pmf=math.comb(n,k)*(p**k)*((1-p)**(n-k))
        if cumulative: return sum(math.comb(n,i)*(p**i)*((1-p)**(n-i)) for i in range(k+1))
        return pmf
def _xl_binomdist_inv(n, p, alpha):
    n=int(n); cum=0
    for k in range(n+1):
        cum+=math.comb(n,k)*(p**k)*((1-p)**(n-k))
        if cum>=alpha: return k
    return n
def _xl_poisson(x, mean, cumulative=False):
    x=int(x)
    if cumulative: return sum(math.exp(-mean)*mean**k/math.factorial(k) for k in range(x+1))
    return math.exp(-mean)*mean**x/math.factorial(x)
def _xl_gamma(x):
    try: return math.gamma(x)
    except: return '#NUM!'
def _xl_gammaln(x):
    try: return math.lgamma(x)
    except: return '#NUM!'
def _xl_fisher(x): return 0.5*math.log((1+x)/(1-x)) if -1<x<1 else '#NUM!'
def _xl_fisherinv(y): return (math.exp(2*y)-1)/(math.exp(2*y)+1)
def _xl_confidence(alpha, sd, n): return _xl_norminv(1-alpha/2)*sd/math.sqrt(n)
def _xl_gauss(x): return _xl_normsdist(x)-0.5
def _xl_phi(x): return math.exp(-x**2/2)/math.sqrt(2*math.pi)

# Texto
def _xl_len(s): return len(str(s)) if s is not None else 0
def _xl_left(s, n=1): s=str(s) if s is not None else ''; return s[:max(0,int(n))]
def _xl_right(s, n=1): s=str(s) if s is not None else ''; n=max(0,int(n)); return s[-n:] if n else ''
def _xl_mid(s, start, n): s=str(s) if s is not None else ''; return s[int(start)-1:int(start)-1+int(n)]
def _xl_upper(s): return str(s).upper() if s is not None else ''
def _xl_lower(s): return str(s).lower() if s is not None else ''
def _xl_proper(s):
    if s is None: return ''
    return re.sub(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", lambda m: m.group(0).capitalize(), str(s))
def _xl_trim(s): return re.sub(r' +', ' ', str(s).strip()) if s is not None else ''
def _xl_clean(s): return re.sub(r'[\x00-\x1f]', '', str(s)) if s is not None else ''
def _xl_text(v, fmt=''):
    """Excel TEXT(value, format_text) — suporta formatos de data e número."""
    fmt = str(fmt)

    # ── Formato de data (DD, MM, YYYY, HH, SS) ────────────────────────────
    if fmt and re.search(r'\b(D{1,4}|M{1,4}|Y{2,4}|H{1,2}|S{1,2})\b', fmt, re.IGNORECASE):
        try:
            serial = _to_serial(v) if not isinstance(v, (int, float)) else int(v)
            dt = _excel_date(serial)
            py_fmt = (fmt
                .replace('YYYY', '%Y').replace('YY', '%y')
                .replace('MM', '%m').replace('DD', '%d')
                .replace('HH', '%H').replace('SS', '%S')
                .replace('yyyy', '%Y').replace('yy', '%y')
                .replace('mm', '%m').replace('dd', '%d')
                .replace('hh', '%H').replace('ss', '%S')
            )
            return dt.strftime(py_fmt)
        except Exception:
            pass

    # ── Formato numérico (#,##0.00 / 0.00 / $#,##0.00 / 0% etc.) ─────────
    if fmt:
        try:
            num = float(v)
            # Percentagem: "0%" ou "0.00%"
            if fmt.endswith('%'):
                inner = fmt[:-1]
                decimals = len(inner.split('.')[-1]) if '.' in inner else 0
                return f"{num * 100:.{decimals}f}%"
            # Moeda/contabilidade: começa com $ ou £ ou €
            currency = ''
            clean = fmt
            if fmt and fmt[0] in ('$', '£', '€', 'R'):
                currency = fmt[0]
                clean = fmt[1:]
            # Extrai: separador de milhar e casas decimais
            use_comma = ',' in clean
            if '.' in clean:
                decimals = len(re.sub(r'[^0#]', '', clean.split('.')[-1]))
            else:
                decimals = 0
            formatted = f"{num:,.{decimals}f}" if use_comma else f"{num:.{decimals}f}"
            return f"{currency}{formatted}"
        except (ValueError, TypeError):
            pass

    return str(v)
def _xl_value(s):
    if isinstance(s,(int,float)): return s
    try: return float(str(s).replace(',','.').replace(' ',''))
    except: return '#VALUE!'
def _xl_concat(*args): return ''.join('' if a is None else str(a) for a in _flat(args))
def _xl_textjoin(delim, ignore_empty, *args):
    parts=[]
    for a in _flat(args):
        s='' if a is None else str(a)
        if ignore_empty and s=='': continue
        parts.append(s)
    return str(delim).join(parts)
def _xl_find(needle, haystack, start=1):
    h=str(haystack) if haystack else ''; n=str(needle) if needle else ''
    idx=h.find(n, int(start)-1)
    return idx+1 if idx>=0 else '#VALUE!'
def _xl_search(needle, haystack, start=1):
    h=str(haystack).lower() if haystack else ''; n=str(needle).lower() if needle else ''
    n=re.escape(n).replace(r'\*','.*').replace(r'\?','.')
    m=re.search(n, h[int(start)-1:])
    return m.start()+int(start) if m else '#VALUE!'
def _xl_substitute(s, old, new, instance=None):
    s=str(s) if s else ''; old=str(old) if old else ''; new=str(new) if new else ''
    if instance is None: return s.replace(old, new)
    count=0
    result=''
    i=0
    while i<len(s):
        if s[i:i+len(old)]==old:
            count+=1
            if count==int(instance): result+=new; i+=len(old); continue
        result+=s[i]; i+=1
    return result
def _xl_replace(s, start, n, new):
    s=str(s) if s else ''; new=str(new) if new else ''
    return s[:int(start)-1]+new+s[int(start)-1+int(n):]
def _xl_rept(s, n): return str(s)*max(0,int(n)) if s is not None else ''
def _xl_char(n):
    try: return chr(int(n))
    except: return '#VALUE!'
def _xl_code(s): return ord(str(s)[0]) if s else '#VALUE!'
def _xl_exact(a, b): return str(a)==str(b)
def _xl_dollar(n, d=2):
    try: return f"${round(float(n),int(d)):,.{max(0,int(d))}f}"
    except: return '#VALUE!'
def _xl_fixed(n, d=2, no_commas=False):
    try:
        fmt=f"{round(float(n),int(d)):{',' if not no_commas else ''}.{max(0,int(d))}f}"
        return fmt
    except: return '#VALUE!'
def _xl_unicode(s): return ord(str(s)[0]) if s else '#VALUE!'
def _xl_unichar(n):
    try: return chr(int(n))
    except: return '#VALUE!'
def _xl_t(v): return str(v) if isinstance(v,str) else ''
def _xl_n(v):
    if isinstance(v,(int,float)): return v
    if isinstance(v,bool): return int(v)
    return 0
def _xl_textafter(s, delim, n=1):
    s=str(s) if s else ''; delim=str(delim) if delim else ''
    parts=s.split(delim); n=int(n)
    if n>0 and n<=len(parts)-1: return delim.join(parts[n:])
    return '#N/A'
def _xl_textbefore(s, delim, n=1):
    s=str(s) if s else ''; delim=str(delim) if delim else ''
    parts=s.split(delim); n=int(n)
    if n>0 and n<=len(parts)-1: return delim.join(parts[:n])
    return '#N/A'
def _xl_encodeurl(s):
    import urllib.parse; return urllib.parse.quote(str(s), safe='')
def _xl_strconcat(*args): return ''.join('' if a is None else str(a) for a in args)

# Data/hora
def _xl_today(): return (datetime.date.today()-datetime.date(1899,12,30)).days
def _xl_now():
    dt=datetime.datetime.now(); return (dt-datetime.datetime(1899,12,30)).total_seconds()/86400
def _xl_date(y,m,d):
    try: return (datetime.date(int(y),int(m),int(d))-datetime.date(1899,12,30)).days
    except: return '#VALUE!'
def _xl_datevalue(s):
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%m/%d/%Y','%d-%m-%Y'):
        try: return (datetime.datetime.strptime(str(s),fmt).date()-datetime.date(1899,12,30)).days
        except: pass
    return '#VALUE!'
def _xl_time(h,m,s): return (int(h)*3600+int(m)*60+int(s))/86400
def _xl_timevalue(s):
    for fmt in ('%H:%M:%S','%H:%M'):
        try:
            t=datetime.datetime.strptime(str(s),fmt)
            return (t.hour*3600+t.minute*60+t.second)/86400
        except: pass
    return '#VALUE!'
def _xl_year(d):
    try: return _excel_date(_to_serial(d)).year
    except: return '#VALUE!'
def _xl_month(d):
    try: return _excel_date(_to_serial(d)).month
    except: return '#VALUE!'
def _xl_day(d):
    try: return _excel_date(_to_serial(d)).day
    except: return '#VALUE!'
def _xl_hour(d):
    frac=(float(d)%1)*86400 if isinstance(d,(int,float)) else 0
    return int(frac//3600)
def _xl_minute(d):
    frac=(float(d)%1)*86400 if isinstance(d,(int,float)) else 0
    return int((frac%3600)//60)
def _xl_second(d):
    frac=(float(d)%1)*86400 if isinstance(d,(int,float)) else 0
    return int(frac%60)
def _xl_weekday(d, ret_type=1):
    try:
        dt=_excel_date(_to_serial(d)); wd=dt.weekday()  # 0=Mon
        if ret_type==2: return wd+1  # 1=Mon
        if ret_type==3: return wd    # 0=Mon
        return (wd+1)%7+1           # 1=Sun (default)
    except: return '#VALUE!'
def _xl_weeknum(d, ret_type=1):
    try:
        dt=_excel_date(_to_serial(d))
        return int(dt.strftime('%W'))+1 if ret_type==1 else int(dt.strftime('%U'))+1
    except: return '#VALUE!'
def _xl_isoweeknum(d):
    try: return _excel_date(_to_serial(d)).isocalendar()[1]
    except: return '#VALUE!'
def _xl_days(end, start): return _to_serial(end)-_to_serial(start)
def _xl_days360(start, end, method=False):
    s=_excel_date(_to_serial(start)); e=_excel_date(_to_serial(end))
    sd,sm,sy=s.day,s.month,s.year; ed,em,ey=e.day,e.month,e.year
    if not method:
        if sd==31: sd=30
        if ed==31 and sd==30: ed=30
    else:
        if sd==_last_day(sm,sy): sd=30
        if ed==_last_day(em,ey): ed=30
    return 360*(ey-sy)+30*(em-sm)+(ed-sd)
def _last_day(m,y): return [0,31,28+int(y%4==0 and(y%100!=0 or y%400==0)),31,30,31,30,31,31,30,31,30,31][m]
def _xl_edate(d, months):
    try:
        dt=_excel_date(_to_serial(d)); m=dt.month+int(months)
        y=dt.year+(m-1)//12; m=(m-1)%12+1
        day=min(dt.day,_last_day(m,y))
        return (datetime.date(y,m,day)-datetime.date(1899,12,30)).days
    except: return '#VALUE!'
def _xl_eomonth(d, months):
    try:
        dt=_excel_date(_to_serial(_xl_edate(d,months))); m=dt.month; y=dt.year
        return (datetime.date(y,m,_last_day(m,y))-datetime.date(1899,12,30)).days
    except: return '#VALUE!'
def _xl_datedif(start, end, unit):
    try:
        s=_excel_date(_to_serial(start)); e=_excel_date(_to_serial(end))
        u=str(unit).upper()
        if u=='D': return (e-s).days
        if u=='M': return (e.year-s.year)*12+(e.month-s.month)
        if u=='Y': return e.year-s.year-(1 if (e.month,e.day)<(s.month,s.day) else 0)
        if u=='YD': return (e.replace(year=s.year)-s).days
        if u=='YM': return (e.month-s.month)%12
        if u=='MD': return e.day-s.day
    except: pass
    return '#VALUE!'
def _xl_networkdays(start, end, holidays=None):
    try:
        s=_excel_date(_to_serial(start)); e=_excel_date(_to_serial(end))
        hols=set()
        if holidays and isinstance(holidays,list):
            hols={_excel_date(_to_serial(h)) for h in holidays if isinstance(h,(int,float))}
        count=0; d=s
        step=1 if e>=s else -1
        while d!=e+datetime.timedelta(days=step):
            if d.weekday()<5 and d not in hols: count+=step
            d+=datetime.timedelta(days=step)
        return count
    except: return '#VALUE!'
def _xl_workday(start, days, holidays=None):
    try:
        d=_excel_date(_to_serial(start)); days=int(days)
        hols=set()
        if holidays and isinstance(holidays,list):
            hols={_excel_date(_to_serial(h)) for h in holidays if isinstance(h,(int,float))}
        step=1 if days>=0 else -1
        remaining=abs(days)
        while remaining>0:
            d+=datetime.timedelta(days=step)
            if d.weekday()<5 and d not in hols: remaining-=1
        return (d-datetime.date(1899,12,30)).days
    except: return '#VALUE!'
def _xl_yearfrac(start, end, basis=0):
    try:
        s=_excel_date(_to_serial(start)); e=_excel_date(_to_serial(end))
        days=(e-s).days
        if basis==0: return _xl_days360(start,end)/360
        if basis==1: return days/((datetime.date(s.year+1,1,1)-datetime.date(s.year,1,1)).days)
        if basis==2: return days/360
        if basis==3: return days/365
        if basis==4: return _xl_days360(start,end,True)/360
    except: return '#VALUE!'

# Lookup
def _xl_vlookup(val, table, col, approx=True):
    if not isinstance(table,list): return '#N/A'
    col=int(col)-1
    for row in table:
        if not isinstance(row,list): continue
        if len(row)>col and row[0]==val: return row[col]
    return '#N/A'
def _xl_hlookup(val, table, row, approx=True):
    if not isinstance(table,list): return '#N/A'
    row=int(row)-1
    if not table or not isinstance(table[0],list): return '#N/A'
    for ci,v in enumerate(table[0]):
        if v==val and row<len(table) and ci<len(table[row]): return table[row][ci]
    return '#N/A'
def _xl_index(arr, row, col=1):
    if not isinstance(arr,list): return arr
    row,col=int(row)-1,int(col)-1
    if isinstance(arr[0],list): return arr[row][col] if row<len(arr) and col<len(arr[row]) else '#REF!'
    return arr[row] if row<len(arr) else '#REF!'
def _xl_match(val, arr, match_type=1):
    if not isinstance(arr,list): arr=[arr]
    match_type=int(match_type)
    if match_type==0:
        for i,v in enumerate(arr):
            if _crit_match(v,val): return i+1
    else:
        for i,v in enumerate(arr):
            if v==val: return i+1
    return '#N/A'
def _xl_xlookup(val, lookup_arr, return_arr, not_found=None, match_mode=0, search_mode=1):
    if not isinstance(lookup_arr,list): lookup_arr=[lookup_arr]
    if not isinstance(return_arr,list): return_arr=[return_arr]
    for i,v in enumerate(lookup_arr):
        if v==val and i<len(return_arr): return return_arr[i]
    return not_found if not_found is not None else '#N/A'
def _xl_xmatch(val, arr, match_mode=0, search_mode=1):
    return _xl_match(val, arr, 0)
def _xl_lookup(val, lookup_vec, result_vec=None):
    if not isinstance(lookup_vec,list): lookup_vec=[lookup_vec]
    if result_vec is None: result_vec=lookup_vec
    elif not isinstance(result_vec,list): result_vec=[result_vec]
    last=None
    for i,v in enumerate(lookup_vec):
        if isinstance(v,(int,float,str)) and v<=val and i<len(result_vec): last=result_vec[i]
        elif isinstance(v,(int,float,str)) and v>val: break
    return last if last is not None else '#N/A'
def _xl_choose(idx, *args):
    idx=int(idx)
    return args[idx-1] if 0<idx<=len(args) else '#VALUE!'
def _xl_address(row, col, abs_num=1, a1=True, sheet=None):
    from openpyxl.utils import get_column_letter
    c=get_column_letter(int(col)); r=str(int(row))
    if abs_num==1: addr=f'${c}${r}'
    elif abs_num==2: addr=f'{c}${r}'
    elif abs_num==3: addr=f'${c}{r}'
    else: addr=f'{c}{r}'
    return f"'{sheet}'!{addr}" if sheet else addr
def _xl_row(ref=None): return 1  # simplified
def _xl_rows(arr): return len(arr) if isinstance(arr,list) else 1
def _xl_column(ref=None): return 1
def _xl_columns(arr): return len(arr[0]) if isinstance(arr,list) and arr and isinstance(arr[0],list) else 1

# IS functions
def _xl_isblank(v): return v is None or v == '' or isinstance(v, _Blank)
def _xl_iserror(v): return isinstance(v, ExcelError) or (isinstance(v,str) and v.startswith('#'))
def _xl_iserr(v): return _xl_iserror(v) and not (str(v) == '#N/A')
def _xl_isna(v): return (isinstance(v, ExcelError) and v.code == '#N/A') or v == '#N/A'
def _xl_isnumber(v): return isinstance(v,(int,float)) and not isinstance(v,bool)
def _xl_istext(v): return isinstance(v,str) and not v.startswith('#')
def _xl_isnontext(v): return not isinstance(v,str)
def _xl_islogical(v): return isinstance(v,bool)
def _xl_iseven(v): return int(v)%2==0 if isinstance(v,(int,float)) else '#VALUE!'
def _xl_isodd(v): return int(v)%2!=0 if isinstance(v,(int,float)) else '#VALUE!'
def _xl_type(v):
    if isinstance(v,bool): return 4
    if isinstance(v,(int,float)): return 1
    if isinstance(v,str): return 2 if not v.startswith('#') else 16
    if isinstance(v,list): return 64
    return 1

# Financeiras
def _xl_pmt(rate, nper, pv, fv=0, type_=0):
    if rate==0: return -(pv+fv)/nper
    pmt=(rate*(pv*(1+rate)**nper+fv))/((1+rate)**nper-1)
    return -pmt*(1+rate*type_) if type_ else -pmt
def _xl_fv(rate, nper, pmt, pv=0, type_=0):
    if rate==0: return -(pv+pmt*nper)
    return -(pv*(1+rate)**nper+pmt*(1+rate*type_)*((1+rate)**nper-1)/rate)
def _xl_pv(rate, nper, pmt, fv=0, type_=0):
    if rate==0: return -(pmt*nper+fv)
    return -(pmt*(1+rate*type_)*(1-(1+rate)**-nper)/rate+fv*(1+rate)**-nper)
def _xl_nper(rate, pmt, pv, fv=0, type_=0):
    if rate==0: return -(pv+fv)/pmt if pmt else '#DIV/0!'
    return math.log((pmt-fv*rate)/(pmt+pv*rate))/math.log(1+rate)
def _xl_rate(nper, pmt, pv, fv=0, type_=0, guess=0.1):
    rate=guess
    for _ in range(100):
        f=pv*(1+rate)**nper+pmt*(1+rate*type_)*((1+rate)**nper-1)/rate+fv
        df=nper*pv*(1+rate)**(nper-1)
        if df==0: break
        nr=rate-f/df
        if abs(nr-rate)<1e-10: return nr
        rate=nr
    return rate
def _xl_npv(rate, *args):
    vals=_nums(args); return sum(v/(1+rate)**(i+1) for i,v in enumerate(vals))
def _xl_xnpv(rate, values, dates):
    v=values if isinstance(values,list) else [values]
    d=dates if isinstance(dates,list) else [dates]
    d0=_to_serial(d[0]) if d else 0
    return sum(v[i]/((1+rate)**(((_to_serial(d[i]))-d0)/365)) for i in range(min(len(v),len(d))))
def _xl_irr(values, guess=0.1):
    v=values if isinstance(values,list) else [values]
    rate=guess
    for _ in range(100):
        npv=sum(v[i]/(1+rate)**(i) for i in range(len(v)))
        dnpv=sum(-i*v[i]/(1+rate)**(i+1) for i in range(1,len(v)))
        if dnpv==0: break
        nr=rate-npv/dnpv
        if abs(nr-rate)<1e-8: return nr
        rate=nr
    return rate
def _xl_xirr(values, dates, guess=0.1): return _xl_irr(values if isinstance(values,list) else [values], guess)
def _xl_mirr(values, finance_rate, reinvest_rate):
    v=values if isinstance(values,list) else [values]; n=len(v)
    neg=sum(v[i]/(1+finance_rate)**i for i in range(n) if v[i]<0)
    pos=sum(v[i]*(1+reinvest_rate)**(n-1-i) for i in range(n) if v[i]>0)
    if neg==0: return '#DIV/0!'
    return ((-pos/neg)**(1/(n-1)))-1
def _xl_ipmt(rate, per, nper, pv, fv=0, type_=0):
    pmt=_xl_pmt(rate,nper,pv,fv,type_)
    return pv*(1+rate)**(per-1)*rate+pmt*((1+rate)**(per-1)-1)
def _xl_ppmt(rate, per, nper, pv, fv=0, type_=0):
    return _xl_pmt(rate,nper,pv,fv,type_)-_xl_ipmt(rate,per,nper,pv,fv,type_)
def _xl_sln(cost, salvage, life): return (cost-salvage)/life if life else '#DIV/0!'
def _xl_syd(cost, salvage, life, per):
    life=int(life); per=int(per)
    return (cost-salvage)*(life-per+1)*2/(life*(life+1))
def _xl_ddb(cost, salvage, life, period, factor=2):
    rate=factor/life; bv=cost
    for _ in range(int(period)-1): bv-=max(0,bv*rate-(max(0,bv-salvage)))
    return max(0, bv*rate, bv-salvage) if bv>salvage else 0
def _xl_effect(nominal, nper): return (1+nominal/nper)**nper-1
def _xl_nominal(effect, nper): return nper*((1+effect)**(1/nper)-1)
def _xl_pduration(rate, pv, fv): return math.log(fv/pv)/math.log(1+rate) if rate>0 and pv>0 else '#NUM!'
def _xl_rri(nper, pv, fv): return (fv/pv)**(1/nper)-1 if pv and nper else '#NUM!'
def _xl_ispmt(rate, per, nper, pv): return pv*rate*(per/nper-1)
def _xl_dollarde(dollar, frac):
    frac=int(frac); whole=int(dollar)
    dec=(dollar-whole)*10**len(str(frac))
    return whole+dec/frac
def _xl_dollarfr(dollar, frac):
    frac=int(frac); whole=int(dollar)
    dec=(dollar-whole)*frac
    return whole+dec/10**len(str(frac))

# Engenharia / Conversão de base
def _xl_bin2dec(s): return int(str(s),2) if str(s).lstrip('0') else 0
def _xl_bin2hex(s,places=None): v=int(str(s),2); h=hex(v)[2:].upper(); return h.zfill(places) if places else h
def _xl_bin2oct(s,places=None): v=int(str(s),2); o=oct(v)[2:]; return o.zfill(places) if places else o
def _xl_dec2bin(n,places=None): n=int(n); b=bin(n)[2:] if n>=0 else bin(n&0x3FF)[2:]; return b.zfill(places) if places else b
def _xl_dec2hex(n,places=None): n=int(n); h=hex(n)[2:].upper() if n>=0 else hex(n&0xFFFFFFFFFF)[2:].upper(); return h.zfill(places) if places else h
def _xl_dec2oct(n,places=None): n=int(n); o=oct(n)[2:] if n>=0 else oct(n&0x1FFFFFFF)[2:]; return o.zfill(places) if places else o
def _xl_hex2bin(s,places=None): v=int(str(s),16); b=bin(v)[2:]; return b.zfill(places) if places else b
def _xl_hex2dec(s): return int(str(s),16)
def _xl_hex2oct(s,places=None): v=int(str(s),16); o=oct(v)[2:]; return o.zfill(places) if places else o
def _xl_oct2bin(s,places=None): v=int(str(s),8); b=bin(v)[2:]; return b.zfill(places) if places else b
def _xl_oct2dec(s): return int(str(s),8)
def _xl_oct2hex(s,places=None): v=int(str(s),8); h=hex(v)[2:].upper(); return h.zfill(places) if places else h
def _xl_bitand(a,b): return int(a)&int(b)
def _xl_bitor(a,b): return int(a)|int(b)
def _xl_bitxor(a,b): return int(a)^int(b)
def _xl_bitlshift(n,s): return int(n)<<int(s)
def _xl_bitrshift(n,s): return int(n)>>int(s)
def _xl_delta(a,b=0): return 1 if a==b else 0
def _xl_gestep(n, step=0): return 1 if n>=step else 0
def _xl_erf(x, x2=None):
    try: import scipy.special as ss; return ss.erf(x2)-ss.erf(x) if x2 else ss.erf(x)
    except ImportError: return math.erf(x2)-math.erf(x) if x2 else math.erf(x)
def _xl_erfc(x):
    try: import scipy.special as ss; return ss.erfc(x)
    except ImportError: return math.erfc(x)

_CONVERT_MAP = {
    'g':'kg:0.001','kg':'kg:1','lbm':'kg:0.453592','ozm':'kg:0.0283495','mg':'kg:1e-6','ton':'kg:1000',
    'm':'m:1','km':'m:1000','mi':'m:1609.344','yd':'m:0.9144','ft':'m:0.3048','in':'m:0.0254','cm':'m:0.01','mm':'m:0.001','nm':'m:1e-9',
    'l':'l:1','L':'l:1','ml':'l:0.001','qt':'l:0.946353','pt':'l:0.473176','gal':'l:3.78541','oz':'l:0.0295735',
    'J':'J:1','kJ':'J:1000','cal':'J:4.18400','kcal':'J:4184','ev':'J:1.60218e-19','erg':'J:1e-7','Wh':'J:3600','kWh':'J:3.6e6',
    'Pa':'Pa:1','psi':'Pa:6894.76','atm':'Pa:101325','mmHg':'Pa:133.322',
    'K':'K:1',
    'yr':'s:31557600','day':'s:86400','hr':'s:3600','mn':'s:60','sec':'s:1',
    'bit':'bit:1','byte':'bit:8','kbit':'bit:1000','Mbit':'bit:1e6','Gbit':'bit:1e9',
    'btu':'J:1055.06','HP':'W:745.7','W':'W:1','kW':'W:1000','MW':'W:1e6',
}
def _xl_convert(n, from_u, to_u):
    fu, tu = str(from_u), str(to_u)
    # Temperature: non-linear, handle before general map
    _temps = {'C','F','K'}
    if fu in _temps or tu in _temps:
        if fu == tu: return n
        if fu=='C' and tu=='F': return n*9/5+32
        if fu=='F' and tu=='C': return (n-32)*5/9
        if fu=='C' and tu=='K': return n+273.15
        if fu=='K' and tu=='C': return n-273.15
        if fu=='F' and tu=='K': return (n-32)*5/9+273.15
        if fu=='K' and tu=='F': return (n-273.15)*9/5+32
        return '#N/A'
    def _info(u):
        e=_CONVERT_MAP.get(u)
        if e: parts=e.split(':'); return parts[0],float(parts[1])
        return None,1
    fc,fv=_info(fu); tc,tv=_info(tu)
    if fc is None or tc is None or fc!=tc: return '#N/A'
    return n*fv/tv

# Complexos
def _xl_complex(real, imag, suffix='i'):
    c=complex(real,imag)
    if c.imag==0: return str(c.real) if c.real!=int(c.real) else str(int(c.real))
    r=str(c.real) if c.real!=0 else ''
    i=('' if c.imag==1 else ('-' if c.imag==-1 else str(c.imag)))+suffix
    sign='+' if c.imag>=0 and r else ''
    return r+sign+i
def _xl_imabs(s): return abs(_to_complex(s))
def _xl_imaginary(s): return _to_complex(s).imag
def _xl_imargument(s): return cmath.phase(_to_complex(s))
def _xl_imconjugate(s):
    c=_to_complex(s).conjugate()
    return _xl_complex(c.real,c.imag)
def _xl_imcos(s): c=_to_complex(s); r=cmath.cos(c); return _xl_complex(r.real,r.imag)
def _xl_imcosh(s): c=_to_complex(s); r=cmath.cosh(c); return _xl_complex(r.real,r.imag)
def _xl_imcot(s): c=_to_complex(s); r=cmath.cos(c)/cmath.sin(c); return _xl_complex(r.real,r.imag)
def _xl_imcsc(s): c=_to_complex(s); r=1/cmath.sin(c); return _xl_complex(r.real,r.imag)
def _xl_imcsch(s): c=_to_complex(s); r=1/cmath.sinh(c); return _xl_complex(r.real,r.imag)
def _xl_imdiv(s1,s2): r=_to_complex(s1)/_to_complex(s2); return _xl_complex(r.real,r.imag)
def _xl_imexp(s): r=cmath.exp(_to_complex(s)); return _xl_complex(r.real,r.imag)
def _xl_imln(s): r=cmath.log(_to_complex(s)); return _xl_complex(r.real,r.imag)
def _xl_imlog10(s): r=cmath.log10(_to_complex(s)); return _xl_complex(r.real,r.imag)
def _xl_imlog2(s): r=cmath.log(_to_complex(s),2); return _xl_complex(r.real,r.imag)
def _xl_impower(s,n): r=_to_complex(s)**n; return _xl_complex(r.real,r.imag)
def _xl_improduct(*args):
    r=complex(1)
    for a in args: r*=_to_complex(a)
    return _xl_complex(r.real,r.imag)
def _xl_imreal(s): return _to_complex(s).real
def _xl_imsec(s): c=_to_complex(s); r=1/cmath.cos(c); return _xl_complex(r.real,r.imag)
def _xl_imsech(s): c=_to_complex(s); r=1/cmath.cosh(c); return _xl_complex(r.real,r.imag)
def _xl_imsin(s): r=cmath.sin(_to_complex(s)); return _xl_complex(r.real,r.imag)
def _xl_imsinh(s): r=cmath.sinh(_to_complex(s)); return _xl_complex(r.real,r.imag)
def _xl_imsqrt(s): r=cmath.sqrt(_to_complex(s)); return _xl_complex(r.real,r.imag)
def _xl_imsub(s1,s2): r=_to_complex(s1)-_to_complex(s2); return _xl_complex(r.real,r.imag)
def _xl_imsum(*args):
    r=sum(_to_complex(a) for a in args); return _xl_complex(r.real,r.imag)
def _xl_imtan(s): c=_to_complex(s); r=cmath.sin(c)/cmath.cos(c); return _xl_complex(r.real,r.imag)

# Subtotal / Aggregate
_SUBTOTAL_FUNCS = {
    1:_xl_avg,2:_xl_count,3:_xl_counta,4:_xl_max,5:_xl_min,
    6:_xl_product,7:_xl_stdev,8:_xl_stdevp,9:_xl_sum,10:_xl_var,11:_xl_varp,
    101:_xl_avg,102:_xl_count,103:_xl_counta,104:_xl_max,105:_xl_min,
    106:_xl_product,107:_xl_stdev,108:_xl_stdevp,109:_xl_sum,110:_xl_var,111:_xl_varp,
}
def _xl_subtotal(func_num, *args):
    f=_SUBTOTAL_FUNCS.get(int(func_num))
    return f(*args) if f else 0
def _xl_aggregate(func_num, options, *args):
    return _xl_subtotal(func_num, *args)

def _xl_passthrough(*args):
    """
    Marca funções não implementadas com '#UNSUPPORTED!' em vez de retornar
    o primeiro argumento silenciosamente. Isso garante que resultados incorretos
    apareçam como FAILED no relatório, não como falsos PASSED.
    """
    return ExcelError('#UNSUPPORTED!').code  # sinaliza explicitamente ao runner


# ── Namespace de avaliação ─────────────────────────────────────────────────

def _build_eval_namespace(state_memory: dict, current_sheet: str, expand_range_fn) -> dict:
    def _ref(coord: str):
        coord = coord.replace('$', '')
        if ':' in coord:
            cells = expand_range_fn(coord)
            flat = [state_memory.get(f"{current_sheet}!{c}", state_memory.get(c)) for c in cells]
            # Detect multi-column range → return 2D list for VLOOKUP/HLOOKUP/INDEX
            clean = coord.replace('$', '').upper()
            parts_rng = clean.split(':')
            if len(parts_rng) == 2:
                m1 = re.match(r'^([A-Z]+)', parts_rng[0])
                m2 = re.match(r'^([A-Z]+)', parts_rng[1])
                if m1 and m2:
                    nc = abs(column_index_from_string(m2.group(1)) - column_index_from_string(m1.group(1))) + 1
                    if nc > 1 and len(flat) % nc == 0:
                        return [flat[i:i+nc] for i in range(0, len(flat), nc)]
            return flat
        if '!' in coord:
            sheet_p, cell_p = coord.split('!', 1)
            v = state_memory.get(f"{sheet_p}!{cell_p}", state_memory.get(coord))
        else:
            v = state_memory.get(f"{current_sheet}!{coord}", state_memory.get(coord))
        return _XL_BLANK if v is None else v

    ns = {'__builtins__': {}, 'math': math, 'True': True, 'False': False, 'None': None,
          '_ref': _ref, '_sdiv': _sdiv, 'abs': abs, 'int': _xl_int, 'round': _xl_round,
          'pow': _xl_power, 'min': _xl_min, 'max': _xl_max, 'sum': _xl_sum,
          'len': _xl_len, 'str': str}
    # injeta todas as funções _xl_*
    g = globals()
    for name, fn in g.items():
        if name.startswith('_xl_') and callable(fn):
            ns[name] = fn
    return ns


# ── Transpiler fórmula → Python ────────────────────────────────────────────

def _tokenize_to_python(formula: str) -> str:
    if not _HAS_TOKENIZER:
        raise RuntimeError("openpyxl Tokenizer não disponível")

    clean = formula.replace('$', '')
    if not clean.startswith('='):
        clean = '=' + clean

    try:
        tok = Tokenizer(clean)
    except Exception:
        raise ValueError(f"Falha ao tokenizar: {formula[:80]}")

    parts = []
    for token in tok.items:
        ttype = token.type
        tsub  = token.subtype
        tval  = token.value.replace('$', '')

        if ttype == 'OPERAND':
            if tsub == 'NUMBER' or re.match(r'^-?\d+(\.\d+)?([eE][+-]?\d+)?$', tval):
                parts.append(tval)
            elif tval.endswith('%') and re.match(r'^-?\d+(\.\d+)?%$', tval):
                parts.append(str(float(tval[:-1]) / 100))
            elif tsub == 'TEXT' or (tval.startswith('"') and tval.endswith('"')):
                parts.append(tval)
            elif tsub == 'LOGICAL' or tval.upper() in ('TRUE', 'FALSE'):
                parts.append('True' if tval.upper() == 'TRUE' else 'False')
            else:
                parts.append(f"_ref({tval!r})")

        elif ttype == 'FUNC':
            if tsub == 'OPEN':
                func_name = tval.rstrip('(').upper()
                py_func = EXCEL_FUNC_MAP.get(func_name)
                if py_func is None:
                    # Tentar sem prefixo _XLFN.
                    stripped = re.sub(r'^_XLFN\.', '', func_name)
                    py_func = EXCEL_FUNC_MAP.get(stripped, stripped.lower())
                parts.append(f"{py_func}(")
            elif tsub == 'CLOSE':
                parts.append(')')

        elif ttype == 'SEP':
            parts.append(',')

        elif ttype == 'OPERATOR-INFIX':
            if tval == '=':    parts.append('==')
            elif tval == '<>': parts.append('!=')
            elif tval == '&':  parts.append('+')
            elif tval == '^':  parts.append('**')
            else:              parts.append(tval)

        elif ttype == 'OPERATOR-PREFIX':
            parts.append(tval)

        elif ttype == 'OPERATOR-POSTFIX':
            if tval == '%':
                parts.append('/100')
            else:
                parts.append('')

        elif ttype == 'ARRAY':
            # Constante de array {1,2,3} → lista Python [1,2,3]
            if tsub == 'OPEN':
                parts.append('[')
            elif tsub == 'CLOSE':
                parts.append(']')

        elif ttype == 'PAREN':
            parts.append(tval)

    expr = ''.join(parts)
    # Replace simple a/b patterns with _sdiv(a,b) for safe zero-division handling
    # Matches: _ref('X1')/something or number/something (simple right operand)
    expr = re.sub(
        r"(_ref\('[^']+'\)|(?<![_\w])-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:/100)?)\s*/\s*(_ref\('[^']+'\)|(?<![_\w])-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:/100)?)",
        r'_sdiv(\1,\2)',
        expr
    )
    return expr


# ── API pública ────────────────────────────────────────────────────────────

def evaluate_formula(formula: str, state_memory: dict, current_sheet: str, expand_range_fn) -> Any:
    """
    Avalia uma fórmula Excel. Retorna None para #DIV/0!, '#VALUE!' para TypeError.
    Lança ValueError para referências externas ([workbook]).
    """
    # Referência externa: [workbook.xlsx] fora de strings literais
    if '[' in formula:
        _formula_clean = re.sub(r'"[^"]*"', '', formula)
        if re.search(r'\[[^\]]+\.(xlsx|xlsm|xls|xlsb|xlam|csv)\]', _formula_clean, re.IGNORECASE):
            return '#EXT!'  # referência a workbook externo — não avaliável

    py_expr = _tokenize_to_python(formula)
    ns = _build_eval_namespace(state_memory, current_sheet, expand_range_fn)

    try:
        result = eval(py_expr, ns)  # noqa: S307
        # Normalizar ExcelError → string para comparação com gabarito
        if isinstance(result, ExcelError):
            return result.code
        return result
    except ZeroDivisionError:
        return '#DIV/0!'  # Excel: divisão por zero → erro explícito, não None
    except TypeError:
        return '#VALUE!'
    except SyntaxError:
        return '#VALUE!'  # fórmula malformada ou vazia
    except (NameError, AttributeError):
        raise

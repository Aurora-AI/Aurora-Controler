"""
EXRS Phase A2.5 — Formula Pattern Registry
Classifica fórmulas deterministicamente.
LLM permitido apenas como fallback documentado para UNRESOLVED.
"""
import sys
from pathlib import Path

# Setup paths for trustware and other phases
REPO_ROOT = Path(r"C:\Projetos\ExcelReverseEngine")
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1"))
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))

from pipeline_contracts import (
    FormulaPattern, PatternRegistryEntry, PatternClass,
    NormalizedWorkbookIR, FormulaTokenType, FormulaRegistryMap
)


def build_registry() -> list[PatternRegistryEntry]:
    """Constrói o registry determinístico de padrões de fórmula — cobertura completa."""
    return [
        # ── AGGREGATION ──────────────────────────────
        PatternRegistryEntry(
            rule_name="sum",
            pattern_class=PatternClass.AGGREGATION,
            function_names=["SUM", "SOMA", "SUBTOTAL", "AGREGAR", "AGGREGATE",
                            "SUMPRODUCT", "SOMARPRODUTO", "SUMSQ", "SUMX2MY2", "SUMX2PY2", "SUMXMY2"],
            description="Soma, produto e agregação de valores",
        ),
        PatternRegistryEntry(
            rule_name="average",
            pattern_class=PatternClass.AGGREGATION,
            function_names=["AVERAGE", "AVERAGEA", "MÉDIA", "MÉDIAA", "MEDIA", "TRIMMEAN", "MÉDIA.INTERNA",
                            "GEOMEAN", "MÉDIA.GEOMÉTRICA", "HARMEAN", "MÉDIA.HARMÔNICA"],
            description="Média aritmética, geométrica e harmônica",
        ),
        PatternRegistryEntry(
            rule_name="count",
            pattern_class=PatternClass.AGGREGATION,
            function_names=["COUNT", "COUNTA", "COUNTBLANK", "CONT.NÚM", "CONT.VALORES", "CONTAR.VAZIO"],
            description="Contagem de células",
        ),
        PatternRegistryEntry(
            rule_name="countif",
            pattern_class=PatternClass.AGGREGATION,
            function_names=["COUNTIF", "COUNTIFS", "CONT.SE", "CONT.SES"],
            description="Contagem condicional",
        ),
        PatternRegistryEntry(
            rule_name="sumif",
            pattern_class=PatternClass.AGGREGATION,
            function_names=["SUMIF", "SUMIFS", "SOMASE", "SOMASES",
                            "AVERAGEIF", "AVERAGEIFS", "MÉDIASE", "MÉDIASES"],
            description="Soma ou média condicional",
        ),
        PatternRegistryEntry(
            rule_name="min_max",
            pattern_class=PatternClass.AGGREGATION,
            function_names=["MIN", "MAX", "MINA", "MAXA", "MÍNIMO", "MÁXIMO",
                            "MAXIFS", "MINIFS", "MÁXIMOSES", "MÍNIMOSES"],
            description="Valor mínimo ou máximo, com ou sem critério",
        ),
        PatternRegistryEntry(
            rule_name="statistical",
            pattern_class=PatternClass.AGGREGATION,
            function_names=[
                "STDEV", "STDEV.S", "STDEV.P", "STDEVA", "STDEVPA", "DESVPAD", "DESVPAD.A", "DESVPAD.P", "DESVPADP",
                "VAR", "VAR.S", "VAR.P", "VARA", "VARPA", "VAR.A",
                "AVEDEV", "DESVQ", "DESV.MÉDIO", "DEVSQ",
                "MEDIAN", "MED", "MODE", "MODE.SNGL", "MODE.MULT", "MODO",
                "SKEW", "SKEW.P", "KURT", "STANDARDIZE", "PADRONIZAR",
                "CORREL", "COVAR", "COVARIANCE.P", "COVARIANCE.S", "PEARSON",
                "SLOPE", "INTERCEPT", "RSQ", "STEYX", "INCLINAÇÃO", "INTERCEPTAÇÃO",
                "FORECAST", "FORECAST.LINEAR", "PREVISÃO",
                "PERCENTILE", "PERCENTILE.INC", "PERCENTILE.EXC", "PERCENTIL",
                "PERCENTRANK", "PERCENTRANK.INC", "PERCENTRANK.EXC",
                "QUARTILE", "QUARTILE.INC", "QUARTILE.EXC", "QUARTIL",
                "CONFIDENCE", "CONFIDENCE.NORM", "CONFIDENCE.T", "INT.CONFIANÇA",
                "NORM.DIST", "NORM.S.DIST", "NORM.INV", "NORM.S.INV",
                "NORMDIST", "NORMSDIST", "NORMINV", "NORMSINV",
                "DIST.NORM", "DIST.NORMP", "INV.NORM", "INV.NORMP",
                "T.DIST", "T.DIST.2T", "T.DIST.RT", "TDIST", "T.INV", "T.INV.2T", "TINV",
                "F.DIST", "F.DIST.RT", "FDIST", "F.INV", "F.INV.RT", "FINV",
                "CHISQ.DIST", "CHISQ.DIST.RT", "CHISQ.INV", "CHISQ.INV.RT",
                "BINOM.DIST", "BINOMDIST", "BINOM.INV", "CRITBINOM",
                "NEGBINOM.DIST", "NEGBINOMDIST",
                "POISSON.DIST", "POISSON", "DISTR.POISSON",
                "EXPON.DIST", "EXPONDIST",
                "GAMMA.DIST", "GAMMADIST", "GAMMA.INV", "GAMMAINV", "GAMMA", "GAMMALN", "GAMMALN.PRECISE",
                "BETA.DIST", "BETADIST", "BETA.INV", "BETAINV",
                "LOGNORM.DIST", "LOGNORMDIST", "LOGNORM.INV", "LOGINV",
                "HYPGEOM.DIST", "HYPGEOMDIST",
                "WEIBULL.DIST", "WEIBULL",
                "FISHER", "FISHERINV", "GAUSS", "PHI",
                "PROB", "FREQUENCY", "FREQUÊNCIA",
                "LINEST", "LOGEST", "TREND", "GROWTH", "PROJ.LIN", "PROJ.LOG", "TENDÊNCIA", "CRESCIMENTO",
                "F.TEST", "FTEST", "T.TEST", "TTEST", "CHISQ.TEST", "CHITEST", "Z.TEST", "ZTEST",
            ],
            description="Funções estatísticas e distribuições de probabilidade",
        ),

        # ── CONDITIONAL ──────────────────────────────
        PatternRegistryEntry(
            rule_name="if_simple",
            pattern_class=PatternClass.CONDITIONAL,
            function_names=["IF", "SE"],
            description="Condicional simples IF/SE",
        ),
        PatternRegistryEntry(
            rule_name="if_nested",
            pattern_class=PatternClass.CONDITIONAL,
            function_names=["IFS", "SES", "IFERROR", "SEERRO", "IFNA", "SENÃODISP", "SWITCH", "PARÂMETRO"],
            description="Condicional aninhado, tratamento de erro e switch",
        ),
        PatternRegistryEntry(
            rule_name="boolean_operators",
            pattern_class=PatternClass.CONDITIONAL,
            function_names=["AND", "E", "OR", "OU", "NOT", "NÃO", "XOR",
                            "TRUE", "FALSE", "VERDADEIRO", "FALSO"],
            description="Operadores booleanos",
        ),
        PatternRegistryEntry(
            rule_name="is_functions",
            pattern_class=PatternClass.CONDITIONAL,
            function_names=["ISBLANK", "ISERROR", "ISERR", "ISNA", "ISNUMBER", "ISTEXT",
                            "ISNONTEXT", "ISLOGICAL", "ISREF", "ISEVEN", "ISODD", "ISFORMULA",
                            "ÉCÉL.VAZIA", "ÉERRO", "ÉERROS", "ÉNÚMERO", "ÉTEXTO", "ÉLÓGICO",
                            "É.NÃO.TEXTO", "É.NÃO.DISP", "ÉPAR", "ÉIMPAR", "ÉFÓRMULA",
                            "NA", "N/D", "NÃO.DISP", "TYPE", "TIPO", "ERROR.TYPE", "INFO", "INFORMAÇÃO"],
            description="Funções de informação e verificação de tipo",
        ),

        # ── LOOKUP ───────────────────────────────────
        PatternRegistryEntry(
            rule_name="vlookup",
            pattern_class=PatternClass.LOOKUP,
            function_names=["VLOOKUP", "PROCV", "HLOOKUP", "PROCH", "LOOKUP", "PROC"],
            description="Busca vertical, horizontal e geral",
        ),
        PatternRegistryEntry(
            rule_name="index_match",
            pattern_class=PatternClass.LOOKUP,
            function_names=["INDEX", "ÍNDICE", "MATCH", "CORRESP",
                            "XLOOKUP", "PROCX", "XMATCH",
                            "_XLFN.XLOOKUP", "_XLFN.PROCX", "_XLFN.XMATCH"],
            description="Busca avançada com INDEX/MATCH ou XLOOKUP",
        ),
        PatternRegistryEntry(
            rule_name="reference",
            pattern_class=PatternClass.LOOKUP,
            function_names=["OFFSET", "DESLOC", "INDIRECT", "INDIRETO",
                            "ADDRESS", "ENDEREÇO", "ROW", "LIN", "ROWS", "LINS",
                            "COLUMN", "COL", "COLUMNS", "COLS", "AREAS", "ÁREAS",
                            "CHOOSE", "ESCOLHER", "TRANSPOSE", "TRANSPOR",
                            "GETPIVOTDATA", "INFODADOSTABELADINÂMICA",
                            "HYPERLINK", "HIPERLINK", "FORMULATEXT", "FÓRMULATEXTO"],
            description="Funções de referência e navegação",
        ),
        PatternRegistryEntry(
            rule_name="dynamic_array",
            pattern_class=PatternClass.LOOKUP,
            function_names=["FILTER", "FILTRO", "SORT", "CLASSIFICAR", "SORTBY", "CLASSIFICARPOR",
                            "UNIQUE", "ÚNICO", "SEQUENCE", "SEQUÊNCIA",
                            "RANDARRAY", "MATRIZALEATÓRIA",
                            "TOCOL", "TOROW", "HSTACK", "VSTACK",
                            "TAKE", "DROP", "CHOOSEROWS", "CHOOSECOLS", "EXPAND", "TRIMRANGE",
                            "MAKEARRAY", "BYCOL", "BYROW", "SCAN", "REDUCE", "MAP",
                            "LAMBDA", "LET", "GROUPBY", "PIVOTBY",
                            "_XLFN.FILTER", "_XLFN.SORT", "_XLFN.UNIQUE", "_XLFN.SEQUENCE",
                            "_XLFN.LAMBDA", "_XLFN.LET"],
            description="Funções de array dinâmico (Excel 365)",
        ),

        # ── DATE LOGIC ───────────────────────────────
        PatternRegistryEntry(
            rule_name="date_extraction",
            pattern_class=PatternClass.DATE_LOGIC,
            function_names=["YEAR", "ANO", "MONTH", "MÊS", "DAY", "DIA",
                            "WEEKDAY", "DIA.DA.SEMANA", "WEEKNUM", "NÚM.SEMANA",
                            "ISOWEEKNUM", "HOUR", "HORA", "MINUTE", "MINUTO", "SECOND", "SEGUNDO"],
            description="Extração de componentes de data e hora",
        ),
        PatternRegistryEntry(
            rule_name="date_arithmetic",
            pattern_class=PatternClass.DATE_LOGIC,
            function_names=["DATE", "DATA", "TIME", "TEMPO", "DATEVALUE", "DATA.VALOR",
                            "TIMEVALUE", "VALOR.TEMPO",
                            "EDATE", "DATAM", "EOMONTH", "FIMMÊS",
                            "DATEDIF", "DATADIF", "DAYS", "DIAS", "DAYS360", "DIAS360",
                            "NETWORKDAYS", "DIATRABALHOTOTAL", "NETWORKDAYS.INTL",
                            "WORKDAY", "DIAÚTIL", "WORKDAY.INTL", "YEARFRAC"],
            description="Aritmética, construção e diferença de datas",
        ),
        PatternRegistryEntry(
            rule_name="now_today",
            pattern_class=PatternClass.DATE_LOGIC,
            function_names=["NOW", "AGORA", "TODAY", "HOJE"],
            description="Data/hora atual (volátil)",
        ),

        # ── TEXT TRANSFORMATION ──────────────────────
        PatternRegistryEntry(
            rule_name="text_case",
            pattern_class=PatternClass.TEXT_TRANSFORMATION,
            function_names=["UPPER", "MAIÚSCULA", "LOWER", "MINÚSCULA", "PROPER", "PRI.MAIÚSCULA",
                            "TRIM", "ARRUMAR", "CLEAN", "TIRAR", "LEN", "NÚM.CARACT",
                            "LENB", "UNICODE", "UNICHAR", "CHAR", "CARACT", "CODE", "CÓDIGO",
                            "ASC", "DBCS", "JIS", "PHONETIC", "FONÉTICA", "BAHTTEXT"],
            description="Transformação, limpeza e medição de texto",
        ),
        PatternRegistryEntry(
            rule_name="text_extraction",
            pattern_class=PatternClass.TEXT_TRANSFORMATION,
            function_names=["LEFT", "ESQUERDA", "LEFTB", "RIGHT", "DIREITA", "RIGHTB",
                            "MID", "EXT.TEXTO", "MIDB",
                            "TEXTAFTER", "TEXTBEFORE", "TEXTSPLIT",
                            "REGEXEXTRACT", "REGEXREPLACE", "REGEXTEST"],
            description="Extração e transformação de substrings",
        ),
        PatternRegistryEntry(
            rule_name="text_join",
            pattern_class=PatternClass.TEXT_TRANSFORMATION,
            function_names=["CONCATENATE", "CONCATENAR", "CONCAT", "TEXTJOIN", "UNIRTEXTO",
                            "ARRAYTOTEXT", "&", "REPT",
                            "_XLFN.CONCAT", "_XLFN.TEXTJOIN"],
            description="Concatenação e repetição de texto",
        ),
        PatternRegistryEntry(
            rule_name="text_search",
            pattern_class=PatternClass.TEXT_TRANSFORMATION,
            function_names=["FIND", "PROCURAR", "FINDB", "SEARCH", "PESQUISAR", "LOCALIZAR", "SEARCHB",
                            "SUBSTITUTE", "SUBSTITUIR", "REPLACE", "REPLACEB",
                            "EXACT", "EXATO"],
            description="Busca, substituição e comparação de texto",
        ),
        PatternRegistryEntry(
            rule_name="text_format",
            pattern_class=PatternClass.TEXT_TRANSFORMATION,
            function_names=["TEXT", "TEXTO", "VALUE", "VALOR", "NUMBERVALUE", "VALORNUMÉRICO",
                            "DOLLAR", "DÓLAR", "MOEDA", "FIXED", "DEF.NÚM.DEC", "CORRIGIDO",
                            "T", "N", "ENCODEURL", "CODIFURL"],
            description="Formatação e conversão de texto/número",
        ),

        # ── RANKING ──────────────────────────────────
        PatternRegistryEntry(
            rule_name="rank",
            pattern_class=PatternClass.RANKING,
            function_names=["RANK", "ORDEM", "RANK.EQ", "ORDEM.EQ", "RANK.AVG", "ORDEM.MÉD"],
            description="Ordenação e ranking de valores",
        ),
        PatternRegistryEntry(
            rule_name="large_small",
            pattern_class=PatternClass.RANKING,
            function_names=["LARGE", "MAIOR", "SMALL", "MENOR"],
            description="k-ésimo maior ou menor valor",
        ),

        # ── THRESHOLD LOGIC ──────────────────────────
        PatternRegistryEntry(
            rule_name="comparison_operators",
            pattern_class=PatternClass.THRESHOLD_LOGIC,
            function_names=["=", ">", "<", ">=", "<=", "<>"],
            description="Operadores de comparação em fórmulas",
        ),
        PatternRegistryEntry(
            rule_name="rounding",
            pattern_class=PatternClass.THRESHOLD_LOGIC,
            function_names=["ROUND", "ARRED", "ROUNDUP", "ARREDONDAR.PARA.CIMA",
                            "ROUNDDOWN", "ARREDONDAR.PARA.BAIXO",
                            "CEILING", "TETO", "CEILING.MATH", "CEILING.PRECISE",
                            "FLOOR", "PISO", "FLOOR.MATH", "FLOOR.PRECISE",
                            "MROUND", "MARRED", "EVEN", "PAR", "ODD", "ÍMPAR",
                            "INT", "TRUNC", "TRUNCAR", "ISO.CEILING"],
            description="Arredondamento e truncamento numérico",
        ),
        PatternRegistryEntry(
            rule_name="abs_sign",
            pattern_class=PatternClass.THRESHOLD_LOGIC,
            function_names=["ABS", "SIGN", "SINAL", "MOD", "QUOTIENT", "QUOCIENTE",
                            "DELTA", "GESTEP", "DEGRAU"],
            description="Valor absoluto, sinal, módulo e comparação numérica",
        ),

        # ── ARITHMETIC ───────────────────────────────
        PatternRegistryEntry(
            rule_name="basic_arithmetic",
            pattern_class=PatternClass.ARITHMETIC,
            function_names=["+", "-", "*", "/", "^", "%"],
            description="Operações aritméticas básicas (operadores inline)",
        ),
        PatternRegistryEntry(
            rule_name="math_functions",
            pattern_class=PatternClass.ARITHMETIC,
            function_names=[
                "PRODUCT", "MULT", "POWER", "POTÊNCIA", "SQRT", "RAIZ", "SQRTPI", "RAIZPI",
                "EXP", "LN", "LOG", "LOG10",
                "FACT", "FATORIAL", "FACTDOUBLE", "FATDUPLO",
                "COMBIN", "COMBINA", "PERMUT", "PERMUTATIONA",
                "GCD", "MDC", "LCM", "MMC",
                "PI", "RAND", "ALEATÓRIO", "RANDBETWEEN", "ALEATÓRIOENTRE",
                "DEGREES", "GRAUS", "RADIANS", "RADIANOS",
                "SIN", "SEN", "COS", "TAN", "ASIN", "ASEN", "ACOS", "ATAN", "ATAN2",
                "SINH", "SENH", "COSH", "TANH", "ASINH", "ACOSH", "ATANH",
                "SEC", "CSC", "COT", "SECH", "CSCH", "COTH", "ACOT", "ACOTH",
                "SERIESSUM", "SOMASEQU÷NCIA", "MULTINOMIAL",
                "BASE", "DECIMAL", "ARABIC", "ÁRABE", "ROMAN", "ROMANO",
                "MUNIT", "MMULT", "MDETERM", "MINVERSE",
            ],
            description="Funções matemáticas, trigonométricas e matriciais",
        ),
        PatternRegistryEntry(
            rule_name="financial",
            pattern_class=PatternClass.ARITHMETIC,
            function_names=[
                "PMT", "PGTO", "IPMT", "IPGTO", "PPMT", "PPGTO",
                "FV", "VF", "PV", "VP", "NPER", "RATE", "TAXA",
                "NPV", "VPL", "XNPV", "IRR", "TIR", "XIRR", "MIRR", "MTIR",
                "SLN", "DPD", "SYD", "SDA", "DDB", "BDD",
                "EFFECT", "EFETIVA", "NOMINAL", "PDURATION", "DURAÇÃOP", "RRI", "TAXAJURO",
                "ISPMT", "ÉPGTO", "FVSCHEDULE", "VFPLANO",
                "DOLLARDE", "MOEDADEC", "DOLLARFR", "MOEDAFRA",
                "DURATION", "DURAÇÃO", "MDURATION", "MDURAÇÃO",
                "DISC", "DESC", "INTRATE", "TAXAJUROS", "RECEIVED", "RECEBER",
                "TBILLEQ", "OTN", "TBILLPRICE", "OTNVALOR", "TBILLYIELD", "OTNLUCRO",
                "PRICE", "PREÇO", "PRICEDISC", "PREÇODESC", "PRICEMAT", "PREÇOVENC",
                "YIELD", "LUCRO", "YIELDDISC", "LUCRODESC", "YIELDMAT", "LUCROVENC",
                "ACCRINT", "JUROSACUM", "ACCRINTM", "JUROSACUMV",
                "COUPDAYBS", "CUPDIASINLIQ", "COUPDAYS", "CUPDIAS",
                "COUPDAYSNC", "COUPNCD", "COUPNUM", "CUPNÚM", "COUPPCD",
                "CUMIPMT", "PGTOJURACUM", "CUMPRINC", "PGTOCAPACUM",
                "ODDFPRICE", "PREÇOPRIMINC", "ODDFYIELD", "LUCROPRIMINC",
                "ODDLPRICE", "PREÇOÚLTINC", "ODDLYIELD", "LUCROÚLTINC",
                "AMORDEGRC", "AMORLINC",
            ],
            description="Funções financeiras (juros, amortização, investimento)",
        ),
        PatternRegistryEntry(
            rule_name="engineering",
            pattern_class=PatternClass.ARITHMETIC,
            function_names=[
                "BIN2DEC", "BINADEC", "BIN2HEX", "BINAHEX", "BIN2OCT", "BINAOCT",
                "DEC2BIN", "DECABIN", "DEC2HEX", "DECAHEX", "DEC2OCT", "DECAOCT",
                "HEX2BIN", "HEXABIN", "HEX2DEC", "HEXADEC", "HEX2OCT", "HEXAOCT",
                "OCT2BIN", "OCTABIN", "OCT2DEC", "OCTADEC", "OCT2HEX", "OCTAHEX",
                "BITAND", "BITOR", "BITXOR", "BITLSHIFT", "DESLOCESQBIT",
                "BITRSHIFT", "DESLOCDIRBIT",
                "CONVERT", "CONVERTER",
                "DELTA", "GESTEP", "DEGRAU",
                "ERF", "FUNERRO", "ERF.PRECISE", "ERFC", "FUNERROCOMPL", "ERFC.PRECISE",
                "BESSELI", "BESSELJ", "BESSELK", "BESSELY",
                "COMPLEX", "COMPLEXO",
                "IMABS", "IMAGINARY", "IMAGINÁRIO", "IMARGUMENT", "IMARG",
                "IMCONJUGATE", "IMCONJ", "IMCOS", "IMCOSH", "IMCOT",
                "IMCSC", "IMCOSEC", "IMCSCH", "IMCOSECH",
                "IMDIV", "IMEXP", "IMLN", "IMLOG10", "IMLOG2",
                "IMPOWER", "IMPOT", "IMPRODUCT", "IMPROD",
                "IMREAL", "IMSEC", "IMSECH", "IMSIN", "IMSENO", "IMSINH", "IMSENH",
                "IMSQRT", "IMRAIZ", "IMSUB", "IMSUBTR", "IMSUM", "IMSOMA", "IMTAN",
            ],
            description="Funções de engenharia, bases numéricas e números complexos",
        ),
        PatternRegistryEntry(
            rule_name="database",
            pattern_class=PatternClass.AGGREGATION,
            function_names=[
                "DAVERAGE", "BDMÉDIA", "DCOUNT", "BDCONTAR", "DCOUNTA", "BDCONTARA",
                "DGET", "BDEXTRAIR", "DMAX", "BDMÁX", "DMIN", "BDMÍN",
                "DPRODUCT", "BDMULTIPL", "DSTDEV", "BDEST", "DSTDEVP", "BDDESVPA",
                "DSUM", "BDSOMA", "DVAR", "BDVAREST", "DVARP", "BDVARP",
            ],
            description="Funções de banco de dados (BD*)",
        ),
    ]


def classify_formula(
    tokens: list,  # list[FormulaToken]
    registry: list[PatternRegistryEntry],
    node_id: str = "",
    formula_raw: str = "",
) -> FormulaPattern:
    """
    Classifica uma fórmula tokenizada contra o registry determinístico.
    Retorna UNRESOLVED se nenhuma regra capturar.
    """
    # Extrair nomes de função dos tokens (ignorando case)
    function_names: set[str] = set()
    has_inline_operators = False
    unique_types = set()
    
    for token in tokens:
        unique_types.add(token.type)
        if token.type == FormulaTokenType.FUNCTION:
            function_names.add(token.value.upper())
        elif token.type == FormulaTokenType.OPERATOR:
            if token.value in ('+', '-', '*', '/', '^', '%'):
                has_inline_operators = True
    
    # Calcular Índice de Densidade Lógica (LDI)
    total_tokens = len(tokens)
    ldi = len(unique_types) / max(total_tokens, 1)
    ldi = round(ldi, 4)
    
    # Buscar no registry
    for entry in registry:
        entry_funcs = [f.upper() for f in entry.function_names]
        if any(func in function_names for func in entry_funcs):
            return FormulaPattern(
                node_id=node_id,
                formula_raw=formula_raw,
                pattern_class=entry.pattern_class,
                matched_rule=entry.rule_name,
                confidence=1.0,
                logic_density_index=ldi
            )
    
    # Se não encontrou função registrada mas tem operadores inline
    if has_inline_operators and not function_names:
        return FormulaPattern(
            node_id=node_id,
            formula_raw=formula_raw,
            pattern_class=PatternClass.ARITHMETIC,
            matched_rule="inline_arithmetic",
            confidence=1.0,
            logic_density_index=ldi
        )

    # Referência de célula pura: =C17, =$Y$8, =Sheet2!A1
    # Token único do tipo OPERAND, sem funções nem operadores
    operand_tokens = [t for t in tokens if t.type == FormulaTokenType.OPERAND]
    if len(operand_tokens) == 1 and not function_names and not has_inline_operators:
        return FormulaPattern(
            node_id=node_id,
            formula_raw=formula_raw,
            pattern_class=PatternClass.ARITHMETIC,
            matched_rule="cell_reference",
            confidence=1.0,
            logic_density_index=ldi
        )

    # Fallback: UNRESOLVED
    return FormulaPattern(
        node_id=node_id,
        formula_raw=formula_raw,
        pattern_class=PatternClass.UNRESOLVED,
        matched_rule=None,
        confidence=0.0,
        logic_density_index=ldi
    )


def classify_workbook(
    normalized_ir: NormalizedWorkbookIR,
    registry: list[PatternRegistryEntry],
) -> FormulaRegistryMap:
    """
    Classifica todas as fórmulas de um workbook contra o registry.
    """
    patterns: list[FormulaPattern] = []
    
    for sheet in normalized_ir.sheets:
        for cell in sheet.cells:
            node_id = f"{sheet.name}!{cell.coordinate}"

            # Células com referências externas [workbook] → classificar diretamente
            if cell.has_external_ref and cell.formula_raw:
                patterns.append(FormulaPattern(
                    node_id=node_id,
                    formula_raw=cell.formula_raw,
                    pattern_class=PatternClass.EXTERNAL_REF,
                    matched_rule="external_ref",
                    confidence=1.0,
                    logic_density_index=0.0,
                ))
                continue

            # Se não tem tokens, não é uma fórmula (ou foi ignorada)
            if not cell.formula_tokens:
                continue

            pattern = classify_formula(
                tokens=cell.formula_tokens,
                registry=registry,
                node_id=node_id,
                formula_raw=cell.formula_raw or "",
            )
            patterns.append(pattern)
    
    unresolved_count = sum(1 for p in patterns if p.pattern_class == PatternClass.UNRESOLVED)
    
    return FormulaRegistryMap(
        file_path=normalized_ir.file_path,
        patterns=patterns,
        registry_used=registry,
        unresolved_count=unresolved_count,
        metadata={
            "total_formulas": len(patterns),
            "registry_size": len(registry),
        },
    )


if __name__ == "__main__":
    import argparse
    from extractor import extract_structure
    from normalizer import normalize_workbook
    
    parser = argparse.ArgumentParser(description="EXRS Phase A2.5 — Formula Pattern Registry")
    parser.add_argument("input", type=Path, help="Caminho para .xlsx")
    parser.add_argument("--output", type=Path, default=None, help="Caminho para formula_registry_map.json")
    args = parser.parse_args()
    
    if not args.input.exists():
        print(f"Erro: Arquivo não encontrado: {args.input}")
        sys.exit(1)
        
    raw = extract_structure(args.input)
    norm = normalize_workbook(raw)
    registry = build_registry()
    fmap = classify_workbook(norm, registry)
    
    output_path = args.output or args.input.with_suffix(".formula_registry_map.json")
    output_path.write_text(fmap.model_dump_json(indent=2), encoding="utf-8")
    print(f"Formula Registry Map saved to: {output_path}")
    print(f"Unresolved: {fmap.unresolved_count}/{fmap.metadata['total_formulas']}")

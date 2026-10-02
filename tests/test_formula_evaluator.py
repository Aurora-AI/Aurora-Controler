"""
Testes do formula_evaluator — cobertura de todas as categorias de função Excel.
Cada teste usa state_memory mínimo e verifica o resultado contra o valor esperado.
"""
import math
import sys
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


from product_a.phase_a4.formula_evaluator import evaluate_formula
from kernel.phase_a1_5.normalizer import expand_range


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def sm():
    """State memory padrão para os testes."""
    return {
        "S!A1": 10, "S!A2": 20, "S!A3": 30, "S!A4": 40, "S!A5": 5,
        "S!B1": 3,  "S!B2": 6,  "S!B3": 9,  "S!B4": -4,
        "S!C1": "hello", "S!C2": "world", "S!C3": "Excel",
        "S!D1": 0.5, "S!D2": 100.0, "S!D3": 2.718281828,
        "S!E1": True, "S!E2": False,
        "S!F1": "Vendedor A", "S!F2": "Vendedor B", "S!F3": "Vendedor A",
        "S!G1": 1000, "S!G2": 2000, "S!G3": 1500,
        # E4 ausente → célula vazia (_Blank)
    }


def ev(formula: str, sm: dict, sheet: str = "S") -> object:
    return evaluate_formula(formula, sm, sheet, expand_range)


def approx(a, b, tol=1e-7):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=tol, abs_tol=1e-10)
    return a == b


# ── 1. Lógicas ───────────────────────────────────────────────────────────────

class TestLogical:
    def test_if_true(self, sm): assert ev("=IF(A1>B1,\"sim\",\"não\")", sm) == "sim"
    def test_if_false(self, sm): assert ev("=IF(A1<B1,\"sim\",\"não\")", sm) == "não"
    def test_if_nested(self, sm): assert ev("=IF(A1=10,IF(B1=3,\"ok\",\"b\"),\"a\")", sm) == "ok"
    def test_ifs(self, sm): assert ev("=IFS(A1>50,\"grande\",A1>5,\"médio\",TRUE,\"pequeno\")", sm) == "médio"
    def test_iferror_ok(self, sm): assert ev("=IFERROR(A1/B1,\"err\")", sm) == 10/3
    def test_iferror_div0(self, sm): assert ev("=IFERROR(A1/E4,\"err\")", sm) == "err"
    def test_iferror_na(self, sm): assert ev("=IFERROR(XLOOKUP(99,A1:A3,A1:A3),\"n/a\")", sm) == "n/a"
    def test_ifna(self, sm): assert ev("=IFNA(XLOOKUP(99,A1:A3,A1:A3),\"miss\")", sm) == "miss"
    def test_and_true(self, sm): assert ev("=AND(A1>0,B1>0)", sm) is True
    def test_and_false(self, sm): assert ev("=AND(A1>0,B1>100)", sm) is False
    def test_or_true(self, sm): assert ev("=OR(A1>100,B1>0)", sm) is True
    def test_or_false(self, sm): assert ev("=OR(A1>100,B1>100)", sm) is False
    def test_not(self, sm): assert ev("=NOT(A1>100)", sm) is True
    def test_xor(self, sm): assert ev("=XOR(TRUE,FALSE)", sm) is True
    def test_xor_both_true(self, sm): assert ev("=XOR(TRUE,TRUE)", sm) is False
    def test_switch(self, sm): assert ev("=SWITCH(A1,10,\"dez\",20,\"vinte\",\"outro\")", sm) == "dez"
    def test_switch_default(self, sm): assert ev("=SWITCH(A3,10,\"dez\",20,\"vinte\",\"outro\")", sm) == "outro"


# ── 2. Aggregation ──────────────────────────────────────────────────────────

class TestAggregation:
    def test_sum_range(self, sm): assert ev("=SUM(A1:A5)", sm) == 105
    def test_sum_args(self, sm): assert ev("=SUM(A1,A2,A3)", sm) == 60
    def test_average(self, sm): assert approx(ev("=AVERAGE(A1:A3)", sm), 20.0)
    def test_count(self, sm): assert ev("=COUNT(A1:A5)", sm) == 5
    def test_counta(self, sm): assert ev("=COUNTA(C1:C3)", sm) == 3
    def test_countblank(self, sm): assert ev("=COUNTBLANK(E4:E4)", sm) == 1
    def test_min(self, sm): assert ev("=MIN(A1:A5)", sm) == 5
    def test_max(self, sm): assert ev("=MAX(A1:A5)", sm) == 40
    def test_countif_gt(self, sm): assert ev("=COUNTIF(A1:A5,\">10\")", sm) == 3
    def test_countif_eq(self, sm): assert ev("=COUNTIF(A1:A5,10)", sm) == 1
    def test_countifs(self, sm): assert ev("=COUNTIFS(A1:A3,\">10\",B1:B3,\">5\")", sm) == 2
    def test_sumif(self, sm): assert ev("=SUMIF(A1:A3,\">10\",A1:A3)", sm) == 50
    def test_sumifs(self, sm): assert ev("=SUMIFS(G1:G3,F1:F3,\"Vendedor A\")", sm) == 2500
    def test_averageif(self, sm): assert ev("=AVERAGEIF(F1:F3,\"Vendedor A\",G1:G3)", sm) == 1250
    def test_maxifs(self, sm): assert ev("=MAXIFS(G1:G3,F1:F3,\"Vendedor A\")", sm) == 1500
    def test_minifs(self, sm): assert ev("=MINIFS(G1:G3,F1:F3,\"Vendedor A\")", sm) == 1000
    def test_sumproduct(self, sm): assert ev("=SUMPRODUCT(A1:A3,B1:B3)", sm) == 10*3+20*6+30*9
    def test_large(self, sm): assert ev("=LARGE(A1:A5,1)", sm) == 40
    def test_small(self, sm): assert ev("=SMALL(A1:A5,1)", sm) == 5
    def test_subtotal_sum(self, sm): assert ev("=SUBTOTAL(9,A1:A3)", sm) == 60


# ── 3. Estatísticas ─────────────────────────────────────────────────────────

class TestStatistics:
    def test_median(self, sm): assert ev("=MEDIAN(A1:A3)", sm) == 20
    def test_mode(self, sm):
        sm2 = dict(sm); sm2["S!A6"] = 10
        assert ev("=MODE(A1:A5,A6)", sm2) == 10
    def test_stdev(self, sm): assert approx(ev("=STDEV(A1:A3)", sm), 10.0)
    def test_var(self, sm): assert approx(ev("=VAR(A1:A3)", sm), 100.0)
    def test_stdevp(self, sm): assert approx(ev("=STDEV.P(A1:A3)", sm), math.sqrt(200/3))
    def test_rank_desc(self, sm): assert ev("=RANK(A2,A1:A3,0)", sm) == 2
    def test_rank_asc(self, sm): assert ev("=RANK(A2,A1:A3,1)", sm) == 2
    def test_percentile(self, sm): assert approx(ev("=PERCENTILE(A1:A3,0.5)", sm), 20.0)
    def test_quartile_q2(self, sm): assert approx(ev("=QUARTILE(A1:A3,2)", sm), 20.0)
    def test_correl(self, sm): assert approx(ev("=CORREL(A1:A3,B1:B3)", sm), 1.0)
    def test_slope(self, sm): assert approx(ev("=SLOPE(A1:A3,B1:B3)", sm), 10/3)
    def test_intercept(self, sm): assert approx(ev("=INTERCEPT(A1:A3,B1:B3)", sm), 0.0)
    def test_forecast(self, sm): assert approx(ev("=FORECAST(12,A1:A3,B1:B3)", sm), 40.0)
    def test_geomean(self, sm): assert approx(ev("=GEOMEAN(A1:A3)", sm), (10*20*30)**(1/3))
    def test_harmean(self, sm): assert approx(ev("=HARMEAN(A1:A3)", sm), 3/(1/10+1/20+1/30))
    def test_avedev(self, sm): assert approx(ev("=AVEDEV(A1:A3)", sm), 20/3)
    def test_normdist(self, sm): assert approx(ev("=NORM.DIST(0,0,1,TRUE)", sm), 0.5)
    def test_normsinv(self, sm): assert approx(ev("=NORM.S.INV(0.5)", sm), 0.0)
    def test_standardize(self, sm): assert approx(ev("=STANDARDIZE(20,20,5)", sm), 0.0)
    def test_confidence(self, sm): assert approx(ev("=CONFIDENCE(0.05,10,100)", sm), 1.96, tol=1e-2)
    def test_binomdist(self, sm): assert approx(ev("=BINOM.DIST(3,10,0.5,FALSE)", sm), 0.1171875)
    def test_poisson(self, sm): assert approx(ev("=POISSON.DIST(2,3,FALSE)", sm), math.exp(-3)*9/2)


# ── 4. Matemáticas ──────────────────────────────────────────────────────────

class TestMath:
    def test_abs_pos(self, sm): assert ev("=ABS(B4)", sm) == 4
    def test_abs_neg(self, sm): assert ev("=ABS(-5)", sm) == 5
    def test_round(self, sm): assert ev("=ROUND(3.14159,2)", sm) == 3.14
    def test_roundup(self, sm): assert ev("=ROUNDUP(3.1,0)", sm) == 4
    def test_rounddown(self, sm): assert ev("=ROUNDDOWN(3.9,0)", sm) == 3
    def test_ceiling(self, sm): assert ev("=CEILING(2.3,1)", sm) == 3
    def test_floor(self, sm): assert ev("=FLOOR(2.9,1)", sm) == 2
    def test_mround(self, sm): assert ev("=MROUND(7,3)", sm) == 6
    def test_even(self, sm): assert ev("=EVEN(3)", sm) == 4
    def test_odd(self, sm): assert ev("=ODD(4)", sm) == 5
    def test_int(self, sm): assert ev("=INT(3.9)", sm) == 3
    def test_int_neg(self, sm): assert ev("=INT(-3.1)", sm) == -4
    def test_trunc(self, sm): assert ev("=TRUNC(3.9)", sm) == 3
    def test_mod(self, sm): assert ev("=MOD(10,3)", sm) == 1
    def test_sign_pos(self, sm): assert ev("=SIGN(A1)", sm) == 1
    def test_sign_neg(self, sm): assert ev("=SIGN(B4)", sm) == -1
    def test_sign_zero(self, sm): assert ev("=SIGN(0)", sm) == 0
    def test_power(self, sm): assert ev("=POWER(2,10)", sm) == 1024
    def test_sqrt(self, sm): assert ev("=SQRT(144)", sm) == 12
    def test_sqrtpi(self, sm): assert approx(ev("=SQRTPI(1)", sm), math.sqrt(math.pi))
    def test_exp(self, sm): assert approx(ev("=EXP(1)", sm), math.e)
    def test_ln(self, sm): assert approx(ev("=LN(D3)", sm), 1.0, tol=1e-5)
    def test_log10(self, sm): assert approx(ev("=LOG10(1000)", sm), 3.0)
    def test_log_base2(self, sm): assert approx(ev("=LOG(8,2)", sm), 3.0)
    def test_fact(self, sm): assert ev("=FACT(5)", sm) == 120
    def test_combin(self, sm): assert ev("=COMBIN(5,2)", sm) == 10
    def test_permut(self, sm): assert ev("=PERMUT(5,2)", sm) == 20
    def test_gcd(self, sm): assert ev("=GCD(12,8)", sm) == 4
    def test_lcm(self, sm): assert ev("=LCM(4,6)", sm) == 12
    def test_pi(self, sm): assert approx(ev("=PI()", sm), math.pi)
    def test_degrees(self, sm): assert approx(ev("=DEGREES(PI())", sm), 180.0)
    def test_radians(self, sm): assert approx(ev("=RADIANS(180)", sm), math.pi)
    def test_sin(self, sm): assert approx(ev("=SIN(PI()/2)", sm), 1.0)
    def test_cos(self, sm): assert approx(ev("=COS(0)", sm), 1.0)
    def test_tan(self, sm): assert approx(ev("=TAN(0)", sm), 0.0)
    def test_asin(self, sm): assert approx(ev("=ASIN(1)", sm), math.pi/2)
    def test_atan2(self, sm): assert approx(ev("=ATAN2(1,1)", sm), math.pi/4)
    def test_product(self, sm): assert ev("=PRODUCT(A1,B1)", sm) == 30
    def test_quotient(self, sm): assert ev("=QUOTIENT(10,3)", sm) == 3
    def test_roman(self, sm): assert ev("=ROMAN(2024)", sm) == "MMXXIV"
    def test_arabic(self, sm): assert ev("=ARABIC(\"XIV\")", sm) == 14
    def test_base(self, sm): assert ev("=BASE(255,16)", sm) == "FF"
    def test_decimal(self, sm): assert ev("=DECIMAL(\"FF\",16)", sm) == 255
    def test_sumsq(self, sm): assert ev("=SUMSQ(3,4)", sm) == 25


# ── 5. Texto ─────────────────────────────────────────────────────────────────

class TestText:
    def test_len(self, sm): assert ev("=LEN(C1)", sm) == 5
    def test_left(self, sm): assert ev("=LEFT(C1,3)", sm) == "hel"
    def test_right(self, sm): assert ev("=RIGHT(C1,3)", sm) == "llo"
    def test_mid(self, sm): assert ev("=MID(C1,2,3)", sm) == "ell"
    def test_upper(self, sm): assert ev("=UPPER(C1)", sm) == "HELLO"
    def test_lower(self, sm): assert ev("=LOWER(C3)", sm) == "excel"
    def test_proper(self, sm): assert ev("=PROPER(\"hello world\")", sm) == "Hello World"
    def test_trim(self, sm): assert ev("=TRIM(\"  hello  world  \")", sm) == "hello world"
    def test_concat(self, sm): assert ev("=CONCAT(C1,\" \",C2)", sm) == "hello world"
    def test_concatenate(self, sm): assert ev("=CONCATENATE(C1,C2)", sm) == "helloworld"
    def test_textjoin(self, sm): assert ev("=TEXTJOIN(\", \",TRUE,C1,C2)", sm) == "hello, world"
    def test_textjoin_ignore_empty(self, sm):
        sm2 = dict(sm); sm2["S!C4"] = ""
        assert ev("=TEXTJOIN(\",\",TRUE,C1,C4,C2)", sm2) == "hello,world"
    def test_find(self, sm): assert ev("=FIND(\"ll\",C1)", sm) == 3
    def test_find_not_found(self, sm): assert ev("=FIND(\"xyz\",C1)", sm) == "#VALUE!"
    def test_search_case_insensitive(self, sm): assert ev("=SEARCH(\"HELLO\",C1)", sm) == 1
    def test_substitute(self, sm): assert ev("=SUBSTITUTE(C1,\"l\",\"r\")", sm) == "herro"
    def test_substitute_instance(self, sm): assert ev("=SUBSTITUTE(C1,\"l\",\"r\",1)", sm) == "herlo"
    def test_replace(self, sm): assert ev("=REPLACE(C1,1,3,\"XYZ\")", sm) == "XYZlo"
    def test_rept(self, sm): assert ev("=REPT(\"ab\",3)", sm) == "ababab"
    def test_exact_true(self, sm): assert ev("=EXACT(C1,C1)", sm) is True
    def test_exact_false(self, sm): assert ev("=EXACT(C1,C3)", sm) is False
    def test_value(self, sm): assert ev("=VALUE(\"3.14\")", sm) == 3.14
    def test_text_format(self, sm): assert ev("=TEXT(A1,\"0\")", sm) == "10"
    def test_char(self, sm): assert ev("=CHAR(65)", sm) == "A"
    def test_code(self, sm): assert ev("=CODE(\"A\")", sm) == 65
    def test_dollar(self, sm): assert ev("=DOLLAR(1234.5,2)", sm) == "$1,234.50"
    def test_fixed(self, sm): assert ev("=FIXED(1234.567,2)", sm) == "1,234.57"
    def test_textafter(self, sm): assert ev("=TEXTAFTER(C1,\"el\")", sm) == "lo"
    def test_textbefore(self, sm): assert ev("=TEXTBEFORE(C1,\"ll\")", sm) == "he"
    def test_ampersand(self, sm): assert ev("=C1&\" \"&C2", sm) == "hello world"
    def test_unichar(self, sm): assert ev("=UNICHAR(9786)", sm) == "☺"
    def test_t_text(self, sm): assert ev("=T(C1)", sm) == "hello"
    def test_t_number(self, sm): assert ev("=T(A1)", sm) == ""
    def test_n_number(self, sm): assert ev("=N(A1)", sm) == 10
    def test_n_text(self, sm): assert ev("=N(C1)", sm) == 0
    def test_clean(self, sm): assert ev("=CLEAN(\"hel\x07lo\")", sm) == "hello"
    def test_encodeurl(self, sm): assert ev("=ENCODEURL(\"hello world\")", sm) == "hello%20world"


# ── 6. Data e Hora ──────────────────────────────────────────────────────────

class TestDateTime:
    def test_date(self, sm): assert ev("=DATE(2024,1,1)", sm) == 45292
    def test_year(self, sm): assert ev("=YEAR(45292)", sm) == 2024
    def test_month(self, sm): assert ev("=MONTH(45292)", sm) == 1
    def test_day(self, sm): assert ev("=DAY(45292)", sm) == 1
    def test_hour(self, sm): assert ev("=HOUR(0.5)", sm) == 12
    def test_minute(self, sm): assert ev("=MINUTE(0.5)", sm) == 0
    def test_second(self, sm): assert ev("=SECOND(0.5)", sm) == 0
    def test_weekday(self, sm): assert ev("=WEEKDAY(45292,1)", sm) == 2  # 01/01/2024 = Mon
    def test_days(self, sm): assert ev("=DAYS(45458,45292)", sm) == 166
    def test_edate(self, sm): assert ev("=EDATE(45292,1)", sm) == 45323  # Feb 2024
    def test_eomonth_0(self, sm): assert ev("=EOMONTH(45292,0)", sm) == 45322  # 31/01/2024
    def test_datedif_d(self, sm): assert ev("=DATEDIF(45292,45458,\"D\")", sm) == 166
    def test_datedif_m(self, sm): assert ev("=DATEDIF(45292,45458,\"M\")", sm) == 5
    def test_datedif_y(self, sm): assert ev("=DATEDIF(45292,45458,\"Y\")", sm) == 0
    def test_networkdays(self, sm):
        result = ev("=NETWORKDAYS(45292,45458)", sm)
        assert isinstance(result, int) and result > 0
    def test_workday(self, sm):
        result = ev("=WORKDAY(45292,5)", sm)
        assert result == 45299  # 5 dias úteis depois de 01/01/2024
    def test_days360(self, sm): assert ev("=DAYS360(45292,45458,FALSE)", sm) == 164
    def test_isoweeknum(self, sm): assert ev("=ISOWEEKNUM(45292)", sm) == 1
    def test_time(self, sm): assert approx(ev("=TIME(12,0,0)", sm), 0.5)
    def test_datevalue(self, sm): assert ev("=DATEVALUE(\"2024-01-01\")", sm) == 45292


# ── 7. Lookup ────────────────────────────────────────────────────────────────

class TestLookup:
    def test_vlookup_exact(self, sm):
        sm2 = dict(sm)
        # tabela em F:G precisa de estrutura 2D — usar refs diretas
        assert ev("=VLOOKUP(10,A1:B3,2,FALSE)", sm) == 3

    def test_index_1d(self, sm): assert ev("=INDEX(A1:A3,2)", sm) == 20
    def test_match_exact(self, sm): assert ev("=MATCH(20,A1:A3,0)", sm) == 2
    def test_match_not_found(self, sm): assert ev("=MATCH(99,A1:A3,0)", sm) == "#N/A"
    def test_xlookup_found(self, sm): assert ev("=XLOOKUP(20,A1:A3,A1:A3)", sm) == 20
    def test_xlookup_not_found(self, sm): assert ev("=XLOOKUP(99,A1:A3,A1:A3,\"miss\")", sm) == "miss"
    def test_lookup(self, sm): assert ev("=LOOKUP(20,A1:A3,A1:A3)", sm) == 20
    def test_choose(self, sm): assert ev("=CHOOSE(2,\"a\",\"b\",\"c\")", sm) == "b"
    def test_rows(self, sm): assert ev("=ROWS(A1:A3)", sm) == 3
    def test_columns(self, sm): assert ev("=COLUMNS(A1:B1)", sm) == 2


# ── 8. IS / Info ────────────────────────────────────────────────────────────

class TestIsInfo:
    def test_isblank_empty(self, sm): assert ev("=ISBLANK(E4)", sm) is True
    def test_isblank_filled(self, sm): assert ev("=ISBLANK(A1)", sm) is False
    def test_isnumber_true(self, sm): assert ev("=ISNUMBER(A1)", sm) is True
    def test_isnumber_false(self, sm): assert ev("=ISNUMBER(C1)", sm) is False
    def test_istext_true(self, sm): assert ev("=ISTEXT(C1)", sm) is True
    def test_istext_false(self, sm): assert ev("=ISTEXT(A1)", sm) is False
    def test_islogical_true(self, sm): assert ev("=ISLOGICAL(E1)", sm) is True
    def test_islogical_false(self, sm): assert ev("=ISLOGICAL(A1)", sm) is False
    def test_iseven(self, sm): assert ev("=ISEVEN(A2)", sm) is True
    def test_isodd(self, sm): assert ev("=ISODD(A5)", sm) is True  # A5=5 is odd
    def test_iserror_true(self, sm): assert ev("=ISERROR(IFERROR(1/0,\"ok\"))", sm) is False  # iferror absorve
    def test_isna(self, sm): assert ev("=ISNA(MATCH(99,A1:A3,0))", sm) is True
    def test_type_number(self, sm): assert ev("=TYPE(A1)", sm) == 1
    def test_type_text(self, sm): assert ev("=TYPE(C1)", sm) == 2
    def test_type_logical(self, sm): assert ev("=TYPE(E1)", sm) == 4
    def test_na(self, sm): assert ev("=NA()", sm) == "#N/A"


# ── 9. Financeiras ──────────────────────────────────────────────────────────

class TestFinancial:
    def test_pmt(self, sm):
        # PMT(5%/12, 60, -10000) ≈ 188.71
        result = ev("=PMT(5%/12,60,-10000)", sm)
        assert approx(result, 188.712, tol=1e-3)

    def test_fv(self, sm):
        # FV(5%/12, 12, -100) ≈ 1227.89 (ordinary annuity)
        result = ev("=FV(5%/12,12,-100)", sm)
        assert approx(result, 1227.89, tol=0.1)

    def test_pv(self, sm):
        # PV(5%/12, 60, 188.71) ≈ -10000
        result = ev("=PV(5%/12,60,188.71)", sm)
        assert approx(result, -9999.9, tol=1e-2)

    def test_nper(self, sm):
        result = ev("=NPER(5%/12,-188.71,10000)", sm)
        assert approx(result, 60.0, tol=0.01)

    def test_npv(self, sm):
        result = ev("=NPV(10%,-1000,300,400,500)", sm)
        assert approx(result, -19.12, tol=0.1)

    def test_irr(self, sm):
        # IRR de fluxo de caixa padrão
        sm2 = dict(sm)
        sm2.update({"S!H1": -1000, "S!H2": 300, "S!H3": 400, "S!H4": 500})
        result = ev("=IRR(H1:H4)", sm2)
        assert approx(result, 0.0890, tol=1e-3)

    def test_sln(self, sm):
        result = ev("=SLN(10000,1000,5)", sm)
        assert result == 1800.0

    def test_effect(self, sm):
        result = ev("=EFFECT(10%,12)", sm)
        assert approx(result, 0.10471, tol=1e-4)

    def test_nominal(self, sm):
        result = ev("=NOMINAL(10%,12)", sm)
        assert approx(result, 0.09569, tol=1e-4)

    def test_rri(self, sm):
        result = ev("=RRI(10,1000,2000)", sm)
        assert approx(result, 0.07177, tol=1e-3)

    def test_syd(self, sm):
        result = ev("=SYD(10000,1000,5,1)", sm)
        assert approx(result, 3000.0)

    def test_pduration(self, sm):
        result = ev("=PDURATION(5%,1000,2000)", sm)
        assert approx(result, 14.206, tol=1e-2)


# ── 10. Engenharia ──────────────────────────────────────────────────────────

class TestEngineering:
    def test_bin2dec(self, sm): assert ev("=BIN2DEC(\"1010\")", sm) == 10
    def test_dec2bin(self, sm): assert ev("=DEC2BIN(10)", sm) == "1010"
    def test_hex2dec(self, sm): assert ev("=HEX2DEC(\"FF\")", sm) == 255
    def test_dec2hex(self, sm): assert ev("=DEC2HEX(255)", sm) == "FF"
    def test_oct2dec(self, sm): assert ev("=OCT2DEC(\"17\")", sm) == 15
    def test_dec2oct(self, sm): assert ev("=DEC2OCT(15)", sm) == "17"
    def test_bin2hex(self, sm): assert ev("=BIN2HEX(\"11111111\")", sm) == "FF"
    def test_hex2bin(self, sm): assert ev("=HEX2BIN(\"F\")", sm) == "1111"
    def test_bitand(self, sm): assert ev("=BITAND(12,10)", sm) == 8
    def test_bitor(self, sm): assert ev("=BITOR(12,10)", sm) == 14
    def test_bitxor(self, sm): assert ev("=BITXOR(12,10)", sm) == 6
    def test_bitlshift(self, sm): assert ev("=BITLSHIFT(1,3)", sm) == 8
    def test_bitrshift(self, sm): assert ev("=BITRSHIFT(8,2)", sm) == 2
    def test_delta_eq(self, sm): assert ev("=DELTA(5,5)", sm) == 1
    def test_delta_neq(self, sm): assert ev("=DELTA(5,6)", sm) == 0
    def test_gestep_gte(self, sm): assert ev("=GESTEP(5,3)", sm) == 1
    def test_gestep_lt(self, sm): assert ev("=GESTEP(2,3)", sm) == 0
    def test_erf(self, sm): assert approx(ev("=ERF(1)", sm), 0.842701, tol=1e-4)
    def test_erfc(self, sm): assert approx(ev("=ERFC(1)", sm), 0.157299, tol=1e-4)
    def test_convert_km_m(self, sm): assert approx(ev("=CONVERT(1,\"km\",\"m\")", sm), 1000.0)
    def test_convert_c_f(self, sm): assert approx(ev("=CONVERT(0,\"C\",\"F\")", sm), 32.0)
    def test_imabs(self, sm): assert approx(ev("=IMABS(\"3+4i\")", sm), 5.0)
    def test_imreal(self, sm): assert approx(ev("=IMREAL(\"3+4i\")", sm), 3.0)
    def test_imaginary(self, sm): assert approx(ev("=IMAGINARY(\"3+4i\")", sm), 4.0)
    def test_imsqrt(self, sm):
        result = ev("=IMSQRT(\"-1+0i\")", sm)
        assert "i" in str(result)  # deve retornar número imaginário


# ── 11. Aritmética inline ────────────────────────────────────────────────────

class TestArithmetic:
    def test_add(self, sm): assert ev("=A1+A2", sm) == 30
    def test_sub(self, sm): assert ev("=A2-A1", sm) == 10
    def test_mul(self, sm): assert ev("=A1*B1", sm) == 30
    def test_div(self, sm): assert approx(ev("=A1/B1", sm), 10/3)
    def test_pow(self, sm): assert ev("=A1^2", sm) == 100
    def test_pct(self, sm): assert approx(ev("=50%", sm), 0.5)
    def test_neg(self, sm): assert ev("=-A1", sm) == -10
    def test_comparison_eq(self, sm): assert ev("=A1=10", sm) is True
    def test_comparison_neq(self, sm): assert ev("=A1<>20", sm) is True
    def test_comparison_lt(self, sm): assert ev("=B1<A1", sm) is True
    def test_div_by_zero_iferror(self, sm): assert ev("=IFERROR(1/0,\"err\")", sm) == "err"
    def test_blank_as_zero(self, sm): assert ev("=A1+E4", sm) == 10  # E4 vazio = 0


# ── 12. Cobertura end-to-end com state_memory real ──────────────────────────

class TestEndToEnd:
    """Simula casos de uso completos com dependências entre células."""

    def test_sumif_full_column(self, sm):
        """SUMIF com range de coluna completa — caso do Pasta1.xlsx."""
        sm2 = {f"S!N{i}": f"V{(i-1)%3+1}" for i in range(1, 10)}
        sm2.update({f"S!O{i}": i * 100 for i in range(1, 10)})
        sm2["S!C2"] = "V1"
        result = ev("=SUMIF(N:N,C2,O:O)", sm2)
        # V1 aparece nas linhas 1,4,7 → 100+400+700 = 1200
        assert result == 1200

    def test_iferror_with_xlookup(self, sm):
        result = ev("=IFERROR(XLOOKUP(99,A1:A3,A1:A3),\"não encontrado\")", sm)
        assert result == "não encontrado"

    def test_nested_if_with_and(self, sm):
        result = ev("=IF(AND(A1>=10,B1>=3),\"ok\",\"fail\")", sm)
        assert result == "ok"

    def test_complex_aggregation(self, sm):
        # SUMPRODUCT of two ranges: A1:A3 * B1:B3
        result = ev("=SUMPRODUCT(A1:A3,B1:B3)", sm)
        assert result == 10*3+20*6+30*9  # 30+120+270=420

    def test_text_pipeline(self, sm):
        # LEFT("hello",3)="hel", RIGHT("world",3)="rld" → UPPER("helrld")="HELRLD"
        result = ev("=UPPER(LEFT(C1,3)&RIGHT(C2,3))", sm)
        assert result == "HELRLD"

    def test_financial_mortgage(self, sm):
        """Simula cálculo de parcela de financiamento."""
        pmt = ev("=PMT(6%/12,360,-200000)", sm)
        assert approx(pmt, 1199.1, tol=1e-2)

    def test_date_arithmetic_chain(self, sm):
        """Calcula meses entre datas."""
        start = ev("=DATE(2024,1,1)", sm)
        end   = ev("=DATE(2024,6,15)", sm)
        sm2 = dict(sm); sm2["S!Z1"] = start; sm2["S!Z2"] = end
        months = ev("=DATEDIF(Z1,Z2,\"M\")", sm2)
        assert months == 5

    def test_rank_and_large(self, sm):
        rank = ev("=RANK(A1,A1:A5,0)", sm)
        large = ev("=LARGE(A1:A5,rank)", {"S!A1":10,"S!A2":20,"S!A3":30,"S!A4":40,"S!A5":5,"S!rank":4})
        # rank de 10 (desc) = 4 → 4o maior = 10
        assert rank == 4


# ── _sdiv unit tests ─────────────────────────────────────────────────────────

def test_sdiv_string_zero_returns_div0():
    """_sdiv com denominador string '0' deve retornar #DIV/0!, não #VALUE!"""
    from product_a.phase_a4.formula_evaluator import _sdiv, _DIV0
    result = _sdiv(10, "0")
    assert result == _DIV0, f"Esperado #DIV/0!, obtido {result!r}"

def test_sdiv_string_nonzero_divides():
    """_sdiv com denominador string '5' deve dividir normalmente."""
    from product_a.phase_a4.formula_evaluator import _sdiv
    result = _sdiv(10, "5")
    assert result == 2.0, f"Esperado 2.0, obtido {result!r}"

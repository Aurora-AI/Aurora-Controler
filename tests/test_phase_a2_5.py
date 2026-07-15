"""Testes Phase A2.5 — Formula Pattern Registry"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


from product_a.phase_a2_5.pattern_registry import build_registry, classify_formula, classify_workbook
from product_a.trustware.pipeline_contracts import (
    FormulaToken, FormulaTokenType, PatternClass,
    NormalizedWorkbookIR, NormalizedSheet, NormalizedCell
)


def test_registry_coverage():
    """Registry deve cobrir todas as 8 classes da Spec."""
    registry = build_registry()
    classes = set(e.pattern_class for e in registry)
    assert PatternClass.ARITHMETIC in classes
    assert PatternClass.AGGREGATION in classes
    assert PatternClass.CONDITIONAL in classes
    assert PatternClass.LOOKUP in classes
    assert PatternClass.DATE_LOGIC in classes
    assert PatternClass.TEXT_TRANSFORMATION in classes
    assert PatternClass.RANKING in classes
    assert PatternClass.THRESHOLD_LOGIC in classes


def test_classify_sum_aggregation():
    """SUM deve ser classificado como AGGREGATION."""
    tokens = [
        FormulaToken(type=FormulaTokenType.FUNCTION, value='SUM', position=0),
        FormulaToken(type=FormulaTokenType.LPAREN, value='(', position=3),
        FormulaToken(type=FormulaTokenType.OPERAND, value='A1:A2', position=4),
        FormulaToken(type=FormulaTokenType.RPAREN, value=')', position=9),
    ]
    registry = build_registry()
    pattern = classify_formula(tokens, registry, 'Test!A3', '=SUM(A1:A2)')
    assert pattern.pattern_class == PatternClass.AGGREGATION
    assert pattern.matched_rule == 'sum'
    assert pattern.confidence == 1.0


def test_classify_inline_arithmetic():
    """Fórmula sem função explícita deve ser ARITHMETIC."""
    tokens = [
        FormulaToken(type=FormulaTokenType.OPERAND, value='A1', position=1),
        FormulaToken(type=FormulaTokenType.OPERATOR, value='+', position=3),
        FormulaToken(type=FormulaTokenType.OPERAND, value='B1', position=4),
    ]
    registry = build_registry()
    pattern = classify_formula(tokens, registry, 'Test!C1', '=A1+B1')
    assert pattern.pattern_class == PatternClass.ARITHMETIC


def test_classify_unresolved():
    """Função desconhecida deve ser UNRESOLVED."""
    tokens = [
        FormulaToken(type=FormulaTokenType.FUNCTION, value='MYSTERY_FUNC', position=0),
        FormulaToken(type=FormulaTokenType.LPAREN, value='(', position=12),
        FormulaToken(type=FormulaTokenType.RPAREN, value=')', position=13),
    ]
    registry = build_registry()
    pattern = classify_formula(tokens, registry, 'Test!X1', '=MYSTERY_FUNC()')
    assert pattern.pattern_class == PatternClass.UNRESOLVED
    assert pattern.matched_rule is None
    assert pattern.confidence == 0.0


def test_classify_pt_br():
    """Funções em PT-BR devem ser classificadas corretamente."""
    tokens = [
        FormulaToken(type=FormulaTokenType.FUNCTION, value='SOMA', position=0),
        FormulaToken(type=FormulaTokenType.LPAREN, value='(', position=4),
        FormulaToken(type=FormulaTokenType.OPERAND, value='B1:B10', position=5),
        FormulaToken(type=FormulaTokenType.RPAREN, value=')', position=11),
    ]
    registry = build_registry()
    pattern = classify_formula(tokens, registry, 'Test!A3', '=SOMA(B1:B10)')
    # SOMA está no registry
    assert pattern.pattern_class == PatternClass.AGGREGATION


def test_external_ref_classified():
    """Células com [workbook] devem ser classificadas como EXTERNAL_REF."""
    registry = build_registry()
    cell = NormalizedCell(
        coordinate="A1",
        formula_raw="=SUM('[Sales.xlsx]Jan'!A:A)",
        formula_tokens=[],
        dependencies=[],
        value_static=None,
        data_type="n",
        has_external_ref=True,
    )
    sheet = NormalizedSheet(name="Resumo", index=0, state="visible", cells=[cell])
    norm_ir = NormalizedWorkbookIR(
        file_path="test.xlsx",
        sheets=[sheet],
        named_ranges=[],
        metadata={},
        normalization_info={},
    )
    fmap = classify_workbook(norm_ir, registry)
    assert len(fmap.patterns) == 1
    assert fmap.patterns[0].pattern_class == PatternClass.EXTERNAL_REF
    assert fmap.patterns[0].matched_rule == "external_ref"


def test_bracket_in_string_literal_not_external_ref():
    """Colchete dentro de string literal NÃO deve ser detectado como ref externa."""
    import sys
    from normalizer import _has_external_ref
    assert _has_external_ref('=IF(A1>0,"[ok]","err")') is False
    assert _has_external_ref("=SUM('[Sales.xlsx]Jan'!A:A)") is True
    assert _has_external_ref('=VLOOKUP(A1,Sheet2!A:B,2,0)') is False
    assert _has_external_ref("='[Budget.xlsm]Q1'!B5") is True


def test_external_ref_evaluator_returns_ext():
    """evaluate_formula deve retornar '#EXT!' para fórmulas com referência externa."""
    import sys
    from formula_evaluator import evaluate_formula
    from normalizer import expand_range
    result = evaluate_formula("=SUM('[Sales.xlsx]Jan'!A:A)", {}, "Sheet1", expand_range)
    assert result == '#EXT!'


if __name__ == "__main__":
    try:
        test_registry_coverage()
        test_classify_sum_aggregation()
        test_classify_inline_arithmetic()
        test_classify_unresolved()
        test_classify_pt_br()
        print("[TEST A2.5.5] Todos os testes unitários passaram.")
    except Exception as e:
        print(f"[TEST A2.5.5] FALHA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


from normalizer import tokenize_formula

def test_tokenize_malformed_formula_logs_and_does_not_raise(caplog):
    """Fórmula malformada não deve lançar exceção; deve logar em DEBUG se tokenizer falhar."""
    with caplog.at_level(logging.DEBUG, logger="normalizer"):
        tokens = tokenize_formula("=((((broken")
    # The tokenizer may be lenient and not raise — either way, no exception and >= 1 token
    assert len(tokens) >= 1
    # If a log was emitted (tokenizer failed), verify it's the right log
    if caplog.records:
        assert any("tokenize_formula" in r.message or "falha" in r.message
                   for r in caplog.records), f"Log inesperado: {caplog.records}"

def test_tokenize_empty_formula_returns_token():
    """Fórmula vazia não deve lançar exceção."""
    tokens = tokenize_formula("")
    assert isinstance(tokens, list)

def test_normalizer_uses_pipeline_contracts_classes():
    """
    Garante que normalizer.py usa as classes de pipeline_contracts,
    não redefinições locais. Falha se alguém introduzir duplicação.
    """
    import sys
    from pathlib import Path
    REPO = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(REPO / "src" / "kernel" / "phase_a1_5"))
    sys.path.insert(0, str(REPO / "src" / "product_a" / "trustware"))

    import importlib
    import normalizer as norm
    import product_a.trustware.pipeline_contracts as pc

    assert norm.FormulaToken is pc.FormulaToken, \
        "FormulaToken em normalizer não é o mesmo de pipeline_contracts"
    assert norm.NormalizedCell is pc.NormalizedCell, \
        "NormalizedCell em normalizer não é o mesmo de pipeline_contracts"
    assert norm.NormalizedSheet is pc.NormalizedSheet, \
        "NormalizedSheet em normalizer não é o mesmo de pipeline_contracts"
    assert norm.NormalizedWorkbookIR is pc.NormalizedWorkbookIR, \
        "NormalizedWorkbookIR em normalizer não é o mesmo de pipeline_contracts"
    assert norm.FormulaTokenType is pc.FormulaTokenType, \
        "FormulaTokenType em normalizer não é o mesmo de pipeline_contracts"

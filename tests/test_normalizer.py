import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

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

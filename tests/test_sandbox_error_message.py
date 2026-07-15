"""Verifica que a mensagem de Docker indisponível é acionável (não só um sentinela técnico)."""
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from product_a.phase_a4.runner import execute_in_sandbox


def test_docker_unavailable_message_is_actionable():
    with patch("product_a.phase_a4.runner._docker_available", return_value=False):
        result = execute_in_sandbox("def f(): return 1", "f", {})
    assert "docker.com" in result.lower() or "docker desktop" in result.lower()

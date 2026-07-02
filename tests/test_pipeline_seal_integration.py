"""
ME-5 (OS-EXRS-CRYPTO-SEAL) — Gate de integração no caminho de produção.

Cobre o achado do QA independente: uma falha inesperada na selagem (não apenas chave
ausente) não pode crashar o job nem produzir um selo forjado.
"""
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (
    REPO_ROOT / "libs" / "trustware", REPO_ROOT / "src" / "orchestrator",
    REPO_ROOT / "src" / "phase_a0", REPO_ROOT / "src" / "phase_a1",
    REPO_ROOT / "src" / "phase_a1_5", REPO_ROOT / "src" / "phase_a2",
    REPO_ROOT / "src" / "phase_a2_5", REPO_ROOT / "src" / "phase_a3",
    REPO_ROOT / "src" / "phase_a4",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_unexpected_sealing_error_does_not_crash_job(tmp_path, monkeypatch):
    """seal_module levanta erro genérico (não SigningKeyUnavailable) → job completa sem selo,
    evento FACTORY_TOOL_UNAVAILABLE gravado, artefato final NÃO tem selo forjado."""
    import pipeline_orchestrator
    from storage_manager import StorageManager

    def _boom(*_a, **_k):
        raise RuntimeError("falha simulada de hardware criptográfico")

    # Chave válida configurada: load_private_key() deve suceder, para que a falha simulada
    # ocorra especificamente dentro de seal_module() (o caminho de exceção genérica).
    key_path = tmp_path / "signing.pem"
    key_path.write_bytes(Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    monkeypatch.setenv("EXRS_SIGNING_KEY_FILE", str(key_path))
    monkeypatch.setattr(pipeline_orchestrator, "seal_module", _boom)
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))

    fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"
    storage = StorageManager("job-unexpected-seal-error", str(tmp_path))
    result = pipeline_orchestrator.orchestrate_pipeline(fixture, storage)

    assert result["status"] in {"PASSED", "PARTIAL", "FAILED"}  # não crashou
    assert result["certified"] is not None
    assert result["certified"].seal is None  # nunca selo forjado

    events = _read_jsonl(tmp_path / "factory_events.jsonl")
    unavailable = [e for e in events if e["event"] == "FACTORY_TOOL_UNAVAILABLE"
                   and e.get("tool") == "signing-key"]
    assert unavailable, "evento FACTORY_TOOL_UNAVAILABLE não foi gravado"
    assert "falha inesperada" in unavailable[0]["detail"]

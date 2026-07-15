"""
ME-4 (OS-EXRS-CRYPTO-SEAL) — Gate adversarial do verificador standalone.

Os 4 casos que a OS exige: íntegro→válido, 1 byte alterado→inválido, assinatura de outra
chave→inválido, selo removido→inválido com mensagem clara.
"""
import json
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "product_a" / "trustware"))

from product_a.trustware.pipeline_contracts import (
    CertifiedModule, DomainModule, MismatchReport, ValidationResult,
)
from sealing import seal_module
from verify_seal import SealInvalid, verify_artifact


def _key(tmp_path: Path) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def _certified() -> CertifiedModule:
    result = ValidationResult(
        node_id="Sheet1!B5", expected_value="100", actual_value="100",
        passed=True, status="OK",
    )
    report = MismatchReport(total_nodes=1, passed=1, failed=0, results=[result])
    domain = DomainModule(file_path="x.xlsx", imports=[], functions=[], generated_at="t")
    return CertifiedModule(
        original_file="x.xlsx", domain_module=domain, validation_report=report,
        certification_status="PASSED", certified_at="2026-06-27T00:00:00Z",
    )


def _write(module: CertifiedModule, tmp_path: Path) -> Path:
    p = tmp_path / "art_a4_certified.json"
    p.write_text(module.model_dump_json(), encoding="utf-8")
    return p


def test_intact_artifact_is_valid(tmp_path):
    sealed = seal_module(_certified(), Ed25519PrivateKey.generate())
    proof = verify_artifact(str(_write(sealed, tmp_path)))
    assert proof["valid"] is True
    assert proof["status"] == "PASSED"


def test_tampered_value_is_invalid(tmp_path):
    sealed = seal_module(_certified(), Ed25519PrivateKey.generate())
    path = _write(sealed, tmp_path)
    # Adultera 1 valor avaliado DEPOIS da selagem, preservando o selo original.
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["validation_report"]["results"][0]["actual_value"] = "101"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SealInvalid, match="digest diverge"):
        verify_artifact(str(path))


def test_signature_from_other_key_is_invalid(tmp_path):
    # Sela com a chave A mas substitui a pubkey por uma chave B independente.
    sealed = seal_module(_certified(), Ed25519PrivateKey.generate())
    other_pub = Ed25519PrivateKey.generate().public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    import base64
    raw = json.loads(sealed.model_dump_json())
    raw["seal"]["public_key"] = base64.b64encode(other_pub).decode("ascii")
    path = tmp_path / "art_a4_certified.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SealInvalid, match="assinatura inválida"):
        verify_artifact(str(path))


def test_missing_seal_is_invalid_with_clear_message(tmp_path):
    unsealed = _certified()  # seal=None
    with pytest.raises(SealInvalid, match="NÃO possui selo"):
        verify_artifact(str(_write(unsealed, tmp_path)))


def test_forged_but_self_consistent_artifact_rejected_by_pubkey_pin(tmp_path):
    """Achado do QA final: um atacante SEM a chave do EXRS pode forjar um artefato inteiro
    (conteúdo falso + chave própria + assinatura própria) que é internamente consistente —
    digest e assinatura batem entre si. Isso passa SEM --expected-pubkey (é o comportamento
    documentado: só prova integridade interna). Mas COM --expected-pubkey pinado na chave
    legítima do EXRS, deve ser rejeitado, porque a public_key do selo forjado é outra."""
    legit_key = Ed25519PrivateKey.generate()
    legit_pubkey_b64 = seal_module(_certified(), legit_key).seal.public_key

    # Atacante: conteúdo adulterado, selado do zero com SUA PRÓPRIA chave (não a do EXRS).
    attacker_key = Ed25519PrivateKey.generate()
    forged = _certified().model_copy(update={"certification_status": "PASSED"})
    forged_sealed = seal_module(forged, attacker_key)
    path = _write(forged_sealed, tmp_path)

    # Sem pin: internamente consistente → válido (mas pubkey_pinned=False, ver teste abaixo).
    proof = verify_artifact(str(path))
    assert proof["valid"] is True
    assert proof["pubkey_pinned"] is False

    # Com pin na chave legítima do EXRS: deve rejeitar, pois a public_key do selo é do atacante.
    with pytest.raises(SealInvalid, match="NÃO confere com a chave esperada"):
        verify_artifact(str(path), expected_pubkey=legit_pubkey_b64)


def test_matching_expected_pubkey_still_validates(tmp_path):
    """Selo legítimo + --expected-pubkey correta → válido, com pubkey_pinned=True."""
    key = Ed25519PrivateKey.generate()
    sealed = seal_module(_certified(), key)
    path = _write(sealed, tmp_path)
    proof = verify_artifact(str(path), expected_pubkey=sealed.seal.public_key)
    assert proof["valid"] is True
    assert proof["pubkey_pinned"] is True


def test_malformed_seal_schema_is_invalid_not_a_raw_traceback(tmp_path):
    """Achado do QA independente: campo obrigatório do selo ausente deve virar SealInvalid
    com mensagem legível — nunca um ValidationError/traceback cru vazado ao chamador."""
    sealed = seal_module(_certified(), Ed25519PrivateKey.generate())
    raw = json.loads(sealed.model_dump_json())
    del raw["seal"]["signature"]  # campo obrigatório de CertificationSeal ausente
    path = tmp_path / "art_a4_certified.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SealInvalid, match="schema esperado"):
        verify_artifact(str(path))


def test_verifier_does_not_import_pipeline():
    """Garante o requisito de isolamento: o verificador não puxa o orquestrador/fases."""
    import verify_seal
    src = Path(verify_seal.__file__).read_text(encoding="utf-8")
    assert "pipeline_orchestrator" not in src
    assert "phase_a" not in src

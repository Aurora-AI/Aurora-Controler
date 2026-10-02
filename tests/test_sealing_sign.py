"""
ME-3 (OS-EXRS-CRYPTO-SEAL) — Gate de assinatura Ed25519 + selagem.
"""
import base64
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)



from libs.trustware.pipeline_contracts import (
    CertifiedModule, DomainModule, MismatchReport, ValidationResult,
)
from libs.trustware.sealing import (
    SigningKeyUnavailable, canonical_digest, load_private_key, seal_module,
)


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


def _write_key(tmp_path: Path) -> Path:
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    p = tmp_path / "signing.pem"
    p.write_bytes(pem)
    return p


def test_seal_module_fills_seal_and_does_not_mutate_original(tmp_path):
    key = load_private_key(str(_write_key(tmp_path)))
    base = _certified()
    sealed = seal_module(base, key)
    assert base.seal is None              # original intacto
    assert sealed.seal is not None
    assert sealed.seal.algorithm == "Ed25519"
    assert sealed.seal.digest_sha256 == canonical_digest(base)
    assert sealed.seal.sealed_at != ""


def test_signature_verifies_with_embedded_public_key(tmp_path):
    key = load_private_key(str(_write_key(tmp_path)))
    sealed = seal_module(_certified(), key)
    pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(sealed.seal.public_key))
    sig = base64.b64decode(sealed.seal.signature)
    # Não levanta → assinatura válida sobre os bytes do digest hex.
    pub.verify(sig, sealed.seal.digest_sha256.encode("ascii"))


def test_signature_fails_for_tampered_digest(tmp_path):
    key = load_private_key(str(_write_key(tmp_path)))
    sealed = seal_module(_certified(), key)
    pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(sealed.seal.public_key))
    sig = base64.b64decode(sealed.seal.signature)
    with pytest.raises(Exception):
        pub.verify(sig, b"0" * 64)  # digest diferente → assinatura inválida


def test_load_private_key_missing_env_raises(monkeypatch):
    monkeypatch.delenv("EXRS_SIGNING_KEY_FILE", raising=False)  # trava a branch "env não definido"
    with pytest.raises(SigningKeyUnavailable):
        load_private_key(None)  # sem env e sem path


def test_load_private_key_nonexistent_file_raises():
    with pytest.raises(SigningKeyUnavailable):
        load_private_key("C:/nao/existe/chave.pem")

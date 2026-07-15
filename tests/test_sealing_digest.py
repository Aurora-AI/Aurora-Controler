"""
ME-2 (OS-EXRS-CRYPTO-SEAL) — Gate de determinismo do digest canônico.

Garante a propriedade da qual depende a prova inteira: o digest é reproduzível e sensível.
"""
import sys
from pathlib import Path



from product_a.trustware.pipeline_contracts import (
    CertifiedModule, DomainModule, MismatchReport, ValidationResult,
)
from sealing import canonical_digest


def _certified(actual_value="100", expected_value="100") -> CertifiedModule:
    result = ValidationResult(
        node_id="Sheet1!B5",
        expected_value=expected_value,
        actual_value=actual_value,
        passed=str(actual_value) == str(expected_value),
        status="OK",
    )
    report = MismatchReport(total_nodes=1, passed=1, failed=0, results=[result])
    domain = DomainModule(file_path="x.xlsx", imports=[], functions=[], generated_at="t")
    return CertifiedModule(
        original_file="x.xlsx",
        domain_module=domain,
        validation_report=report,
        certification_status="PASSED",
        certified_at="2026-06-27T00:00:00Z",
    )


def test_digest_is_deterministic_across_iterations():
    """Mesmo módulo → mesmo digest em 1000 reconstruções independentes."""
    digests = {canonical_digest(_certified()) for _ in range(1000)}
    assert len(digests) == 1


def test_digest_ignores_seal_field():
    """Preencher `seal` não muda o digest — o selo não cobre a si mesmo."""
    from product_a.trustware.pipeline_contracts import CertificationSeal

    base = _certified()
    sealed = base.model_copy(update={"seal": CertificationSeal(
        digest_sha256="deadbeef", signature="x", public_key="y", sealed_at="t",
    )})
    assert canonical_digest(base) == canonical_digest(sealed)


def test_digest_changes_when_actual_value_changes():
    """Alterar 1 valor avaliado muda o digest (sensibilidade à adulteração)."""
    a = canonical_digest(_certified(actual_value="100"))
    b = canonical_digest(_certified(actual_value="101"))
    assert a != b


def test_digest_is_hex_sha256():
    d = canonical_digest(_certified())
    assert len(d) == 64
    int(d, 16)  # levanta se não for hex

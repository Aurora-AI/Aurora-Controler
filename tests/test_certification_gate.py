import sys
from pathlib import Path

import pytest



from product_a.trustware.pipeline_contracts import (
    CertifiedModule, DomainModule, MismatchReport, ValidationResult,
)
from certification_gate import verify_certification, CertificationGateError


def _domain() -> DomainModule:
    return DomainModule(file_path="x.xlsx", imports=[], functions=[], generated_at="t")


def _certified(status: str, results: list[ValidationResult]) -> CertifiedModule:
    report = MismatchReport(
        total_nodes=len(results),
        passed=len([r for r in results if r.passed]),
        failed=len([r for r in results if not r.passed]),
        results=results,
    )
    return CertifiedModule(
        original_file="x.xlsx",
        domain_module=_domain(),
        validation_report=report,
        certification_status=status,
    )


def test_gate_accepts_honest_passed():
    results = [ValidationResult(node_id="S!A1", actual_value=10, expected_value=10,
                                passed=True, status="PASSED")]
    verify_certification(_certified("PASSED", results))  # não levanta


def test_gate_accepts_honest_failed():
    results = [ValidationResult(node_id="S!A1", actual_value=9, expected_value=10,
                                passed=False, status="FAILED")]
    verify_certification(_certified("FAILED", results))  # FAILED honesto é íntegro


def test_gate_rejects_tampered_passed_over_failures():
    """Selo PASSED com nó falho — o caso de fraude que o gate existe para barrar."""
    results = [
        ValidationResult(node_id="S!A1", actual_value=10, expected_value=10, passed=True, status="PASSED"),
        ValidationResult(node_id="S!A2", actual_value=9, expected_value=10, passed=False, status="FAILED"),
    ]
    with pytest.raises(CertificationGateError):
        verify_certification(_certified("PASSED", results))


def test_gate_rejects_status_inconsistent_with_parity():
    """Paridade real é 0.5 → status não pode ser PASSED."""
    results = [
        ValidationResult(node_id="S!A1", passed=True, status="PASSED"),
        ValidationResult(node_id="S!A2", passed=False, status="FAILED"),
    ]
    with pytest.raises(CertificationGateError):
        verify_certification(_certified("PASSED", results))


def test_gate_rejects_passed_node_with_error_sentinel():
    """Nó passed=True não pode carregar sentinela de erro no actual_value."""
    results = [ValidationResult(node_id="S!A1", actual_value="RUNTIME_ERROR: boom",
                                expected_value="RUNTIME_ERROR: boom", passed=True, status="PASSED")]
    with pytest.raises(CertificationGateError):
        verify_certification(_certified("PASSED", results))


def test_gate_rejects_byzantine_passed_flag_against_values():
    """passed=True mas expected != actual (valores limpos) — o gap Byzantino, agora fechado."""
    results = [ValidationResult(node_id="S!A1", actual_value=1, expected_value=999,
                                passed=True, status="PASSED")]
    with pytest.raises(CertificationGateError):
        verify_certification(_certified("PASSED", results))


def test_gate_detects_error_sentinel_in_nested_value():
    """Sentinela de erro embutida em dict/list (não só str escalar) é detectada."""
    results = [ValidationResult(node_id="S!A1", actual_value={"v": "#ERROR! (Boom)"},
                                expected_value={"v": "#ERROR! (Boom)"}, passed=True, status="PASSED")]
    with pytest.raises(CertificationGateError):
        verify_certification(_certified("PASSED", results))


def test_gate_ignores_skipped_no_cache_in_parity():
    """Nós sem cache não contam para paridade; PASSED permanece válido."""
    results = [
        ValidationResult(node_id="S!A1", actual_value=10, expected_value=10, passed=True, status="PASSED"),
        ValidationResult(node_id="S!A2", passed=False, status="SKIPPED_NO_CACHE"),
    ]
    verify_certification(_certified("PASSED", results))  # não levanta

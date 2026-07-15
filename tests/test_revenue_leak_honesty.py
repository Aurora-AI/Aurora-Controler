"""
Testes de regressão do motor honesto — Fix 2 (piso de materialidade).

Trava contra os dois falsos positivos expostos pela fixture de ótica: SKUs esparsos
(< 1% da receita) não devem mais aparecer em revenue_leaks, e o sinal real (AG-12) deve
continuar detectado.
"""
from pathlib import Path

from product_b.oracle.commercial_auditor import run_audit

FIXTURE = Path(__file__).parent / "fixtures" / "otica_test_bom.xlsx"

_SPARSE_SKUS = {"ARM-059", "LEN-071", "LEN-074", "LEN-076", "LEN-083", "LEN-118"}


def test_materiality_floor_suppresses_sparse_skus():
    report = run_audit(FIXTURE)
    flagged_products = {
        leak.entity_id for leak in report.revenue_leaks if leak.scope == "product"
    }
    assert not flagged_products & _SPARSE_SKUS


def test_materiality_floor_preserves_real_signal():
    report = run_audit(FIXTURE)
    ag12_leaks = [
        leak for leak in report.revenue_leaks
        if leak.scope == "product" and leak.entity_id == "AG-12"
    ]
    assert any(
        leak.period == "2024-05" and leak.severity == "high" and not leak.low_confidence
        for leak in ag12_leaks
    )


def test_yoy_residual_suppresses_regular_seasonality():
    report = run_audit(FIXTURE)
    solar_march_leaks = [
        leak for leak in report.revenue_leaks
        if leak.scope == "product" and leak.entity_id == "SOLAR-SEASONAL"
        and leak.period in ("2024-03", "2025-03", "2026-03")
    ]
    assert not solar_march_leaks

# -*- coding: utf-8 -*-
"""
Testes de regressão — Fase E, E2: Conflito de Comissionamento.

Não recalcula margem — anota achados de SellerMarginMixProfile/
SellerMarginCorrosionAlert já existentes. Construídos diretamente (Pydantic puro),
sem passar pelos detectores de origem — o que importa aqui é a lógica de anotação
e a dependência de ordem (consumir a lista JÁ pós-taint).
"""
from product_b.oracle.commercial_auditor import detect_incentive_misalignment
from product_b.oracle.forensic_contracts import (
    AuditThresholdsConfig, SellerMarginCorrosionAlert, SellerMarginMixProfile,
)


def _mix(salesperson="V-01", store="L1", destructive=True, gap=20.0):
    return SellerMarginMixProfile(
        salesperson=salesperson, store=store, total_revenue=10000.0,
        seller_margin_pct=20.0, store_margin_pct=20.0 + gap, margin_gap_pp=gap,
        is_margin_destructive=destructive, sample_size=50,
    )


def _corrosion(salesperson="V-02", store="L1", corrosive=True, tainted=False):
    return SellerMarginCorrosionAlert(
        salesperson=salesperson, store=store, total_revenue=10000.0, total_discount=500.0,
        discount_pct=5.0, store_mean_discount_pct=2.0, store_std_discount_pct=1.0,
        sample_size=50, is_corrosive=corrosive, tainted_by_triage=tainted,
    )


def test_commission_basis_unknown_nao_avalia_nada():
    thresholds = AuditThresholdsConfig()  # default "unknown"
    alerts = detect_incentive_misalignment([_mix()], [_corrosion()], thresholds)
    assert alerts == []


def test_commission_basis_mixed_nao_gera_alerta():
    thresholds = AuditThresholdsConfig(commission_basis="mixed")
    alerts = detect_incentive_misalignment([_mix()], [_corrosion()], thresholds)
    assert alerts == []


def test_commission_basis_contribution_margin_nao_gera_alerta():
    thresholds = AuditThresholdsConfig(commission_basis="contribution_margin")
    alerts = detect_incentive_misalignment([_mix()], [_corrosion()], thresholds)
    assert alerts == []


def test_gross_revenue_com_margin_destructive_gera_alerta():
    thresholds = AuditThresholdsConfig(commission_basis="gross_revenue")
    alerts = detect_incentive_misalignment([_mix(destructive=True, gap=15.0)], [], thresholds)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.linked_finding_type == "margin_mix"
    assert a.salesperson == "V-01" and a.store == "L1"
    assert "15.0pp" in a.linked_finding_summary
    assert a.recommended_fix  # string fixa, não vazia


def test_gross_revenue_com_corrosao_gera_alerta():
    thresholds = AuditThresholdsConfig(commission_basis="gross_revenue")
    alerts = detect_incentive_misalignment([], [_corrosion(corrosive=True)], thresholds)
    assert len(alerts) == 1
    assert alerts[0].linked_finding_type == "margin_corrosion"
    assert alerts[0].salesperson == "V-02"


def test_gross_revenue_sem_achado_destrutivo_nao_gera_alerta():
    thresholds = AuditThresholdsConfig(commission_basis="gross_revenue")
    alerts = detect_incentive_misalignment(
        [_mix(destructive=False)], [_corrosion(corrosive=False)], thresholds,
    )
    assert alerts == []


def test_vendedor_absolvido_por_taint_nao_gera_alerta():
    # QA/Spec (achado de revisão): esta função só LÊ is_corrosive — o teste trava
    # que a função respeita is_corrosive=False mesmo que tainted_by_triage=True
    # esteja setado (simula exatamente o estado PÓS-taint que run_audit precisa
    # produzir antes de chamar esta função).
    thresholds = AuditThresholdsConfig(commission_basis="gross_revenue")
    absolvido = _corrosion(salesperson="V-03", corrosive=False, tainted=True)
    alerts = detect_incentive_misalignment([], [absolvido], thresholds)
    assert alerts == []


def test_ambos_achados_simultaneos_geram_dois_alertas_independentes():
    thresholds = AuditThresholdsConfig(commission_basis="gross_revenue")
    alerts = detect_incentive_misalignment(
        [_mix(salesperson="V-01", destructive=True)],
        [_corrosion(salesperson="V-01", corrosive=True)],
        thresholds,
    )
    assert len(alerts) == 2
    assert {a.linked_finding_type for a in alerts} == {"margin_mix", "margin_corrosion"}

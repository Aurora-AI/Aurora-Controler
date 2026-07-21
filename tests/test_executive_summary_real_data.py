"""
Testes de FORMA sobre dado real (consultoria_real_test.xlsx) para
build_executive_summary — nenhum valor cravado, tudo recalculado a partir do próprio
relatório. Este arquivo é o passo de verificação independente exigido antes de
regenerar tests/fixtures/golden_laudo_v3.json (ver
docs/superpowers/specs/2026-07-17-laudo-executive-summary-e-frontend-drilldown-design.md,
seção 7.1) — se algum teste aqui falhar, NÃO regenere o golden master; há um bug em
build_executive_summary para corrigir primeiro.
"""
from pathlib import Path

from product_b.oracle.commercial_auditor import run_audit

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


def test_executive_summary_totals_recompute_from_the_report_itself():
    report = run_audit(FIXTURE)
    summary = report.executive_summary

    # C3: alerta promocional (forma_pagto=promocao) fica fora do prejuízo estrutural
    expected_operational_loss = sum(
        abs(a.contribution_margin)
        for a in report.contribution_margin_alerts if not a.promotional
    )
    assert abs(summary.total_operational_loss - expected_operational_loss) < 0.01

    expected_capital_frozen = (
        report.dead_stock[0].capital_frozen if report.dead_stock else 0.0
    )
    assert summary.total_capital_frozen == expected_capital_frozen

    expected_ltv_risk = sum(c.historical_annual_value for c in report.churn_findings)
    assert abs(summary.total_ltv_risk - expected_ltv_risk) < 0.01


def test_executive_summary_natures_are_never_summed_together():
    """Guarda simples contra double-count/merge acidental entre naturezas: nenhum
    total é igual à soma dos outros dois."""
    report = run_audit(FIXTURE)
    summary = report.executive_summary
    assert summary.total_operational_loss != (
        summary.total_capital_frozen + summary.total_ltv_risk
    )


def test_discarded_alarms_only_uses_categories_the_engine_actually_checks():
    report = run_audit(FIXTURE)
    categories = {a.category for a in report.executive_summary.discarded_alarms}
    # Fase E, E2 — commission_basis_unknown sempre aparece com o threshold default
    # ("unknown"), somado às duas categorias pré-existentes.
    assert categories <= {"salesperson_ramp", "store_cold_start", "commission_basis_unknown"}


def test_action_plan_is_sorted_by_tier_then_impact_descending():
    report = run_audit(FIXTURE)
    plan = report.executive_summary.action_plan
    tiers = [item.tier for item in plan]
    assert tiers == sorted(tiers)
    for tier in set(tiers):
        impacts = [item.impact_brl for item in plan if item.tier == tier]
        assert impacts == sorted(impacts, reverse=True)


def test_action_plan_never_contains_a_latent_or_scenario_nature():
    report = run_audit(FIXTURE)
    natures = {item.nature for item in report.executive_summary.action_plan}
    assert "scenario" not in natures
    assert "latent" not in natures
    assert natures <= {"operational", "capital", "ltv_risk"}


def test_at_least_one_real_action_plan_item_exists_for_this_fixture():
    """`consultoria_real_test.xlsx` tem SKUs no vermelho, estoque morto e churn
    conhecidos (ver test_store_macro_pnl.py, test_forensic_contracts.py) — o plano de
    ação não deveria vir vazio para este dataset."""
    report = run_audit(FIXTURE)
    assert report.executive_summary.action_plan

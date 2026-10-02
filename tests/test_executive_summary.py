"""
Testes de src/product_b/oracle/commercial_auditor.py::build_executive_summary.

Aritmética isolada (sintética): constrói os outputs dos detectores diretamente (não
roda o pipeline inteiro) para testar só a agregação, sem depender de nenhuma fixture
real. Os testes de FORMA sobre dado real ficam em test_executive_summary_real_data.py.
"""
import inspect

from product_b.oracle.commercial_auditor import build_executive_summary
from product_b.oracle.forensic_contracts import (
    AuditThresholdsConfig, ChurnFinding, ContributionMarginAlert, DeadStockFinding,
    SalespersonPerformance, StorePerformance,
)


def _thresholds():
    return AuditThresholdsConfig(sev_ramp_min_days=180.0, cold_start_min_months=4.0)


def test_total_operational_loss_sums_absolute_negative_margins():
    alerts = [
        ContributionMarginAlert(
            product="P1", avg_price=50.0, avg_entry_cost=60.0, variable_cost_pct=15.0,
            contribution_margin=-17.5, sample_size=10,
        ),
        ContributionMarginAlert(
            product="P2", avg_price=30.0, avg_entry_cost=35.0, variable_cost_pct=15.0,
            contribution_margin=-9.5, sample_size=4,
        ),
    ]
    summary = build_executive_summary(
        contribution_margin_alerts=alerts, dead_stock=[], churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert abs(summary.total_operational_loss - 27.0) < 1e-6


def test_total_capital_frozen_reads_the_single_dead_stock_finding():
    dead_stock = [DeadStockFinding(
        dead_stock_months=8, sku_count=16, capital_frozen=35040.0,
        total_inventory_value=100000.0, dead_stock_pct=35.04, skus=["SKU-1"],
    )]
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=dead_stock, churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.total_capital_frozen == 35040.0


def test_total_capital_frozen_is_zero_without_dead_stock():
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.total_capital_frozen == 0.0


def test_total_ltv_risk_sums_historical_annual_value():
    churn = [
        ChurnFinding(customer_id="Client_A", purchase_count=18, avg_cadence_days=30.0,
                     last_purchase="2024-06-15", months_silent=6, historical_annual_value=48000.0),
        ChurnFinding(customer_id="Client_B", purchase_count=5, avg_cadence_days=45.0,
                     last_purchase="2024-05-01", months_silent=4, historical_annual_value=12000.0),
    ]
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=churn,
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.total_ltv_risk == 60000.0


def test_total_ltv_risk_floors_each_customer_at_zero_before_summing():
    """Um cliente com valor histórico líquido negativo (estornos pesados) nunca pode
    cancelar o risco real de outro cliente churnado com valor positivo — cada achado é
    avaliado isoladamente. Sem o piso, -500 + 300 = -200 apagaria o item de plano de
    ação inteiro mesmo havendo R$300 de risco real."""
    churn = [
        ChurnFinding(customer_id="Client_A", purchase_count=3, avg_cadence_days=30.0,
                     last_purchase="2024-01-01", months_silent=6, historical_annual_value=-500.0),
        ChurnFinding(customer_id="Client_B", purchase_count=3, avg_cadence_days=30.0,
                     last_purchase="2024-01-01", months_silent=6, historical_annual_value=300.0),
    ]
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=churn,
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.total_ltv_risk == 300.0
    assert any(item.nature == "ltv_risk" for item in summary.action_plan)


def test_discarded_alarms_flags_ramping_salesperson_and_cold_start_store():
    salespeople = [
        SalespersonPerformance(
            salesperson="Vendedor Novo", total_revenue=5000.0, sample_size=8,
            capture_rate_pct=70.0, low_capture_flag=False, days_since_first_sale=60,
            has_sufficient_tenure=False, low_volume_flag=False,
        ),
        SalespersonPerformance(
            salesperson="Vendedor Maduro", total_revenue=50000.0, sample_size=80,
            capture_rate_pct=70.0, low_capture_flag=False, days_since_first_sale=400,
            has_sufficient_tenure=True, low_volume_flag=False,
        ),
    ]
    stores = [
        StorePerformance(
            store="Loja Nova", gross_revenue=1000.0, revenue_sample_size=5,
            avg_price=100.0, avg_entry_cost=50.0, variable_cost_pct=15.0,
            contribution_margin_avg=35.0, contribution_margin_total=175.0,
            margin_sample_size=5, months_of_history=1.5, has_sufficient_history=False,
        ),
        StorePerformance(
            store="Loja Madura", gross_revenue=100000.0, revenue_sample_size=500,
            avg_price=100.0, avg_entry_cost=50.0, variable_cost_pct=15.0,
            contribution_margin_avg=35.0, contribution_margin_total=17500.0,
            margin_sample_size=500, months_of_history=24.0, has_sufficient_history=True,
        ),
    ]
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=[],
        salesperson_performance=salespeople, store_performance=stores,
        thresholds=_thresholds(),
    )
    categories_and_entities = {(a.category, a.entity_id) for a in summary.discarded_alarms}
    assert categories_and_entities == {
        ("salesperson_ramp", "Vendedor Novo"),
        ("store_cold_start", "Loja Nova"),
        # Fase E, E2 — commission_basis default "unknown" sempre gera este alarme
        # (ponto cego honesto), independente de rampa/cold-start.
        ("commission_basis_unknown", "rede"),
    }


def test_action_plan_orders_by_tier_then_impact_descending_within_tier():
    alerts = [ContributionMarginAlert(
        product="P1", avg_price=50.0, avg_entry_cost=60.0, variable_cost_pct=15.0,
        contribution_margin=-10.0, sample_size=5,
    )]  # total_operational_loss = 50.0 -> tier 1
    dead_stock = [DeadStockFinding(
        dead_stock_months=8, sku_count=1, capital_frozen=200.0,
        total_inventory_value=1000.0, dead_stock_pct=20.0, skus=["SKU-1"],
    )]  # total_capital_frozen = 200.0 -> tier 2
    churn = [ChurnFinding(
        customer_id="Client_A", purchase_count=5, avg_cadence_days=30.0,
        last_purchase="2024-01-01", months_silent=6, historical_annual_value=99999.0,
    )]  # total_ltv_risk = 99999.0 -> tier 3 (maior R$ de todos, mas último por natureza)
    summary = build_executive_summary(
        contribution_margin_alerts=alerts, dead_stock=dead_stock, churn_findings=churn,
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert [item.nature for item in summary.action_plan] == ["operational", "capital", "ltv_risk"]
    assert [item.tier for item in summary.action_plan] == [1, 2, 3]


def test_action_plan_omits_items_with_zero_impact():
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.action_plan == []


def test_build_executive_summary_cannot_leak_latent_revenue_into_the_plan():
    """Guarda de regressão: build_executive_summary não recebe latent_revenue como
    parâmetro — impossível vazar receita latente (cenário) para dentro do plano de
    ação como se fosse fato, mesmo por engano futuro."""
    params = inspect.signature(build_executive_summary).parameters
    assert "latent_revenue" not in params


from pathlib import Path

from product_b.oracle.commercial_auditor import run_audit

_FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


def test_run_audit_populates_executive_summary():
    report = run_audit(_FIXTURE)
    assert report.executive_summary is not None
    assert report.executive_summary.total_operational_loss >= 0.0
    assert report.executive_summary.total_capital_frozen >= 0.0
    assert report.executive_summary.total_ltv_risk >= 0.0

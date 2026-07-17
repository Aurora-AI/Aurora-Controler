"""
Testes de src/product_b/oracle/forensic_contracts.py — contratos Pydantic V2 do Data Oracle.

FASE RED (TDD): estes testes devem FALHAR agora (ModuleNotFoundError) — o módulo
ainda não existe. Servem de especificação executável para a engenharia do motor.
"""
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from product_b.oracle.forensic_contracts import (
    ActionPlanItem, AuditThresholdsConfig, ChurnFinding, CleaningSummary, DiscardedAlarm,
    ExecutiveAuditReport, ExecutiveSummary, ProductTrendEntry, RevenueLeakAnomaly, SalesRecord, SeasonalityCurve,
)


def test_thresholds_config_has_documented_defaults():
    """Nenhum detector deve conter número mágico — todos os limiares vêm daqui."""
    t = AuditThresholdsConfig()
    assert t.revenue_drop_sigma == 2.0
    assert t.churn_cadence_multiplier == 2.0
    assert t.churn_min_purchases == 3
    assert t.trend_decoupling_pct == 20.0
    assert t.seasonality_min_months == 12


def test_thresholds_config_is_overridable():
    t = AuditThresholdsConfig(revenue_drop_sigma=3.0, churn_cadence_multiplier=1.5)
    assert t.revenue_drop_sigma == 3.0
    assert t.churn_cadence_multiplier == 1.5


def test_sales_record_requires_rastreability_fields():
    record = SalesRecord(
        date=datetime(2023, 1, 15), product="Cabo HDMI", customer="Cliente Beta SA",
        value=3000.0, quantity=30, source_file="sales_history_test.xlsx", source_row=2,
    )
    assert record.source_file == "sales_history_test.xlsx"
    assert record.source_row == 2


def test_sales_record_quantity_is_optional():
    record = SalesRecord(
        date=datetime(2023, 1, 15), product="Cabo HDMI", customer="Cliente Beta SA",
        value=3000.0, quantity=None, source_file="f.xlsx", source_row=2,
    )
    assert record.quantity is None


def test_cleaning_summary_tracks_discards_by_reason_not_just_a_total():
    summary = CleaningSummary(
        rows_read=100, rows_accepted=95,
        rows_discarded_by_reason={"data_invalida": 3, "valor_nao_numerico": 2},
        files_skipped=[],
    )
    assert summary.rows_discarded_by_reason["data_invalida"] == 3
    assert sum(summary.rows_discarded_by_reason.values()) == 100 - 95


def test_revenue_leak_anomaly_carries_numeric_evidence():
    anomaly = RevenueLeakAnomaly(
        scope="total", entity_id="total", period="2024-08",
        expected_value=18000.0, actual_value=2700.0, drop_sigma=4.2, severity="high",
    )
    assert anomaly.actual_value < anomaly.expected_value
    assert anomaly.drop_sigma > 0


def test_churn_finding_reports_historical_value_lost():
    finding = ChurnFinding(
        customer_id="Client_A", purchase_count=18, avg_cadence_days=30.0,
        last_purchase="2024-06-15", months_silent=6, historical_annual_value=48000.0,
    )
    assert finding.months_silent >= 2  # excede o multiplicador padrão de churn


def test_product_trend_entry_flags_decoupling_with_last_sale_month():
    entry = ProductTrendEntry(
        product="Adaptador USB", company_growth_pct=45.0, product_growth_pct=-80.0,
        decoupled=True, last_sale_month="2024-08",
    )
    assert entry.decoupled is True
    assert entry.last_sale_month == "2024-08"


def test_seasonality_curve_reports_insufficient_data_explicitly():
    curve = SeasonalityCurve(
        scope="total", entity="total", monthly_index=None,
        insufficient_data=True, months_available=8,
    )
    assert curve.insufficient_data is True
    assert curve.monthly_index is None


def test_executive_audit_report_assembles_all_sections():
    report = ExecutiveAuditReport(
        period_start="2023-01", period_end="2024-12",
        cleaning=CleaningSummary(rows_read=258, rows_accepted=258,
                                  rows_discarded_by_reason={}, files_skipped=[]),
        thresholds=AuditThresholdsConfig(),
        revenue_leaks=[], churn_findings=[], product_trends=[], seasonality=[],
        executive_summary=ExecutiveSummary(
            total_operational_loss=0.0, total_capital_frozen=0.0, total_ltv_risk=0.0,
        ),
        generated_at="2026-07-06T00:00:00",
    )
    assert report.period_start == "2023-01"
    assert report.thresholds.revenue_drop_sigma == 2.0
    assert report.executive_summary.total_operational_loss == 0.0


def test_discarded_alarm_carries_category_entity_and_reason():
    alarm = DiscardedAlarm(
        category="salesperson_ramp", entity_id="Vendedor Novo",
        reason="Vendedor em rampa há 60 dias — volume baixo não é penalizado.",
    )
    assert alarm.category == "salesperson_ramp"
    assert alarm.entity_id == "Vendedor Novo"


def test_action_plan_item_carries_tier_for_ordering():
    item = ActionPlanItem(
        id="act-operational", category="margem_produto", title="Estancar Sangria",
        description="...", impact_brl=1000.0, nature="operational", tier=1,
    )
    assert item.tier == 1
    assert item.nature == "operational"


def test_executive_summary_defaults_to_empty_alarms_and_plan():
    summary = ExecutiveSummary(
        total_operational_loss=0.0, total_capital_frozen=0.0, total_ltv_risk=0.0,
    )
    assert summary.discarded_alarms == []
    assert summary.action_plan == []


def test_executive_summary_natures_stay_as_three_separate_fields():
    """Guarda de regressão: os três totais são campos INDEPENDENTES — nenhum é
    calculado como soma dos outros dois (isso seria uma violação da regra de que as
    três naturezas contábeis nunca se somam)."""
    summary = ExecutiveSummary(
        total_operational_loss=100.0, total_capital_frozen=200.0, total_ltv_risk=300.0,
    )
    assert summary.total_operational_loss == 100.0
    assert summary.total_capital_frozen == 200.0
    assert summary.total_ltv_risk == 300.0

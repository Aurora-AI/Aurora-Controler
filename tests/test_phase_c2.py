"""Testes da Fase C2 — Motor de Métricas."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c2",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import KPI, AggregationRow, Aggregation, Anomaly, MetricsReport


def test_kpi_carries_evidence():
    k = KPI(metric="approval_rate", label="Taxa de Aprovação", value=0.2076,
            formula="sum(quantidade where status == 'Aprovado') / sum(quantidade)",
            numerator=769, denominator=3704, validation_status="ok")
    assert k.numerator == 769 and k.denominator == 3704


def test_aggregation_model():
    a = Aggregation(id="status_distribution", by="status", measure="quantidade",
                    rows=[AggregationRow(key="Aprovado", value=769)])
    assert a.rows[0].key == "Aprovado"


def test_metrics_report_roundtrip():
    r = MetricsReport(
        kpis=[KPI(metric="m", label="L", value=1.0, formula="f",
                  numerator=1, denominator=1, validation_status="ok")],
        aggregations=[Aggregation(id="a", by="status", measure="quantidade",
                                  rows=[AggregationRow(key="K", value=2)])],
        anomalies=[Anomaly(type="concentration", severity="high",
                           metric="m", evidence="evidência numérica")],
    )
    assert r.schema_version == "c2_metrics.v1"
    assert MetricsReport.model_validate(r.model_dump()).kpis[0].metric == "m"


# --- Task 11: aggregate ---
from aggregate import aggregate_by

_DATASET = [
    {"row_id": 1, "cnpj": "X1", "status": "Aprovado", "quantidade": 10.0},
    {"row_id": 2, "cnpj": "X1", "status": "Reprovado", "quantidade": 20.0},
    {"row_id": 3, "cnpj": "X2", "status": "Aprovado", "quantidade": 5.0},
]


def test_aggregate_by_status():
    agg = aggregate_by(_DATASET, by="status", measure="quantidade", agg_id="status_distribution")
    rows = {r.key: r.value for r in agg.rows}
    assert rows["Aprovado"] == 15.0
    assert rows["Reprovado"] == 20.0
    assert agg.id == "status_distribution"


def test_aggregate_by_entity():
    agg = aggregate_by(_DATASET, by="cnpj", measure="quantidade", agg_id="cnpj_ranking")
    rows = {r.key: r.value for r in agg.rows}
    assert rows["X1"] == 30.0
    assert rows["X2"] == 5.0

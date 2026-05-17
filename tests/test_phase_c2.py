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


# --- Task 12: metrics ---
from dashboard_contracts import (
    C0Dataset, IngestionStrategy, DetectedStructure, ValidationSummary,
    SemanticModel, SemanticField,
)
from metrics import compute_kpis, detect_anomalies, build_metrics_report


def _c0() -> C0Dataset:
    return C0Dataset(
        source_file="t.csv",
        ingestion_strategy=IngestionStrategy(primary="structured_model",
            fallback="grid_scraping", used="structured_model", reason="flat"),
        detected_structure=DetectedStructure(table_kind="flat"),
        dataset=list(_DATASET), source_map=[], discarded_rows=[],
        validation_summary=ValidationSummary(total_rows_read=3, source_rows_emitted=3,
            source_rows_context=0, source_rows_discarded=0, dataset_rows_emitted=3),
    )


def _c1() -> SemanticModel:
    return SemanticModel(primary_dimension="cnpj", secondary_dimension="status",
        fields=[
            SemanticField(name="cnpj", type="string", semantic_role="entity_id", cardinality=2),
            SemanticField(name="status", type="category", semantic_role="breakdown_dimension",
                          business_role="proposal_status", cardinality=2),
            SemanticField(name="quantidade", type="integer", semantic_role="measure"),
        ])


def test_compute_kpis_rate_over_long_model():
    kpis = compute_kpis(list(_DATASET), _c1())
    by_metric = {k.metric: k for k in kpis}
    assert "total_quantidade" in by_metric
    assert by_metric["total_quantidade"].value == 35.0
    aprov = by_metric["aprovado_rate"]
    assert abs(aprov.value - 15.0 / 35.0) < 1e-9
    assert aprov.numerator == 15.0 and aprov.denominator == 35.0
    assert aprov.validation_status == "ok"


def test_detect_anomalies_concentration():
    skewed = [
        {"row_id": 1, "status": "Reprovado", "quantidade": 90.0},
        {"row_id": 2, "status": "Aprovado", "quantidade": 10.0},
    ]
    kpis = compute_kpis(skewed, _c1())
    anomalies = detect_anomalies(skewed, _c1(), kpis)
    assert any(a.type == "concentration" for a in anomalies)


def test_build_metrics_report_complete():
    report = build_metrics_report(_c0(), _c1())
    assert report.schema_version == "c2_metrics.v1"
    assert len(report.kpis) >= 1
    assert any(a.id == "status_distribution" for a in report.aggregations)


def test_kpi_division_by_zero_is_undefined():
    empty = []
    kpis = compute_kpis(empty, _c1())
    total = {k.metric: k for k in kpis}.get("total_quantidade")
    assert total is not None and total.value == 0.0


# --- Task 13: __main__ ---
import json as _json
import subprocess as _sub
import os as _os


def test_phase_c2_cli_writes_artifact(tmp_path):
    (tmp_path / "T_c0_dataset.json").write_text(_c0().model_dump_json(indent=2), encoding="utf-8")
    (tmp_path / "T_c1_semantic.json").write_text(_c1().model_dump_json(indent=2), encoding="utf-8")
    result = _sub.run(
        [sys.executable, "-m", "phase_c2", str(tmp_path / "T")],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**_os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    out = tmp_path / "T_c2_metrics.json"
    assert out.exists()
    assert _json.loads(out.read_text(encoding="utf-8"))["schema_version"] == "c2_metrics.v1"

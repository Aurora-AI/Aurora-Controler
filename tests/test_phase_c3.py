"""Testes da Fase C3 — Recomendador + DashboardSpec."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "src" / "product_a" / "trustware",
    REPO_ROOT / "src" / "phase_c3",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import (
    Resolution, DataView, DashboardComponent, Layout, NarrativeBlock,
    DashboardSpec, ChartRule, DashboardComponentSpec,
)


def test_data_view_typed():
    dv = DataView(kind="series", columns=["key", "value"],
                  rows=[{"key": "Aprovado", "value": 769}],
                  source={"aggregation_id": "status_distribution"})
    assert dv.kind == "series"


def test_chart_rule_carries_ids_not_functions():
    r = ChartRule(id="rule.status_distribution.horizontal_bar.v1", priority=20,
                  analytical_intent="status_distribution",
                  predicate_id="predicate.has_status_breakdown_and_measure.v1",
                  component_type="horizontal_bar",
                  data_view_builder_id="builder.status_distribution.v1")
    assert isinstance(r.predicate_id, str)
    assert isinstance(r.data_view_builder_id, str)


def test_dashboard_spec_roundtrip():
    spec = DashboardSpec(
        dashboard_id="d1", title="T", resolution=Resolution(),
        theme="executive_dark", llm_used=False,
        layout=Layout(kind="c_level_grid", rows=[["kpi_summary"]]),
        data_views={"kpis": DataView(kind="kpi_list", columns=["metric"],
                                     rows=[{"metric": "m"}])},
        components=[DashboardComponent(id="kpi_summary", type="kpi_cards",
            data_binding="data_views.kpis", analytical_intent="summary_kpis",
            generated_by_rule="rule.summary_kpis.kpi_cards.v1")],
    )
    assert spec.schema_version == "dashboard_spec.v1"
    assert spec.resolution.width == 3840
    assert DashboardSpec.model_validate(spec.model_dump()).dashboard_id == "d1"


def test_dashboard_component_spec_pair():
    cs = DashboardComponentSpec(
        component=DashboardComponent(id="c1", type="horizontal_bar",
            data_binding="data_views.c1", analytical_intent="status_distribution",
            generated_by_rule="rule.x.v1"),
        required_data_view=DataView(kind="series", columns=["key", "value"], rows=[]),
    )
    assert cs.component.id == "c1"


# --- Task 14: catalog ---
from dashboard_contracts import (
    MetricsReport, KPI, Aggregation, AggregationRow, SemanticModel, SemanticField,
)
from catalog import (
    CHART_RULES, PREDICATE_REGISTRY, DATA_VIEW_BUILDER_REGISTRY,
)


def _metrics() -> MetricsReport:
    return MetricsReport(
        kpis=[KPI(metric="total_quantidade", label="Total", value=35.0,
                  formula="sum(quantidade)", numerator=35, denominator=35,
                  validation_status="ok")],
        aggregations=[
            Aggregation(id="status_distribution", by="status", measure="quantidade",
                        rows=[AggregationRow(key="Aprovado", value=15.0),
                              AggregationRow(key="Reprovado", value=20.0)]),
            Aggregation(id="cnpj_ranking", by="cnpj", measure="quantidade",
                        rows=[AggregationRow(key="X1", value=30.0),
                              AggregationRow(key="X2", value=5.0)]),
        ],
    )


def _semantic() -> SemanticModel:
    return SemanticModel(primary_dimension="cnpj", secondary_dimension="status",
        fields=[SemanticField(name="quantidade", type="integer", semantic_role="measure")])


def test_every_rule_has_registered_predicate_and_builder():
    for rule in CHART_RULES:
        assert rule.predicate_id in PREDICATE_REGISTRY
        assert rule.data_view_builder_id in DATA_VIEW_BUILDER_REGISTRY


def test_predicates_fire_on_fixture():
    sem, met = _semantic(), _metrics()
    assert PREDICATE_REGISTRY["predicate.has_kpis.v1"](sem, met) is True
    assert PREDICATE_REGISTRY["predicate.has_status_breakdown_and_measure.v1"](sem, met) is True
    assert PREDICATE_REGISTRY["predicate.has_entity_and_measure.v1"](sem, met) is True


def test_builder_status_distribution_produces_series():
    dv = DATA_VIEW_BUILDER_REGISTRY["builder.status_distribution.v1"](_semantic(), _metrics())
    assert dv.kind == "series"
    assert dv.columns == ["key", "value"]
    assert {"key": "Aprovado", "value": 15.0} in dv.rows
    assert dv.source["aggregation_id"] == "status_distribution"


def test_fmt_kpi_preserves_decimals():
    from catalog import _fmt_kpi
    assert _fmt_kpi(20.0, "total_quantidade") == "20"
    assert _fmt_kpi(19.99, "total_valor") == "19,99"   # decimal preservado
    assert _fmt_kpi(0.2076, "aprovado_rate") == "20,8%"


# --- Task 15: recommend ---
from recommend import recommend


def test_recommend_returns_component_specs():
    specs = recommend(_semantic(), _metrics())
    intents = {s.component.analytical_intent for s in specs}
    assert intents == {"summary_kpis", "status_distribution", "entity_ranking"}


def test_recommend_one_component_per_intent():
    specs = recommend(_semantic(), _metrics())
    intents = [s.component.analytical_intent for s in specs]
    assert len(intents) == len(set(intents))


def test_recommend_each_spec_has_data_view_and_rule():
    specs = recommend(_semantic(), _metrics())
    for s in specs:
        assert s.required_data_view.rows is not None
        assert s.component.generated_by_rule.startswith("rule.")
        assert s.component.data_binding == f"data_views.{s.component.id}"


def test_recommend_ordered_by_priority():
    specs = recommend(_semantic(), _metrics())
    # summary_kpis (100) vem antes de status_distribution (80) antes de entity_ranking (60)
    assert specs[0].component.analytical_intent == "summary_kpis"


# --- Task 16: spec_builder ---
from spec_builder import build_dashboard_spec, validate_spec_self_contained


def test_build_dashboard_spec_is_self_contained():
    spec = build_dashboard_spec(_semantic(), _metrics(),
                                dashboard_id="d1", title="Análise")
    assert spec.schema_version == "dashboard_spec.v1"
    for comp in spec.components:
        assert comp.id in spec.data_views
    comp_ids = {c.id for c in spec.components}
    for row in spec.layout.rows:
        for cid in row:
            assert cid in comp_ids


def test_build_dashboard_spec_layout_puts_kpis_first():
    spec = build_dashboard_spec(_semantic(), _metrics(), dashboard_id="d1", title="T")
    assert spec.layout.rows[0] == ["summary_kpis"]


def test_validate_spec_self_contained_passes():
    spec = build_dashboard_spec(_semantic(), _metrics(), dashboard_id="d1", title="T")
    validate_spec_self_contained(spec)  # não levanta exceção


def test_validate_spec_self_contained_catches_missing_binding():
    spec = build_dashboard_spec(_semantic(), _metrics(), dashboard_id="d1", title="T")
    del spec.data_views[spec.components[0].id]
    import pytest
    with pytest.raises(ValueError):
        validate_spec_self_contained(spec)


def test_build_dashboard_spec_no_llm_empty_narrative():
    spec = build_dashboard_spec(_semantic(), _metrics(), dashboard_id="d1",
                                title="T", llm_used=False)
    assert spec.narrative == []
    assert spec.llm_used is False


# --- Task 17: narrative + __main__ ---
import json as _json
import subprocess as _sub
import os as _os
from narrative import build_narrative_prompt


def test_build_narrative_prompt_includes_kpis():
    prompt = build_narrative_prompt(_metrics())
    assert "total_quantidade" in prompt
    assert "Total" in prompt


def test_phase_c3_cli_writes_spec_without_llm(tmp_path):
    sem = _semantic()
    met = _metrics()
    (tmp_path / "T_c1_semantic.json").write_text(sem.model_dump_json(indent=2), encoding="utf-8")
    (tmp_path / "T_c2_metrics.json").write_text(met.model_dump_json(indent=2), encoding="utf-8")
    result = _sub.run(
        [sys.executable, "-m", "phase_c3", str(tmp_path / "T")],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**_os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    out = tmp_path / "T_c3_dashboard_spec.json"
    assert out.exists()
    data = _json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "dashboard_spec.v1"
    assert data["llm_used"] is False
    assert data["narrative"] == []

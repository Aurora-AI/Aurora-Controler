"""Testes da Fase C3 — Recomendador + DashboardSpec."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
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

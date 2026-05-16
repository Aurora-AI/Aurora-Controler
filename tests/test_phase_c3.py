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

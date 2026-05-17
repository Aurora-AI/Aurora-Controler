"""Testes da Fase C4 — Renderização."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c4",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import (
    DashboardSpec, DataView, DashboardComponent, Layout, Resolution,
)
from html_render import render_html


def _spec() -> DashboardSpec:
    return DashboardSpec(
        dashboard_id="d1", title="Análise de Propostas", resolution=Resolution(),
        theme="executive_dark", llm_used=False,
        layout=Layout(kind="c_level_grid",
                      rows=[["summary_kpis"], ["status_distribution"]]),
        data_views={
            "summary_kpis": DataView(kind="kpi_list",
                columns=["metric", "label", "value", "display_value"],
                rows=[{"metric": "total", "label": "Total", "value": 35.0,
                       "display_value": "35"}]),
            "status_distribution": DataView(kind="series", columns=["key", "value"],
                rows=[{"key": "Aprovado", "value": 15.0}]),
        },
        components=[
            DashboardComponent(id="summary_kpis", type="kpi_cards",
                data_binding="data_views.summary_kpis",
                analytical_intent="summary_kpis",
                generated_by_rule="rule.summary_kpis.kpi_cards.v1"),
            DashboardComponent(id="status_distribution", type="horizontal_bar",
                data_binding="data_views.status_distribution",
                analytical_intent="status_distribution",
                generated_by_rule="rule.status_distribution.horizontal_bar.v1"),
        ],
    )


def test_render_html_contains_title():
    html = render_html(_spec())
    assert "Análise de Propostas" in html


def test_render_html_has_container_per_component():
    html = render_html(_spec())
    assert 'id="comp-summary_kpis"' in html
    assert 'id="comp-status_distribution"' in html


def test_render_html_embeds_spec_and_echarts():
    html = render_html(_spec())
    assert "echarts" in html
    assert "data_views" in html  # SPEC embutido como JSON


def test_render_html_sets_4k_dimensions():
    html = render_html(_spec())
    assert "3840" in html and "2160" in html

"""Fase C3 — Montagem do DashboardSpec autocontido.

O DashboardSpec sai daqui com todos os data_views materializados.
A C4 nunca precisa abrir o C2.
"""
from __future__ import annotations

from libs.trustware.dashboard_contracts import (
    DashboardComponent, DashboardSpec, DataView, Layout, MetricsReport,
    Resolution, SemanticModel,
)
from phase_c3.recommend import recommend


def _build_layout(components: list[DashboardComponent]) -> Layout:
    """KPIs na primeira linha; demais componentes em pares."""
    kpi_ids = [c.id for c in components if c.type == "kpi_cards"]
    other_ids = [c.id for c in components if c.type != "kpi_cards"]
    rows: list[list[str]] = []
    if kpi_ids:
        rows.append(kpi_ids)
    for i in range(0, len(other_ids), 2):
        rows.append(other_ids[i:i + 2])
    if not rows:
        rows = [[c.id for c in components]]
    return Layout(kind="c_level_grid", rows=rows)


def validate_spec_self_contained(spec: DashboardSpec) -> None:
    """Garante que todo componente e todo id de layout têm data_view e componente.

    Levanta ValueError se a regra de autocontenção for violada.
    """
    comp_ids = {c.id for c in spec.components}
    for comp in spec.components:
        if comp.id not in spec.data_views:
            raise ValueError(f"Componente '{comp.id}' sem data_view materializado")
    for row in spec.layout.rows:
        for cid in row:
            if cid not in comp_ids:
                raise ValueError(f"Layout referencia '{cid}' sem componente")


def build_dashboard_spec(
    semantic: SemanticModel,
    metrics: MetricsReport,
    dashboard_id: str,
    title: str,
    theme: str = "executive_dark",
    llm_used: bool = False,
) -> DashboardSpec:
    """Monta o DashboardSpec autocontido a partir de C1 + C2."""
    specs = recommend(semantic, metrics)

    data_views: dict[str, DataView] = {}
    components: list[DashboardComponent] = []
    for s in specs:
        data_views[s.component.id] = s.required_data_view
        components.append(s.component)

    spec = DashboardSpec(
        dashboard_id=dashboard_id, title=title, resolution=Resolution(),
        theme=theme, llm_used=llm_used, layout=_build_layout(components),
        data_views=data_views, components=components, narrative=[],
    )
    validate_spec_self_contained(spec)
    return spec

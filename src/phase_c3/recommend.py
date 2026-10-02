"""Fase C3 — Recomendação determinística de componentes.

Aplica o catálogo, deduplica por analytical_intent (maior priority vence),
e materializa o data_view de cada componente escolhido.
"""
from __future__ import annotations

from libs.trustware.dashboard_contracts import (
    ChartRule, DashboardComponent, DashboardComponentSpec, MetricsReport, SemanticModel,
)
from phase_c3.catalog import CHART_RULES, DATA_VIEW_BUILDER_REGISTRY, PREDICATE_REGISTRY


def recommend(
    semantic: SemanticModel, metrics: MetricsReport
) -> list[DashboardComponentSpec]:
    """Retorna a lista de DashboardComponentSpec — componente + data_view."""
    # Dedup por intent: cada intent fica com a regra de maior priority
    chosen: dict[str, ChartRule] = {}
    for rule in CHART_RULES:
        predicate = PREDICATE_REGISTRY[rule.predicate_id]
        if not predicate(semantic, metrics):
            continue
        current = chosen.get(rule.analytical_intent)
        if current is None or rule.priority > current.priority:
            chosen[rule.analytical_intent] = rule

    ordered = sorted(chosen.values(), key=lambda r: -r.priority)

    specs: list[DashboardComponentSpec] = []
    for rule in ordered:
        builder = DATA_VIEW_BUILDER_REGISTRY[rule.data_view_builder_id]
        data_view = builder(semantic, metrics)
        component = DashboardComponent(
            id=rule.analytical_intent,
            type=rule.component_type,
            data_binding=f"data_views.{rule.analytical_intent}",
            analytical_intent=rule.analytical_intent,
            generated_by_rule=rule.id,
        )
        specs.append(DashboardComponentSpec(
            component=component, required_data_view=data_view))
    return specs

"""Fase C3 — Catálogo de regras de gráfico (dado versionado).

Cada ChartRule carrega IDs estáveis (predicate_id, data_view_builder_id)
resolvidos por registries. Nunca carrega funções Python diretamente.
"""
from __future__ import annotations

from typing import Callable

from dashboard_contracts import ChartRule, DataView, MetricsReport, SemanticModel

_RANKING_LIMIT = 15

Predicate = Callable[[SemanticModel, MetricsReport], bool]
Builder = Callable[[SemanticModel, MetricsReport], DataView]


# --------------------------------------------------------------------------
# Predicados — determinísticos, puros
# --------------------------------------------------------------------------
def _has_kpis(semantic: SemanticModel, metrics: MetricsReport) -> bool:
    return len(metrics.kpis) > 0


def _has_status_breakdown(semantic: SemanticModel, metrics: MetricsReport) -> bool:
    return any(a.id.endswith("_distribution") for a in metrics.aggregations)


def _has_entity_ranking(semantic: SemanticModel, metrics: MetricsReport) -> bool:
    return any(a.id.endswith("_ranking") for a in metrics.aggregations)


PREDICATE_REGISTRY: dict[str, Predicate] = {
    "predicate.has_kpis.v1": _has_kpis,
    "predicate.has_status_breakdown_and_measure.v1": _has_status_breakdown,
    "predicate.has_entity_and_measure.v1": _has_entity_ranking,
}


# --------------------------------------------------------------------------
# Builders de data_view — materializam dados do C2 num DataView tipado
# --------------------------------------------------------------------------
def _fmt_kpi(value: float, metric: str) -> str:
    if metric.endswith("_rate"):
        return f"{value * 100:.1f}%".replace(".", ",")
    return f"{value:,.0f}".replace(",", ".")


def _build_kpi_list(semantic: SemanticModel, metrics: MetricsReport) -> DataView:
    rows = [
        {"metric": k.metric, "label": k.label, "value": k.value,
         "display_value": _fmt_kpi(k.value, k.metric)}
        for k in metrics.kpis
    ]
    return DataView(
        kind="kpi_list", columns=["metric", "label", "value", "display_value"],
        rows=rows, source={"kpi_ids": [k.metric for k in metrics.kpis]},
    )


def _first_agg(metrics: MetricsReport, suffix: str):
    for a in metrics.aggregations:
        if a.id.endswith(suffix):
            return a
    raise ValueError(f"Nenhuma agregação com sufixo {suffix}")


def _build_status_distribution(semantic: SemanticModel, metrics: MetricsReport) -> DataView:
    agg = _first_agg(metrics, "_distribution")
    rows = [{"key": r.key, "value": r.value} for r in agg.rows]
    return DataView(kind="series", columns=["key", "value"], rows=rows,
                    source={"aggregation_id": agg.id})


def _build_entity_ranking(semantic: SemanticModel, metrics: MetricsReport) -> DataView:
    agg = _first_agg(metrics, "_ranking")
    rows = [{"key": r.key, "value": r.value} for r in agg.rows[:_RANKING_LIMIT]]
    return DataView(kind="series", columns=["key", "value"], rows=rows,
                    source={"aggregation_id": agg.id})


DATA_VIEW_BUILDER_REGISTRY: dict[str, Builder] = {
    "builder.kpi_list.v1": _build_kpi_list,
    "builder.status_distribution.v1": _build_status_distribution,
    "builder.entity_ranking.v1": _build_entity_ranking,
}


# --------------------------------------------------------------------------
# Catálogo — prioridade numérica descendente (maior vence)
# --------------------------------------------------------------------------
CHART_RULES: list[ChartRule] = [
    ChartRule(
        id="rule.summary_kpis.kpi_cards.v1", priority=100,
        analytical_intent="summary_kpis",
        predicate_id="predicate.has_kpis.v1",
        component_type="kpi_cards",
        data_view_builder_id="builder.kpi_list.v1",
    ),
    ChartRule(
        id="rule.status_distribution.horizontal_bar.v1", priority=80,
        analytical_intent="status_distribution",
        predicate_id="predicate.has_status_breakdown_and_measure.v1",
        component_type="horizontal_bar",
        data_view_builder_id="builder.status_distribution.v1",
    ),
    ChartRule(
        id="rule.entity_ranking.bar_ranking.v1", priority=60,
        analytical_intent="entity_ranking",
        predicate_id="predicate.has_entity_and_measure.v1",
        component_type="bar_ranking",
        data_view_builder_id="builder.entity_ranking.v1",
    ),
]

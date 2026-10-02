"""Fase C2 — Agregações group-by em Python puro.

Limite operacional do MVP: até 100.000 linhas normalizadas. Acima disso,
o pipeline deve emitir warning de escala (ver build_metrics_report).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from libs.trustware.dashboard_contracts import Aggregation, AggregationRow


def aggregate_by(
    dataset: list[dict[str, Any]], by: str, measure: str, agg_id: str
) -> Aggregation:
    """Soma `measure` agrupando por `by`. Retorna Aggregation ordenada desc."""
    sums: dict[str, float] = defaultdict(float)
    for row in dataset:
        key = str(row.get(by, ""))
        value = row.get(measure, 0.0)
        if isinstance(value, (int, float)):
            sums[key] += float(value)
    rows = [
        AggregationRow(key=k, value=v)
        for k, v in sorted(sums.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return Aggregation(id=agg_id, by=by, measure=measure, rows=rows)

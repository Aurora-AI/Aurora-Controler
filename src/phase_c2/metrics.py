"""Fase C2 — Motor de KPIs, validação e detecção de anomalias.

Toda fórmula opera sobre o modelo canônico longo: nunca assume colunas
físicas de status. KPIs carregam fórmula, numerador, denominador e validação.

validation_status: "ok" (calculado sobre o modelo longo já validado pela C0)
ou "undefined" (divisão por zero). O valor "mismatch" do contrato fica
reservado para uma futura validação cruzada contra o total geral da origem.
"""
from __future__ import annotations

import sys
import unicodedata
from typing import Any

from libs.trustware.dashboard_contracts import (
    Aggregation, Anomaly, C0Dataset, KPI, MetricsReport, SemanticModel,
)
from phase_c2.aggregate import aggregate_by

_SCALE_LIMIT = 100_000
_CONCENTRATION_THRESHOLD = 0.5


def _slug(text: str) -> str:
    """Normaliza um rótulo em chave ASCII minúscula (Aprovado -> aprovado)."""
    norm = unicodedata.normalize("NFKD", str(text))
    ascii_text = norm.encode("ascii", "ignore").decode("ascii")
    return ascii_text.strip().lower().replace(" ", "_")


def _measure_field(semantic: SemanticModel) -> str:
    for f in semantic.fields:
        if f.semantic_role == "measure":
            return f.name
    return "quantidade"


def _status_field(semantic: SemanticModel) -> str | None:
    for f in semantic.fields:
        if f.business_role == "proposal_status":
            return f.name
    for f in semantic.fields:
        if f.semantic_role == "breakdown_dimension":
            return f.name
    return None


def compute_kpis(dataset: list[dict[str, Any]], semantic: SemanticModel) -> list[KPI]:
    """Calcula KPIs sobre o modelo longo: total da measure + taxa por categoria."""
    measure = _measure_field(semantic)
    status = _status_field(semantic)
    total = sum(float(r.get(measure, 0.0)) for r in dataset
                if isinstance(r.get(measure), (int, float)))

    kpis: list[KPI] = [KPI(
        metric=f"total_{measure}", label=f"Total de {measure}", value=total,
        formula=f"sum({measure})", numerator=total, denominator=total,
        validation_status="ok",
    )]

    if status is None:
        return kpis

    per_cat: dict[str, float] = {}
    for r in dataset:
        val = r.get(measure, 0.0)
        if isinstance(val, (int, float)):
            key = str(r.get(status, ""))
            per_cat[key] = per_cat.get(key, 0.0) + float(val)

    for cat, num in per_cat.items():
        if total == 0:
            value, vstatus = 0.0, "undefined"
        else:
            value, vstatus = num / total, "ok"
        kpis.append(KPI(
            metric=f"{_slug(cat)}_rate", label=f"Taxa de {cat}", value=value,
            formula=f"sum({measure} where {status} == '{cat}') / sum({measure})",
            numerator=num, denominator=total, validation_status=vstatus,
        ))
    return kpis


def detect_anomalies(
    dataset: list[dict[str, Any]], semantic: SemanticModel, kpis: list[KPI]
) -> list[Anomaly]:
    """Detecta concentração: alguma categoria de status acima de 50% do total.

    `dataset` e `semantic` são reservados para tipos futuros de anomalia
    (ex.: detecção de outliers por dimensão); o MVP usa apenas `kpis`.
    """
    anomalies: list[Anomaly] = []
    for k in kpis:
        if k.metric.endswith("_rate") and k.value > _CONCENTRATION_THRESHOLD:
            anomalies.append(Anomaly(
                type="concentration", severity="high", metric=k.metric,
                evidence=f"{k.value * 100:.1f}% concentrado em {k.label}",
            ))
    return anomalies


def build_metrics_report(c0: C0Dataset, semantic: SemanticModel) -> MetricsReport:
    """Monta o MetricsReport: KPIs + agregações + anomalias.

    Acima de _SCALE_LIMIT linhas, emite aviso de escala em stderr.
    """
    dataset = c0.dataset
    measure = _measure_field(semantic)
    if len(dataset) > _SCALE_LIMIT:
        print(f"[C2] Aviso de escala: {len(dataset)} linhas acima do limite "
              f"de {_SCALE_LIMIT} — considerar backend analítico futuro",
              file=sys.stderr)

    aggregations: list[Aggregation] = []
    for f in semantic.fields:
        if f.semantic_role == "breakdown_dimension":
            aggregations.append(aggregate_by(dataset, f.name, measure, f"{f.name}_distribution"))
        elif f.semantic_role == "entity_id":
            aggregations.append(aggregate_by(dataset, f.name, measure, f"{f.name}_ranking"))

    kpis = compute_kpis(dataset, semantic)
    anomalies = detect_anomalies(dataset, semantic, kpis)
    return MetricsReport(kpis=kpis, aggregations=aggregations, anomalies=anomalies)

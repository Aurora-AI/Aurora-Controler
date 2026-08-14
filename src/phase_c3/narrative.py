"""Fase C3 — Narrativa executiva opcional via LLM.

A LLM só redige texto (títulos, narrativa). Nunca calcula números nem
altera data_views. Sem LLM disponível, retorna lista vazia.
"""
from __future__ import annotations

from libs.trustware.dashboard_contracts import MetricsReport, NarrativeBlock


def build_narrative_prompt(metrics: MetricsReport) -> str:
    """Monta o prompt da narrativa a partir dos KPIs e anomalias do C2."""
    lines = ["Você é um analista executivo. Com base nos indicadores abaixo,",
             "escreva 2 frases de leitura executiva. Não invente números.\n",
             "KPIs:"]
    for k in metrics.kpis:
        lines.append(f"- {k.metric} ({k.label}): {k.value}")
    if metrics.anomalies:
        lines.append("Anomalias:")
        for a in metrics.anomalies:
            lines.append(f"- {a.evidence}")
    return "\n".join(lines)


def generate_narrative(metrics: MetricsReport) -> list[NarrativeBlock]:
    """Gera a narrativa via LLM. Qualquer falha resulta em lista vazia."""
    prompt = build_narrative_prompt(metrics)
    try:
        from litellm import completion
        resp = completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp["choices"][0]["message"]["content"].strip()
        return [NarrativeBlock(level="c_level", text=text)]
    except Exception:
        return []

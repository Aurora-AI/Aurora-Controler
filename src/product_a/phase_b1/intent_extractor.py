"""
EXRS Phase B1 — Intent Extractor

Usa litellm.completion() para extrair uma IntentCapture estruturada
a partir do histórico de conversa com o usuário.
Segue o mesmo padrão JSON-structured output da Phase A3 (translator.py).
"""
import json
import logging
import os

from litellm import completion
from product_a.trustware.pipeline_contracts import InputParameter, IntentCapture, OutputMetric

_log = logging.getLogger(__name__)

_EXTRACTION_SCHEMA = """
Retorne APENAS um JSON válido com a seguinte estrutura (sem markdown, sem texto extra):
{
  "user_goal": "<resumo em 1-2 frases do que o usuário quer analisar ou simular>",
  "input_parameters": [
    {
      "node_id": "<coordenada canônica, ex: Planilha1!B5>",
      "label": "<nome legível inferido da conversa>",
      "suggested_range": [<min>, <max>]
    }
  ],
  "output_metrics": [
    {
      "node_id": "<coordenada canônica>",
      "label": "<nome legível>"
    }
  ],
  "scenario_description": "<descrição opcional do cenário>"
}

Omita "suggested_range" se o usuário não mencionou valores. Omita "scenario_description" se não aplicável.
"""


def build_extraction_prompt(messages: list[dict], summary: dict) -> str:
    """
    Constrói o prompt de extração com o histórico de conversa e o contexto do workbook.
    """
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )
    candidates_in = "\n".join(
        f"  - {c['node_id']} (valor atual: {c.get('current_value', 'N/A')})"
        for c in summary.get("input_candidates", [])
    )
    candidates_out = "\n".join(
        f"  - {c['node_id']} (fórmula: {c.get('formula', '')})"
        for c in summary.get("output_candidates", [])
    )

    return f"""Workbook: {summary['workbook_name']}
Abas: {', '.join(summary.get('sheets', []))}

Candidatos a entrada (células sem dependências):
{candidates_in or '  (nenhum identificado)'}

Candidatos a saída (fórmulas finais):
{candidates_out or '  (nenhum identificado)'}

--- HISTÓRICO DA CONVERSA ---
{history_text}
--- FIM DO HISTÓRICO ---

Com base na conversa acima, extraia a intenção estruturada do usuário.
{_EXTRACTION_SCHEMA}"""


def extract_intent(messages: list[dict], summary: dict) -> IntentCapture:
    """
    Chama o LLM para extrair um IntentCapture estruturado do histórico de conversa.

    Args:
        messages: lista de dicts {"role": "user"|"assistant", "content": str}
        summary: dict retornado por context_builder.build_workbook_summary()

    Returns:
        IntentCapture com a intenção estruturada.
    """
    model = os.getenv("CHAT_MODEL", "anthropic/claude-3-5-haiku-20241022")
    prompt = build_extraction_prompt(messages, summary)

    _log.debug("Extraindo intenção com modelo %s", model)
    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=1024,
        timeout=30,
    )
    raw = response.choices[0].message.content.strip()

    # Limpar markdown se necessário (mesmo padrão do translator.py)
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    data = json.loads(raw)

    return IntentCapture(
        workbook_name=summary["workbook_name"],
        user_goal=data["user_goal"],
        input_parameters=[
            InputParameter(
                node_id=p["node_id"],
                label=p["label"],
                suggested_range=p.get("suggested_range"),
            )
            for p in data.get("input_parameters", [])
        ],
        output_metrics=[
            OutputMetric(node_id=m["node_id"], label=m["label"])
            for m in data.get("output_metrics", [])
        ],
        scenario_description=data.get("scenario_description"),
    )

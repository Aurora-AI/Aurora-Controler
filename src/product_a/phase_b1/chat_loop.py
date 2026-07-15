"""
EXRS Phase B1 — Chat Loop

Loop de chat CLI multi-turn que conversa com o usuário para capturar
a intenção de simulação. Encerra quando o usuário digita uma palavra-chave
de confirmação ("ok", "pronto", "done", "capturar") ou após 10 turnos.
"""
import logging
import os

from litellm import completion
from intent_extractor import extract_intent
from product_a.trustware.pipeline_contracts import IntentCapture

_log = logging.getLogger(__name__)

_DONE_KEYWORDS = {"ok", "pronto", "done", "capturar", "confirmar", "pode"}
_MAX_TURNS = 10


def _is_done_signal(text: str) -> bool:
    """Retorna True se o texto contém uma palavra-chave de encerramento."""
    words = set(text.lower().split())
    return bool(words & _DONE_KEYWORDS)


def build_system_prompt(summary: dict) -> str:
    """Constrói o system prompt com o contexto do workbook."""
    inputs_text = "\n".join(
        f"  • {c['node_id']} — valor atual: {c.get('current_value', 'N/A')}"
        for c in summary.get("input_candidates", [])
    ) or "  (nenhum identificado)"

    outputs_text = "\n".join(
        f"  • {c['node_id']} — {c.get('formula', '')}"
        for c in summary.get("output_candidates", [])
    ) or "  (nenhum identificado)"

    return f"""Você é um analista que ajuda o usuário a simular e analisar a planilha "{summary['workbook_name']}".

Abas disponíveis: {', '.join(summary.get('sheets', []))}

Células de entrada (candidatas a parâmetros):
{inputs_text}

Células de saída (resultados finais):
{outputs_text}

Seu objetivo é entender:
1. O que o usuário quer simular ou analisar
2. Quais parâmetros ele quer variar (e com quais valores)
3. Quais resultados ele quer acompanhar

Faça perguntas diretas e objetivas. Quando tiver informações suficientes,
informe ao usuário que pode digitar "ok" ou "pronto" para capturar a intenção."""


def run_chat(summary: dict) -> IntentCapture:
    """
    Executa o loop de chat interativo e retorna um IntentCapture estruturado.

    Args:
        summary: dict retornado por context_builder.build_workbook_summary()

    Returns:
        IntentCapture com a intenção capturada.
    """
    model = os.getenv("CHAT_MODEL", "anthropic/claude-3-5-haiku-20241022")
    system_prompt = build_system_prompt(summary)
    messages: list[dict] = []

    print(f"\n{'='*60}")
    print(f"  Chat de Captura de Intenção — {summary['workbook_name']}")
    print(f"{'='*60}")
    print("  Digite sua intenção de simulação. Quando terminar, digite 'ok'.")
    print(f"{'='*60}\n")

    for turn in range(_MAX_TURNS):
        user_input = input("Você: ").strip()
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        if _is_done_signal(user_input) and turn > 0:
            break

        _log.debug("Turno %d — chamando LLM", turn + 1)
        response = completion(
            model=model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.3,
            max_tokens=512,
            timeout=30,
        )
        assistant_msg = response.choices[0].message.content.strip()
        messages.append({"role": "assistant", "content": assistant_msg})
        print(f"\nAssistente: {assistant_msg}\n")

    print("\nCapturando intenção estruturada...\n")
    return extract_intent(messages=messages, summary=summary)

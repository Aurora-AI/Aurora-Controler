# Phase B1 — Chat (Intent Capture) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar um loop de chat CLI que lê os outputs do pipeline A0–A4, identifica células de entrada e saída, conversa com o usuário para capturar intenção de simulação e grava um `IntentCapture` estruturado em JSON.

**Architecture:** Três camadas independentes: `context_builder` (lê os JSONs do pipeline e constrói um resumo textual do workbook para o LLM), `intent_extractor` (envia o histórico de conversa ao LLM e extrai um `IntentCapture` JSON), e `chat_loop` (orquestra as duas camadas em um loop CLI interativo). A extração usa a mesma abordagem JSON-structured output que a Phase A3 — sem tool_use, sem dependências novas.

**Tech Stack:** Python 3.11+, litellm (já em requirements.txt), pydantic v2, json, os, pathlib. LLM configurável via `CHAT_MODEL` env var (default: `anthropic/claude-3-5-haiku-20241022`).

---

## Mapa de Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `libs/trustware/pipeline_contracts.py` | Adicionar `InputParameter`, `OutputMetric`, `IntentCapture` abaixo de `IntentSpec` existente |
| `src/phase_b1/__init__.py` | Pacote vazio |
| `src/phase_b1/context_builder.py` | Lê `_a2_dag.json` + `_a15_norm.json`, identifica inputs/outputs, retorna summary dict |
| `src/phase_b1/intent_extractor.py` | Chama `litellm.completion()` com histórico + prompt de extração, devolve `IntentCapture` |
| `src/phase_b1/chat_loop.py` | Loop CLI multi-turn; para quando usuário digita "ok"/"pronto"/"done" |
| `src/phase_b1/__main__.py` | Entry point: `python -m phase_b1 output/Pasta1` |
| `tests/test_phase_b1.py` | Testes unitários com mock de `litellm.completion` — sem chamadas reais à API |

---

## Task 1 — Adicionar tipos B1 ao `pipeline_contracts.py`

**Files:**
- Modify: `libs/trustware/pipeline_contracts.py` — adicionar após a classe `IntentSpec` existente
- Test: `tests/test_phase_b1.py` (criar)

- [ ] **Step 1: Escrever o teste que valida os novos tipos**

Criar `tests/test_phase_b1.py`:

```python
"""Testes da Phase B1 — Chat (Intent Capture)."""
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in [
    REPO_ROOT / "src" / "phase_b1",
    REPO_ROOT / "libs" / "trustware",
]:
    sys.path.insert(0, str(p))

from pipeline_contracts import InputParameter, OutputMetric, IntentCapture


def test_input_parameter_model():
    p = InputParameter(node_id="Sheet1!B5", label="Taxa de desconto", current_value=0.1)
    assert p.node_id == "Sheet1!B5"
    assert p.suggested_range is None


def test_input_parameter_with_range():
    p = InputParameter(
        node_id="Sheet1!B5",
        label="Taxa de desconto",
        suggested_range=[0.0, 0.5],
    )
    assert p.suggested_range == [0.0, 0.5]


def test_output_metric_model():
    m = OutputMetric(node_id="Sheet1!D20", label="Lucro líquido", current_value=50000)
    assert m.node_id == "Sheet1!D20"


def test_intent_capture_serialization():
    ic = IntentCapture(
        workbook_name="Pasta1",
        user_goal="Simular impacto de desconto no lucro",
        input_parameters=[
            InputParameter(node_id="Sheet1!B5", label="Desconto", suggested_range=[0.0, 0.3])
        ],
        output_metrics=[
            OutputMetric(node_id="Sheet1!D20", label="Lucro")
        ],
        scenario_description="Reduzir desconto de 10% para 5%",
    )
    data = ic.model_dump()
    assert data["workbook_name"] == "Pasta1"
    assert len(data["input_parameters"]) == 1
    assert data["input_parameters"][0]["node_id"] == "Sheet1!B5"
    # Roundtrip
    ic2 = IntentCapture.model_validate(data)
    assert ic2.user_goal == ic.user_goal


def test_intent_capture_timestamp_auto():
    ic = IntentCapture(
        workbook_name="X",
        user_goal="test",
        input_parameters=[],
        output_metrics=[],
    )
    assert ic.timestamp  # não vazio
```

- [ ] **Step 2: Rodar e confirmar que FALHA** (tipos não existem ainda)

```bash
python -m pytest tests/test_phase_b1.py::test_input_parameter_model -v
```
Expected: `ImportError: cannot import name 'InputParameter'`

- [ ] **Step 3: Adicionar os tipos ao `pipeline_contracts.py`**

Localizar a classe `IntentSpec` (linha ~162) e inserir APÓS ela (antes de `StagedRuleGraph`):

```python
class InputParameter(BaseModel):
    """Parâmetro de entrada identificado para simulação — Phase B1."""
    node_id: str                            # ex: "Planilha1!B5"
    label: str                              # nome legível inferido do contexto
    current_value: Any = None
    suggested_range: list[float] | None = None  # [min, max]

class OutputMetric(BaseModel):
    """Métrica de saída que o usuário quer monitorar — Phase B1."""
    node_id: str
    label: str
    current_value: Any = None

class IntentCapture(BaseModel):
    """Intenção estruturada capturada via chat — Phase B1."""
    workbook_name: str
    user_goal: str                              # resumo em 1-2 frases
    input_parameters: list[InputParameter]      # células que o usuário quer variar
    output_metrics: list[OutputMetric]          # células que o usuário quer monitorar
    scenario_description: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b1.py -v
```
Expected: 5 tests PASSED.

- [ ] **Step 5: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: 466 passed (461 + 5 novos), 0 failed.

- [ ] **Step 6: Commit**

```bash
git add libs/trustware/pipeline_contracts.py tests/test_phase_b1.py
git commit -m "feat(b1): add InputParameter, OutputMetric, IntentCapture to pipeline_contracts"
```

---

## Task 2 — Implementar `context_builder.py`

**Files:**
- Create: `src/phase_b1/__init__.py`
- Create: `src/phase_b1/context_builder.py`
- Test: `tests/test_phase_b1.py` (adicionar)

- [ ] **Step 1: Criar `src/phase_b1/__init__.py`** (vazio)

```bash
# Criar diretório e __init__.py vazio
```

Conteúdo do arquivo: apenas um comentário de identificação:
```python
"""EXRS Phase B1 — Chat (Intent Capture)."""
```

- [ ] **Step 2: Escrever os testes de `context_builder`**

Adicionar ao final de `tests/test_phase_b1.py`:

```python
# ── context_builder ────────────────────────────────────────────────────────

from context_builder import identify_input_nodes, identify_output_nodes, build_workbook_summary


# DAG mínimo para testes (não lê disco)
_SAMPLE_DAG = {
    "nodes": [
        {"id": "S!A1", "sheet": "S", "coordinate": "A1", "formula_raw": None, "dependencies": []},
        {"id": "S!A2", "sheet": "S", "coordinate": "A2", "formula_raw": None, "dependencies": []},
        {"id": "S!B1", "sheet": "S", "coordinate": "B1", "formula_raw": "=A1+A2", "dependencies": ["S!A1", "S!A2"]},
        {"id": "S!C1", "sheet": "S", "coordinate": "C1", "formula_raw": "=B1*2", "dependencies": ["S!B1"]},
    ],
    "edges": [],
    "topological_order": ["S!A1", "S!A2", "S!B1", "S!C1"],
}


def test_identify_input_nodes_returns_leaf_nodes():
    """Nós sem dependências são candidatos a input."""
    inputs = identify_input_nodes(_SAMPLE_DAG)
    ids = [n["id"] for n in inputs]
    assert "S!A1" in ids
    assert "S!A2" in ids
    assert "S!B1" not in ids  # tem dependências


def test_identify_output_nodes_returns_root_nodes():
    """Nós com fórmula que não são dependência de ninguém são candidatos a output."""
    outputs = identify_output_nodes(_SAMPLE_DAG)
    ids = [n["id"] for n in outputs]
    assert "S!C1" in ids       # fórmula, não depende de ninguém
    assert "S!B1" not in ids   # é dependência de C1
    assert "S!A1" not in ids   # não tem fórmula (é input estático)


def test_build_workbook_summary_returns_expected_keys():
    """build_workbook_summary retorna dict com as chaves esperadas."""
    summary = build_workbook_summary(dag=_SAMPLE_DAG, norm_ir=_SAMPLE_NORM_IR, workbook_name="TestWB")
    assert "workbook_name" in summary
    assert "sheets" in summary
    assert "input_candidates" in summary
    assert "output_candidates" in summary
    assert summary["workbook_name"] == "TestWB"


_SAMPLE_NORM_IR = {
    "file_path": "test.xlsx",
    "sheets": [
        {
            "name": "S",
            "index": 0,
            "state": "visible",
            "cells": [
                {"coordinate": "A1", "formula_raw": None, "value_static": 100, "data_type": "n"},
                {"coordinate": "A2", "formula_raw": None, "value_static": 200, "data_type": "n"},
                {"coordinate": "B1", "formula_raw": "=A1+A2", "value_static": None, "data_type": "n"},
                {"coordinate": "C1", "formula_raw": "=B1*2", "value_static": None, "data_type": "n"},
            ],
        }
    ],
}
```

- [ ] **Step 3: Rodar e confirmar que FALHA**

```bash
python -m pytest tests/test_phase_b1.py::test_identify_input_nodes_returns_leaf_nodes -v
```
Expected: `ModuleNotFoundError: No module named 'context_builder'`

- [ ] **Step 4: Implementar `src/phase_b1/context_builder.py`**

```python
"""
EXRS Phase B1 — Context Builder

Lê os outputs do pipeline A0–A4 e constrói um resumo compacto do workbook
para uso como contexto do LLM no chat de captura de intenção.
"""
import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def identify_input_nodes(dag: dict) -> list[dict]:
    """
    Retorna nós folha (leaf nodes): células sem dependências.
    São candidatos naturais a parâmetros de entrada para simulação.
    """
    return [n for n in dag["nodes"] if not n.get("dependencies")]


def identify_output_nodes(dag: dict) -> list[dict]:
    """
    Retorna nós raiz (root nodes): células com fórmula que não são
    dependência de nenhum outro nó. São candidatos a métricas de saída.
    """
    all_deps: set[str] = set()
    for node in dag["nodes"]:
        all_deps.update(node.get("dependencies", []))
    return [
        n for n in dag["nodes"]
        if n.get("formula_raw") and n["id"] not in all_deps
    ]


def _get_cell_value(norm_ir: dict, node_id: str) -> object:
    """Busca o valor estático de uma célula no normalized IR."""
    parts = node_id.split("!")
    if len(parts) != 2:
        return None
    sheet_name, coord = parts
    for sheet in norm_ir.get("sheets", []):
        if sheet["name"] == sheet_name:
            for cell in sheet.get("cells", []):
                if cell["coordinate"] == coord:
                    return cell.get("value_static")
    return None


def build_workbook_summary(dag: dict, norm_ir: dict, workbook_name: str) -> dict:
    """
    Constrói um dicionário resumo do workbook para o LLM.

    Args:
        dag: dict deserializado do arquivo _a2_dag.json
        norm_ir: dict deserializado do arquivo _a15_norm.json
        workbook_name: nome do workbook (ex: "Pasta1")

    Returns:
        dict com: workbook_name, sheets, input_candidates, output_candidates
    """
    sheets = [s["name"] for s in norm_ir.get("sheets", [])]

    input_nodes = identify_input_nodes(dag)
    output_nodes = identify_output_nodes(dag)

    input_candidates = [
        {
            "node_id": n["id"],
            "current_value": _get_cell_value(norm_ir, n["id"]),
        }
        for n in input_nodes[:20]  # limita a 20 para não explodir o contexto
    ]

    output_candidates = [
        {
            "node_id": n["id"],
            "formula": n.get("formula_raw", ""),
        }
        for n in output_nodes[:10]
    ]

    return {
        "workbook_name": workbook_name,
        "sheets": sheets,
        "input_candidates": input_candidates,
        "output_candidates": output_candidates,
    }


def load_summary_from_prefix(output_prefix: str) -> dict:
    """
    Carrega os arquivos _a2_dag.json e _a15_norm.json a partir de um prefixo
    (ex: "output/Pasta1") e retorna o summary dict.

    Args:
        output_prefix: caminho sem sufixo (ex: "output/Pasta1")
    """
    prefix = Path(output_prefix)
    workbook_name = prefix.name

    dag_path = Path(f"{output_prefix}_a2_dag.json")
    norm_path = Path(f"{output_prefix}_a15_norm.json")

    if not dag_path.exists():
        raise FileNotFoundError(f"DAG não encontrado: {dag_path}")
    if not norm_path.exists():
        raise FileNotFoundError(f"Normalized IR não encontrado: {norm_path}")

    with open(dag_path, encoding="utf-8") as f:
        dag = json.load(f)
    with open(norm_path, encoding="utf-8") as f:
        norm_ir = json.load(f)

    return build_workbook_summary(dag, norm_ir, workbook_name)
```

- [ ] **Step 5: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b1.py -v
```
Expected: 9 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/phase_b1/__init__.py src/phase_b1/context_builder.py tests/test_phase_b1.py
git commit -m "feat(b1): implement context_builder — identifies input/output nodes from DAG"
```

---

## Task 3 — Implementar `intent_extractor.py`

**Files:**
- Create: `src/phase_b1/intent_extractor.py`
- Test: `tests/test_phase_b1.py` (adicionar)

- [ ] **Step 1: Escrever os testes com mock do litellm**

Adicionar ao final de `tests/test_phase_b1.py`:

```python
# ── intent_extractor ───────────────────────────────────────────────────────

from intent_extractor import extract_intent, build_extraction_prompt


def _mock_completion(json_payload: dict):
    """Retorna um MagicMock que simula litellm.completion() com JSON no conteúdo."""
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(json_payload)
    return mock_resp


_SAMPLE_INTENT_JSON = {
    "user_goal": "Simular impacto de desconto no lucro",
    "input_parameters": [
        {"node_id": "S!A1", "label": "Taxa de desconto", "suggested_range": [0.0, 0.3]}
    ],
    "output_metrics": [
        {"node_id": "S!C1", "label": "Lucro líquido"}
    ],
    "scenario_description": "Reduzir desconto de 10% para 5%",
}


def test_extract_intent_returns_intent_capture():
    """extract_intent com mock retorna IntentCapture válido."""
    messages = [
        {"role": "user", "content": "quero simular o impacto do desconto no lucro"}
    ]
    summary = {
        "workbook_name": "Pasta1",
        "sheets": ["S"],
        "input_candidates": [{"node_id": "S!A1", "current_value": 0.1}],
        "output_candidates": [{"node_id": "S!C1", "formula": "=B1*2"}],
    }
    with patch("intent_extractor.completion", return_value=_mock_completion(_SAMPLE_INTENT_JSON)):
        result = extract_intent(messages=messages, summary=summary)

    assert isinstance(result, IntentCapture)
    assert result.user_goal == "Simular impacto de desconto no lucro"
    assert result.workbook_name == "Pasta1"
    assert len(result.input_parameters) == 1
    assert result.input_parameters[0].node_id == "S!A1"
    assert result.input_parameters[0].suggested_range == [0.0, 0.3]
    assert len(result.output_metrics) == 1
    assert result.output_metrics[0].node_id == "S!C1"


def test_extract_intent_handles_missing_optional_fields():
    """extract_intent funciona sem scenario_description e suggested_range."""
    payload = {
        "user_goal": "Analisar lucro",
        "input_parameters": [{"node_id": "S!A1", "label": "Receita"}],
        "output_metrics": [{"node_id": "S!C1", "label": "Lucro"}],
    }
    with patch("intent_extractor.completion", return_value=_mock_completion(payload)):
        result = extract_intent(
            messages=[{"role": "user", "content": "analisar lucro"}],
            summary={"workbook_name": "WB", "sheets": [], "input_candidates": [], "output_candidates": []},
        )
    assert result.scenario_description is None
    assert result.input_parameters[0].suggested_range is None


def test_build_extraction_prompt_contains_workbook_name():
    """O prompt de extração menciona o nome do workbook."""
    messages = [{"role": "user", "content": "teste"}]
    summary = {"workbook_name": "MinhaPlilha", "sheets": ["Aba1"], "input_candidates": [], "output_candidates": []}
    prompt = build_extraction_prompt(messages, summary)
    assert "MinhaPlilha" in prompt
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

```bash
python -m pytest tests/test_phase_b1.py::test_extract_intent_returns_intent_capture -v
```
Expected: `ModuleNotFoundError: No module named 'intent_extractor'`

- [ ] **Step 3: Implementar `src/phase_b1/intent_extractor.py`**

```python
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
from pipeline_contracts import InputParameter, IntentCapture, OutputMetric

_log = logging.getLogger(__name__)

_EXTRACTION_SCHEMA = """
Retorne APENAS um JSON válido com a seguinte estrutura (sem markdown, sem texto extra):
{
  "user_goal": "<resumo em 1-2 frases do que o usuário quer analisar ou simular>",
  "input_parameters": [
    {
      "node_id": "<coordenada canônica, ex: Planilha1!B5>",
      "label": "<nome legível inferido da conversa>",
      "suggested_range": [<min>, <max>]  // opcional — omitir se não mencionado
    }
  ],
  "output_metrics": [
    {
      "node_id": "<coordenada canônica>",
      "label": "<nome legível>"
    }
  ],
  "scenario_description": "<descrição opcional do cenário>"  // omitir se não mencionado
}
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
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b1.py -v
```
Expected: 14 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/phase_b1/intent_extractor.py tests/test_phase_b1.py
git commit -m "feat(b1): implement intent_extractor — extracts IntentCapture via litellm JSON output"
```

---

## Task 4 — Implementar `chat_loop.py`

**Files:**
- Create: `src/phase_b1/chat_loop.py`
- Test: `tests/test_phase_b1.py` (adicionar)

- [ ] **Step 1: Escrever o teste do chat_loop com mock**

Adicionar ao final de `tests/test_phase_b1.py`:

```python
# ── chat_loop ──────────────────────────────────────────────────────────────

from chat_loop import build_system_prompt, _is_done_signal


def test_is_done_signal_detects_keywords():
    """Palavras-chave de encerramento devem ser detectadas."""
    assert _is_done_signal("ok") is True
    assert _is_done_signal("OK") is True
    assert _is_done_signal("pronto") is True
    assert _is_done_signal("done") is True
    assert _is_done_signal("Pode capturar") is True  # contém "capturar"
    assert _is_done_signal("quero simular mais") is False


def test_build_system_prompt_contains_workbook_name():
    """O system prompt menciona o nome do workbook."""
    summary = {
        "workbook_name": "Pasta1",
        "sheets": ["Planilha1"],
        "input_candidates": [{"node_id": "Planilha1!B5", "current_value": 100}],
        "output_candidates": [{"node_id": "Planilha1!D20", "formula": "=B5*C5"}],
    }
    prompt = build_system_prompt(summary)
    assert "Pasta1" in prompt
    assert "Planilha1!B5" in prompt
    assert "Planilha1!D20" in prompt


def test_run_chat_with_mocked_llm(monkeypatch):
    """
    run_chat com input simulado e LLM mockado deve retornar IntentCapture.
    Simula: usuário digita uma mensagem e depois 'ok'.
    """
    from chat_loop import run_chat

    # Simular input do usuário: primeira mensagem + "ok" para encerrar
    inputs = iter(["quero simular o impacto do desconto no lucro", "ok"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    # Mock da resposta do assistant no loop
    mock_chat_resp = MagicMock()
    mock_chat_resp.choices[0].message.content = "Entendido! Quais valores de desconto quer testar?"

    # Mock da extração final
    mock_extract_resp = MagicMock()
    mock_extract_resp.choices[0].message.content = json.dumps({
        "user_goal": "Simular desconto",
        "input_parameters": [{"node_id": "S!A1", "label": "Desconto"}],
        "output_metrics": [{"node_id": "S!C1", "label": "Lucro"}],
    })

    call_count = {"n": 0}
    def mock_completion(**kwargs):
        call_count["n"] += 1
        # Primeira chamada = chat; segunda = extração
        return mock_chat_resp if call_count["n"] == 1 else mock_extract_resp

    with patch("chat_loop.completion", side_effect=mock_completion):
        with patch("intent_extractor.completion", return_value=mock_extract_resp):
            result = run_chat(
                summary={
                    "workbook_name": "Pasta1",
                    "sheets": ["S"],
                    "input_candidates": [{"node_id": "S!A1", "current_value": 0.1}],
                    "output_candidates": [{"node_id": "S!C1", "formula": "=B1*2"}],
                }
            )
    assert isinstance(result, IntentCapture)
    assert result.workbook_name == "Pasta1"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

```bash
python -m pytest tests/test_phase_b1.py::test_is_done_signal_detects_keywords -v
```
Expected: `ModuleNotFoundError: No module named 'chat_loop'`

- [ ] **Step 3: Implementar `src/phase_b1/chat_loop.py`**

```python
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
from pipeline_contracts import IntentCapture

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
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b1.py -v
```
Expected: 17 tests PASSED.

- [ ] **Step 5: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: 478 passed, 0 failed.

- [ ] **Step 6: Commit**

```bash
git add src/phase_b1/chat_loop.py tests/test_phase_b1.py
git commit -m "feat(b1): implement chat_loop — interactive CLI intent capture with litellm"
```

---

## Task 5 — Entry point `__main__.py` + smoke test de integração

**Files:**
- Create: `src/phase_b1/__main__.py`
- Test: `tests/test_phase_b1.py` (adicionar)

- [ ] **Step 1: Escrever o smoke test do entry point**

Adicionar ao final de `tests/test_phase_b1.py`:

```python
# ── __main__ / integração ─────────────────────────────────────────────────

def test_phase_b1_package_imports_cleanly():
    """O pacote phase_b1 importa sem erros."""
    import phase_b1
    import context_builder
    import intent_extractor
    import chat_loop
    assert True  # chegou aqui = sem ImportError


def test_intent_capture_saved_to_json(tmp_path):
    """IntentCapture serializa para JSON e pode ser recarregado."""
    ic = IntentCapture(
        workbook_name="Pasta1",
        user_goal="Simular desconto",
        input_parameters=[
            InputParameter(node_id="S!A1", label="Desconto", suggested_range=[0.0, 0.3])
        ],
        output_metrics=[OutputMetric(node_id="S!C1", label="Lucro")],
    )
    out_file = tmp_path / "Pasta1_b1_intent.json"
    out_file.write_text(ic.model_dump_json(indent=2), encoding="utf-8")

    loaded = IntentCapture.model_validate_json(out_file.read_text())
    assert loaded.workbook_name == "Pasta1"
    assert loaded.input_parameters[0].suggested_range == [0.0, 0.3]
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

```bash
python -m pytest tests/test_phase_b1.py::test_phase_b1_package_imports_cleanly -v
```
Expected: PASSED (imports já existem) OU `ModuleNotFoundError: No module named 'phase_b1'` se o sys.path não incluir src/phase_b1.

- [ ] **Step 3: Implementar `src/phase_b1/__main__.py`**

```python
"""
EXRS Phase B1 — Entry Point

Uso:
    python -m phase_b1 output/Pasta1

Onde 'output/Pasta1' é o prefixo dos arquivos do pipeline
(sem sufixo _a2_dag.json, _a15_norm.json, etc.).

O resultado é salvo em output/Pasta1_b1_intent.json.
"""
import json
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

# Setup paths
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from context_builder import load_summary_from_prefix
from chat_loop import run_chat


def main(output_prefix: str) -> None:
    print(f"Carregando workbook: {output_prefix}")
    summary = load_summary_from_prefix(output_prefix)

    intent = run_chat(summary)

    out_path = Path(f"{output_prefix}_b1_intent.json")
    out_path.write_text(intent.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n✅ IntentCapture salvo em: {out_path}")
    print(f"   Objetivo: {intent.user_goal}")
    print(f"   Entradas: {len(intent.input_parameters)} parâmetro(s)")
    print(f"   Saídas:   {len(intent.output_metrics)} métrica(s)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m phase_b1 output/<workbook_prefix>")
        sys.exit(1)
    main(sys.argv[1])
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b1.py -v
```
Expected: 19 tests PASSED.

- [ ] **Step 5: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: 480 passed, 0 failed.

- [ ] **Step 6: Commit final**

```bash
git add src/phase_b1/__main__.py tests/test_phase_b1.py
git commit -m "feat(b1): add __main__ entry point — python -m phase_b1 output/<prefix>"
```

---

## Checklist de Self-Review

**1. Spec coverage:**

| Requisito B1 | Task | Coberto? |
|---|---|---|
| Capturar intenção do usuário via chat | Task 4 (chat_loop) | ✅ |
| Identificar células de entrada (inputs) | Task 2 (context_builder) | ✅ |
| Identificar células de saída (outputs) | Task 2 (context_builder) | ✅ |
| Estrutura de dados IntentCapture | Task 1 (pipeline_contracts) | ✅ |
| Extração estruturada via LLM | Task 3 (intent_extractor) | ✅ |
| Persistência em JSON | Task 5 (__main__) | ✅ |
| Testes sem chamadas reais à API | Tasks 1–5 (mocks) | ✅ |
| Entry point CLI | Task 5 | ✅ |

**2. Placeholder scan:** Nenhum TBD, TODO, "similar ao Task N" ou "adicione validação" sem código. Todos os passos têm código completo.

**3. Type consistency:**
- `InputParameter.suggested_range: list[float] | None` — usado igual em Task 1, Task 3 e Task 5.
- `extract_intent(messages, summary)` — assinatura igual em Task 3 (definição) e Task 4 (chamada).
- `build_workbook_summary(dag, norm_ir, workbook_name)` — assinatura igual em Task 2 (definição) e teste.
- `load_summary_from_prefix(output_prefix)` — usado em Task 5 (`__main__.py`), definido em Task 2.

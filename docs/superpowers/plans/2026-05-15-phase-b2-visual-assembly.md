# Phase B2 — Modules (Visual Assembly) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Receber um `IntentCapture` do B1, montar um `StagedRuleGraph` filtrado com os nós computacionais do workbook, e gerar uma visualização HTML interativa com vis.js mostrando o grafo de dependências com inputs/outputs do usuário destacados.

**Architecture:** Três camadas: `graph_assembler` (transforma DAG + IntentCapture → StagedRuleGraph, filtrando para ≤150 nós relevantes), `html_visualizer` (renderiza StagedRuleGraph → HTML self-contained com vis.js hierárquico LR), e `__main__` (entry point que carrega os arquivos e orquestra). O `StagedRuleGraph` stub em `pipeline_contracts.py` é substituído por tipos concretos (`GraphNode`, `GraphEdge`).

**Tech Stack:** Python 3.11+, pydantic v2, vis-network 9.1.9 (CDN — sem build step), json, pathlib. Sem dependências novas no requirements.txt.

---

## Mapa de Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `libs/trustware/pipeline_contracts.py` | Substituir stub `StagedRuleGraph` por `GraphNodeType`, `GraphNode`, `GraphEdge`, `StagedRuleGraph` concreto |
| `src/phase_b2/__init__.py` | Pacote vazio com docstring |
| `src/phase_b2/graph_assembler.py` | Lê DAG + norm_ir + IntentCapture → StagedRuleGraph filtrado (≤150 nós) |
| `src/phase_b2/html_visualizer.py` | StagedRuleGraph → HTML string com vis.js hierárquico LR |
| `src/phase_b2/__main__.py` | `python -m phase_b2 output/Pasta1` — carrega arquivos, monta grafo, salva HTML + JSON |
| `tests/test_phase_b2.py` | Testes unitários de todos os componentes — sem chamadas de rede, sem LLM |

---

## Task 1 — Tipos B2 em `pipeline_contracts.py`

**Files:**
- Modify: `libs/trustware/pipeline_contracts.py` — substituir stub `StagedRuleGraph` (linhas ~191–194)
- Create: `tests/test_phase_b2.py`

- [ ] **Step 1: Criar `tests/test_phase_b2.py`** com os testes dos novos tipos:

```python
"""Testes da Phase B2 — Modules (Visual Assembly)."""
import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in [
    REPO_ROOT / "src" / "phase_b2",
    REPO_ROOT / "libs" / "trustware",
]:
    sys.path.insert(0, str(p))

from pipeline_contracts import (
    GraphNodeType, GraphNode, GraphEdge, StagedRuleGraph,
    InputParameter, OutputMetric, IntentCapture,
)


def _make_intent() -> IntentCapture:
    return IntentCapture(
        workbook_name="TestWB",
        user_goal="Simular desconto",
        input_parameters=[InputParameter(node_id="S!A1", label="Desconto")],
        output_metrics=[OutputMetric(node_id="S!C1", label="Lucro")],
    )


def test_graph_node_type_values():
    assert GraphNodeType.INPUT == "input"
    assert GraphNodeType.OUTPUT == "output"
    assert GraphNodeType.INTERMEDIATE == "intermediate"
    assert GraphNodeType.STATIC == "static"


def test_graph_node_user_flags():
    n = GraphNode(
        id="S!A1", label="Desconto", node_type=GraphNodeType.INPUT,
        is_user_input=True, current_value=0.1,
    )
    assert n.is_user_input is True
    assert n.is_user_output is False
    assert n.formula is None


def test_graph_edge_direction():
    e = GraphEdge(source="S!A1", target="S!B1")
    assert e.source == "S!A1"
    assert e.target == "S!B1"


def test_staged_rule_graph_serialization():
    graph = StagedRuleGraph(
        workbook_name="TestWB",
        nodes=[
            GraphNode(id="S!A1", label="Desc", node_type=GraphNodeType.INPUT, is_user_input=True),
            GraphNode(id="S!C1", label="Lucro", node_type=GraphNodeType.OUTPUT, is_user_output=True,
                      formula="=A1*B1"),
        ],
        edges=[GraphEdge(source="S!A1", target="S!C1")],
        intent=_make_intent(),
    )
    data = graph.model_dump()
    assert data["workbook_name"] == "TestWB"
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["nodes"][0]["is_user_input"] is True
    # Roundtrip
    g2 = StagedRuleGraph.model_validate(data)
    assert g2.nodes[0].id == "S!A1"


def test_staged_rule_graph_timestamp_auto():
    graph = StagedRuleGraph(
        workbook_name="X", nodes=[], edges=[], intent=_make_intent()
    )
    assert graph.generated_at  # não vazio
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

```bash
python -m pytest tests/test_phase_b2.py::test_graph_node_type_values -v
```
Expected: `ImportError: cannot import name 'GraphNodeType'`

- [ ] **Step 3: Substituir o stub `StagedRuleGraph` em `pipeline_contracts.py`**

Localizar as linhas ~191–194 com o stub:
```python
class StagedRuleGraph(BaseModel):
    """Grafo visual de regras de negócio (Fase B2)."""
    rules: List[Dict[str, Any]]
    visual_layout: Dict[str, Any] = Field(..., description="Metadados para renderização visual")
```

Substituir por:

```python
class GraphNodeType(str, Enum):
    """Tipo de nó no grafo visual de regras de negócio."""
    INPUT = "input"               # célula folha (sem dependências)
    OUTPUT = "output"             # fórmula final (sem dependentes)
    INTERMEDIATE = "intermediate" # fórmula com dependentes
    STATIC = "static"             # valor estático fora do caminho crítico


class GraphNode(BaseModel):
    """Nó do grafo visual de regras de negócio — Phase B2."""
    id: str                          # node_id canônico: "Sheet!A1"
    label: str                       # nome legível (label do IntentCapture ou coordenada)
    node_type: GraphNodeType
    formula: str | None = None
    current_value: Any = None
    is_user_input: bool = False      # pinned como parâmetro pelo IntentCapture
    is_user_output: bool = False     # monitorado pelo IntentCapture


class GraphEdge(BaseModel):
    """Aresta dirigida: source alimenta target."""
    source: str  # node_id de origem
    target: str  # node_id de destino


class StagedRuleGraph(BaseModel):
    """Grafo visual de regras de negócio — Phase B2."""
    workbook_name: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    intent: IntentCapture
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

**Atenção:** `IntentCapture` já existe no arquivo acima do stub — a referência é válida. `GraphNodeType` usa `Enum` que já está importado via `from enum import Enum`.

- [ ] **Step 4: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b2.py -v
```
Expected: 5 tests PASSED.

- [ ] **Step 5: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: 484 passed, 0 failed.

- [ ] **Step 6: Commit**

```bash
git add libs/trustware/pipeline_contracts.py tests/test_phase_b2.py
git commit -m "feat(b2): replace StagedRuleGraph stub with concrete GraphNode/GraphEdge types"
```

---

## Task 2 — Implementar `graph_assembler.py`

**Files:**
- Create: `src/phase_b2/__init__.py`
- Create: `src/phase_b2/graph_assembler.py`
- Test: `tests/test_phase_b2.py` (adicionar)

- [ ] **Step 1: Criar `src/phase_b2/__init__.py`**

```python
"""EXRS Phase B2 — Modules (Visual Assembly)."""
```

- [ ] **Step 2: Adicionar testes de `graph_assembler` ao final de `tests/test_phase_b2.py`**

```python
# ── graph_assembler ───────────────────────────────────────────────────────

from graph_assembler import build_graph, _get_label, _filter_nodes


_SAMPLE_DAG = {
    "nodes": [
        {"id": "S!A1", "sheet": "S", "coordinate": "A1", "formula_raw": None, "dependencies": []},
        {"id": "S!A2", "sheet": "S", "coordinate": "A2", "formula_raw": None, "dependencies": []},
        {"id": "S!B1", "sheet": "S", "coordinate": "B1", "formula_raw": "=A1+A2",
         "dependencies": ["S!A1", "S!A2"]},
        {"id": "S!C1", "sheet": "S", "coordinate": "C1", "formula_raw": "=B1*2",
         "dependencies": ["S!B1"]},
    ],
    "edges": [],
    "topological_order": ["S!A1", "S!A2", "S!B1", "S!C1"],
}

_SAMPLE_NORM_IR = {
    "file_path": "test.xlsx",
    "sheets": [{
        "name": "S", "index": 0, "state": "visible",
        "cells": [
            {"coordinate": "A1", "formula_raw": None, "value_static": 0.1, "data_type": "n"},
            {"coordinate": "A2", "formula_raw": None, "value_static": 200, "data_type": "n"},
            {"coordinate": "B1", "formula_raw": "=A1+A2", "value_static": None, "data_type": "n"},
            {"coordinate": "C1", "formula_raw": "=B1*2", "value_static": None, "data_type": "n"},
        ],
    }],
}

_SAMPLE_INTENT = IntentCapture(
    workbook_name="TestWB",
    user_goal="Simular impacto do desconto",
    input_parameters=[InputParameter(node_id="S!A1", label="Taxa de desconto")],
    output_metrics=[OutputMetric(node_id="S!C1", label="Lucro líquido")],
)


def test_get_label_uses_intent_label():
    assert _get_label("S!A1", _SAMPLE_INTENT) == "Taxa de desconto"
    assert _get_label("S!C1", _SAMPLE_INTENT) == "Lucro líquido"


def test_get_label_falls_back_to_coordinate():
    assert _get_label("S!B1", _SAMPLE_INTENT) == "B1"


def test_filter_nodes_includes_formula_nodes():
    filtered = _filter_nodes(_SAMPLE_DAG["nodes"], _SAMPLE_INTENT)
    ids = [n["id"] for n in filtered]
    assert "S!B1" in ids  # tem fórmula
    assert "S!C1" in ids  # tem fórmula


def test_filter_nodes_includes_user_inputs_even_if_static():
    filtered = _filter_nodes(_SAMPLE_DAG["nodes"], _SAMPLE_INTENT)
    ids = [n["id"] for n in filtered]
    assert "S!A1" in ids  # user input, mesmo sendo estático


def test_filter_nodes_excludes_unrelated_statics():
    filtered = _filter_nodes(_SAMPLE_DAG["nodes"], _SAMPLE_INTENT)
    ids = [n["id"] for n in filtered]
    assert "S!A2" not in ids  # estático, não selecionado pelo usuário


def test_build_graph_returns_staged_rule_graph():
    graph = build_graph(_SAMPLE_DAG, _SAMPLE_NORM_IR, _SAMPLE_INTENT)
    assert isinstance(graph, StagedRuleGraph)
    assert graph.workbook_name == "TestWB"


def test_build_graph_marks_user_input():
    graph = build_graph(_SAMPLE_DAG, _SAMPLE_NORM_IR, _SAMPLE_INTENT)
    a1 = next(n for n in graph.nodes if n.id == "S!A1")
    assert a1.is_user_input is True
    assert a1.node_type == GraphNodeType.INPUT


def test_build_graph_marks_user_output():
    graph = build_graph(_SAMPLE_DAG, _SAMPLE_NORM_IR, _SAMPLE_INTENT)
    c1 = next(n for n in graph.nodes if n.id == "S!C1")
    assert c1.is_user_output is True


def test_build_graph_edges_connect_dependencies():
    graph = build_graph(_SAMPLE_DAG, _SAMPLE_NORM_IR, _SAMPLE_INTENT)
    edge_pairs = {(e.source, e.target) for e in graph.edges}
    assert ("S!B1", "S!C1") in edge_pairs


def test_build_graph_node_has_current_value():
    graph = build_graph(_SAMPLE_DAG, _SAMPLE_NORM_IR, _SAMPLE_INTENT)
    a1 = next(n for n in graph.nodes if n.id == "S!A1")
    assert a1.current_value == 0.1
```

- [ ] **Step 3: Rodar e confirmar que FALHA**

```bash
python -m pytest tests/test_phase_b2.py::test_get_label_uses_intent_label -v
```
Expected: `ModuleNotFoundError: No module named 'graph_assembler'`

- [ ] **Step 4: Criar `src/phase_b2/graph_assembler.py`**

```python
"""
EXRS Phase B2 — Graph Assembler

Constrói um StagedRuleGraph filtrado a partir do DAG do pipeline e do IntentCapture do B1.
Filtra para ≤150 nós: todos os nós com fórmula + nós selecionados pelo usuário.
"""
import json
import logging
from pathlib import Path

from pipeline_contracts import (
    GraphEdge, GraphNode, GraphNodeType, IntentCapture, StagedRuleGraph,
)

_log = logging.getLogger(__name__)
_MAX_NODES = 150


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


def _get_label(node_id: str, intent: IntentCapture) -> str:
    """Retorna o label do IntentCapture se disponível, senão a coordenada."""
    for p in intent.input_parameters:
        if p.node_id == node_id:
            return p.label
    for m in intent.output_metrics:
        if m.node_id == node_id:
            return m.label
    return node_id.split("!")[-1] if "!" in node_id else node_id


def _filter_nodes(dag_nodes: list[dict], intent: IntentCapture) -> list[dict]:
    """
    Retorna nós relevantes para a visualização (≤ _MAX_NODES):
    - Todos os nós com fórmula (nós computacionais)
    - Nós selecionados pelo usuário (inputs/outputs), mesmo se estáticos
    Prioridade: user-selected primeiro, depois fórmulas.
    """
    user_ids = (
        {p.node_id for p in intent.input_parameters}
        | {m.node_id for m in intent.output_metrics}
    )
    user_nodes = [n for n in dag_nodes if n["id"] in user_ids]
    formula_nodes = [n for n in dag_nodes if n.get("formula_raw") and n["id"] not in user_ids]
    combined = user_nodes + formula_nodes
    if len(combined) > _MAX_NODES:
        _log.warning("Grafo com %d nós — truncando para %d", len(combined), _MAX_NODES)
    return combined[:_MAX_NODES]


def build_graph(dag: dict, norm_ir: dict, intent: IntentCapture) -> StagedRuleGraph:
    """
    Constrói um StagedRuleGraph filtrado e anotado.

    Args:
        dag: dict deserializado do _a2_dag.json
        norm_ir: dict deserializado do _a15_norm.json
        intent: IntentCapture produzido pela Phase B1

    Returns:
        StagedRuleGraph com nós coloridos por tipo e arestas filtradas.
    """
    user_input_ids = {p.node_id for p in intent.input_parameters}
    user_output_ids = {m.node_id for m in intent.output_metrics}

    # Identificar quais nós são dependência de algum outro (não são raiz)
    all_dep_ids: set[str] = set()
    for node in dag["nodes"]:
        all_dep_ids.update(node.get("dependencies", []))

    filtered = _filter_nodes(dag["nodes"], intent)
    filtered_ids = {n["id"] for n in filtered}

    graph_nodes: list[GraphNode] = []
    for node in filtered:
        nid = node["id"]
        has_formula = bool(node.get("formula_raw"))
        is_depended_on = nid in all_dep_ids

        if nid in user_input_ids:
            ntype = GraphNodeType.INPUT
        elif nid in user_output_ids:
            ntype = GraphNodeType.OUTPUT
        elif has_formula and not is_depended_on:
            ntype = GraphNodeType.OUTPUT       # fórmula raiz não selecionada
        elif has_formula:
            ntype = GraphNodeType.INTERMEDIATE
        else:
            ntype = GraphNodeType.STATIC

        graph_nodes.append(GraphNode(
            id=nid,
            label=_get_label(nid, intent),
            node_type=ntype,
            formula=node.get("formula_raw"),
            current_value=_get_cell_value(norm_ir, nid),
            is_user_input=nid in user_input_ids,
            is_user_output=nid in user_output_ids,
        ))

    # Arestas: apenas entre nós presentes no grafo filtrado
    graph_edges: list[GraphEdge] = [
        GraphEdge(source=dep, target=node["id"])
        for node in dag["nodes"]
        if node["id"] in filtered_ids
        for dep in node.get("dependencies", [])
        if dep in filtered_ids
    ]

    return StagedRuleGraph(
        workbook_name=intent.workbook_name,
        nodes=graph_nodes,
        edges=graph_edges,
        intent=intent,
    )


def load_graph_from_prefix(output_prefix: str) -> tuple[StagedRuleGraph, dict, dict]:
    """
    Carrega DAG + norm_ir de um prefixo e retorna (StagedRuleGraph, dag, norm_ir).
    Requer que o _b1_intent.json exista (produzido pela Phase B1).
    """
    dag_path = Path(f"{output_prefix}_a2_dag.json")
    norm_path = Path(f"{output_prefix}_a15_norm.json")
    intent_path = Path(f"{output_prefix}_b1_intent.json")

    for p in [dag_path, norm_path, intent_path]:
        if not p.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {p}")

    with open(dag_path, encoding="utf-8") as f:
        dag = json.load(f)
    with open(norm_path, encoding="utf-8") as f:
        norm_ir = json.load(f)
    with open(intent_path, encoding="utf-8") as f:
        intent = IntentCapture.model_validate_json(f.read())

    return build_graph(dag, norm_ir, intent), dag, norm_ir
```

- [ ] **Step 5: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b2.py -v
```
Expected: 15 tests PASSED (5 tipos + 10 assembler).

- [ ] **Step 6: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: 494 passed, 0 failed.

- [ ] **Step 7: Commit**

```bash
git add src/phase_b2/__init__.py src/phase_b2/graph_assembler.py tests/test_phase_b2.py
git commit -m "feat(b2): implement graph_assembler — filters DAG to ≤150 nodes, builds StagedRuleGraph"
```

---

## Task 3 — Implementar `html_visualizer.py`

**Files:**
- Create: `src/phase_b2/html_visualizer.py`
- Test: `tests/test_phase_b2.py` (adicionar)

- [ ] **Step 1: Adicionar testes ao final de `tests/test_phase_b2.py`**

```python
# ── html_visualizer ───────────────────────────────────────────────────────

from html_visualizer import generate_html, _node_color


_SAMPLE_GRAPH = StagedRuleGraph(
    workbook_name="TestWB",
    nodes=[
        GraphNode(id="S!A1", label="Desconto", node_type=GraphNodeType.INPUT,
                  is_user_input=True, current_value=0.1),
        GraphNode(id="S!B1", label="B1", node_type=GraphNodeType.INTERMEDIATE,
                  formula="=A1+A2"),
        GraphNode(id="S!C1", label="Lucro", node_type=GraphNodeType.OUTPUT,
                  is_user_output=True, formula="=B1*2"),
    ],
    edges=[
        GraphEdge(source="S!A1", target="S!B1"),
        GraphEdge(source="S!B1", target="S!C1"),
    ],
    intent=_SAMPLE_INTENT,
)


def test_node_color_by_type():
    assert _node_color(GraphNodeType.INPUT) != _node_color(GraphNodeType.OUTPUT)
    assert _node_color(GraphNodeType.INTERMEDIATE) != _node_color(GraphNodeType.INPUT)
    # Retorna string de cor hex
    assert _node_color(GraphNodeType.INPUT).startswith("#")


def test_generate_html_is_valid_html():
    html = generate_html(_SAMPLE_GRAPH)
    assert html.strip().startswith("<!DOCTYPE html>")
    assert "<html" in html
    assert "</html>" in html


def test_generate_html_includes_visjs():
    html = generate_html(_SAMPLE_GRAPH)
    assert "vis-network" in html


def test_generate_html_includes_workbook_name():
    html = generate_html(_SAMPLE_GRAPH)
    assert "TestWB" in html


def test_generate_html_includes_user_goal():
    html = generate_html(_SAMPLE_GRAPH)
    assert "Simular impacto do desconto" in html


def test_generate_html_includes_node_ids():
    html = generate_html(_SAMPLE_GRAPH)
    assert "S!A1" in html
    assert "S!C1" in html


def test_generate_html_includes_edges():
    html = generate_html(_SAMPLE_GRAPH)
    # As arestas devem estar no JSON de edges do vis.js
    assert '"from"' in html or "from:" in html


def test_generate_html_save_to_file(tmp_path):
    from html_visualizer import save_html
    out = tmp_path / "graph.html"
    save_html(_SAMPLE_GRAPH, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "TestWB" in content
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

```bash
python -m pytest tests/test_phase_b2.py::test_generate_html_is_valid_html -v
```
Expected: `ModuleNotFoundError: No module named 'html_visualizer'`

- [ ] **Step 3: Criar `src/phase_b2/html_visualizer.py`**

```python
"""
EXRS Phase B2 — HTML Visualizer

Gera uma visualização HTML self-contained do StagedRuleGraph usando vis-network.
Layout hierárquico LR: inputs à esquerda, outputs à direita.
Sem dependências além do vis-network via CDN.
"""
import json
import logging
from pathlib import Path

from pipeline_contracts import GraphNodeType, StagedRuleGraph

_log = logging.getLogger(__name__)

_VIS_CDN = "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/dist/vis-network.min.js"

# Paleta: alinhada com as CSS vars do html_reporter.py existente
_COLORS: dict[GraphNodeType, dict] = {
    GraphNodeType.INPUT: {
        "background": "#FEF3C7", "border": "#D97706",
        "highlight": {"background": "#FDE68A", "border": "#B45309"},
    },
    GraphNodeType.OUTPUT: {
        "background": "#D1FAE5", "border": "#059669",
        "highlight": {"background": "#A7F3D0", "border": "#047857"},
    },
    GraphNodeType.INTERMEDIATE: {
        "background": "#DBEAFE", "border": "#2563EB",
        "highlight": {"background": "#BFDBFE", "border": "#1D4ED8"},
    },
    GraphNodeType.STATIC: {
        "background": "#F3F4F6", "border": "#9CA3AF",
        "highlight": {"background": "#E5E7EB", "border": "#6B7280"},
    },
}


def _node_color(node_type: GraphNodeType) -> str:
    """Retorna a cor de borda para um tipo de nó (usada nos testes)."""
    return _COLORS[node_type]["border"]


def _vis_nodes(graph: StagedRuleGraph) -> list[dict]:
    """Converte GraphNodes para o formato de nós do vis.js."""
    nodes = []
    for n in graph.nodes:
        tooltip_parts = [f"<b>{n.id}</b>"]
        if n.formula:
            tooltip_parts.append(f"Fórmula: <code>{n.formula}</code>")
        if n.current_value is not None:
            tooltip_parts.append(f"Valor: {n.current_value}")
        if n.is_user_input:
            tooltip_parts.append("<i>📥 Parâmetro de entrada</i>")
        if n.is_user_output:
            tooltip_parts.append("<i>📤 Métrica monitorada</i>")

        node_dict = {
            "id": n.id,
            "label": n.label,
            "title": "<br/>".join(tooltip_parts),
            "color": _COLORS[n.node_type],
            "font": {"size": 13, "face": "monospace" if not (n.is_user_input or n.is_user_output) else "sans-serif"},
            "borderWidth": 3 if (n.is_user_input or n.is_user_output) else 1,
            "shadow": n.is_user_input or n.is_user_output,
        }
        nodes.append(node_dict)
    return nodes


def _vis_edges(graph: StagedRuleGraph) -> list[dict]:
    """Converte GraphEdges para o formato de arestas do vis.js."""
    return [
        {
            "from": e.source,
            "to": e.target,
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
            "color": {"color": "#CBD5E1", "highlight": "#94A3B8"},
            "smooth": {"type": "cubicBezier"},
        }
        for e in graph.edges
    ]


def generate_html(graph: StagedRuleGraph) -> str:
    """
    Gera uma string HTML self-contained com a visualização do StagedRuleGraph.

    Args:
        graph: StagedRuleGraph produzido pelo graph_assembler

    Returns:
        String HTML completa, pronta para salvar em arquivo.
    """
    vis_nodes_json = json.dumps(_vis_nodes(graph), ensure_ascii=False, indent=2)
    vis_edges_json = json.dumps(_vis_edges(graph), ensure_ascii=False, indent=2)

    intent = graph.intent
    inputs_html = "".join(
        f'<li><code>{p.node_id}</code> — {p.label}'
        + (f' <span class="range">[{p.suggested_range[0]}, {p.suggested_range[1]}]</span>'
           if p.suggested_range else "")
        + "</li>"
        for p in intent.input_parameters
    ) or "<li><em>Nenhum selecionado</em></li>"

    outputs_html = "".join(
        f'<li><code>{m.node_id}</code> — {m.label}</li>'
        for m in intent.output_metrics
    ) or "<li><em>Nenhum selecionado</em></li>"

    legend_html = "".join(
        f'<span class="leg-item"><span class="leg-dot" style="background:{_COLORS[t]["background"]};border:2px solid {_COLORS[t]["border"]}"></span>{label}</span>'
        for t, label in [
            (GraphNodeType.INPUT, "Entrada"),
            (GraphNodeType.OUTPUT, "Saída"),
            (GraphNodeType.INTERMEDIATE, "Intermediário"),
            (GraphNodeType.STATIC, "Estático"),
        ]
    )

    node_count = len(graph.nodes)
    edge_count = len(graph.edges)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>EXRS B2 — {graph.workbook_name}</title>
  <script src="{_VIS_CDN}"></script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#F1F5F9;color:#1E293B;display:flex;height:100vh;overflow:hidden}}
    #sidebar{{width:300px;min-width:220px;background:#1E293B;color:#F8FAFC;padding:24px 18px;overflow-y:auto;flex-shrink:0}}
    #sidebar h1{{font-size:15px;font-weight:700;letter-spacing:-.2px;margin-bottom:4px;color:#F8FAFC}}
    #sidebar .sub{{font-size:11px;color:#94A3B8;margin-bottom:16px}}
    #sidebar h2{{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:#94A3B8;margin:16px 0 6px}}
    #sidebar .goal{{font-size:13px;color:#CBD5E1;line-height:1.5;background:#0F172A;padding:10px;border-radius:6px}}
    #sidebar ul{{list-style:none;padding:0}}
    #sidebar ul li{{font-size:12px;color:#CBD5E1;padding:4px 0;border-bottom:1px solid #334155}}
    #sidebar ul li code{{background:#334155;padding:1px 4px;border-radius:3px;font-size:11px;color:#93C5FD}}
    .range{{color:#FCD34D;font-size:11px}}
    #main{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
    #toolbar{{background:#fff;border-bottom:1px solid #E2E8F0;padding:10px 16px;display:flex;align-items:center;gap:16px;font-size:12px;color:#64748B}}
    .leg-item{{display:inline-flex;align-items:center;gap:5px}}
    .leg-dot{{width:14px;height:14px;border-radius:3px;display:inline-block}}
    .stats{{margin-left:auto;color:#94A3B8}}
    #network{{flex:1}}
  </style>
</head>
<body>
  <div id="sidebar">
    <h1>📊 {graph.workbook_name}</h1>
    <div class="sub">Phase B2 — Visual Assembly</div>
    <h2>Intenção</h2>
    <div class="goal">{intent.user_goal}</div>
    <h2>Entradas</h2>
    <ul>{inputs_html}</ul>
    <h2>Saídas</h2>
    <ul>{outputs_html}</ul>
    {f'<h2>Cenário</h2><div class="goal">{intent.scenario_description}</div>' if intent.scenario_description else ''}
  </div>
  <div id="main">
    <div id="toolbar">
      {legend_html}
      <span class="stats">{node_count} nós · {edge_count} arestas</span>
    </div>
    <div id="network"></div>
  </div>
  <script>
    const nodes = new vis.DataSet({vis_nodes_json});
    const edges = new vis.DataSet({vis_edges_json});
    const container = document.getElementById('network');
    const options = {{
      layout: {{
        hierarchical: {{
          enabled: true,
          direction: 'LR',
          sortMethod: 'directed',
          levelSeparation: 180,
          nodeSpacing: 120,
          treeSpacing: 200,
        }}
      }},
      nodes: {{shape: 'box', margin: 8, widthConstraint: {{maximum: 160}}}},
      edges: {{smooth: {{type: 'cubicBezier', forceDirection: 'horizontal'}}}},
      physics: {{enabled: false}},
      interaction: {{hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true}},
    }};
    new vis.Network(container, {{nodes, edges}}, options);
  </script>
</body>
</html>"""


def save_html(graph: StagedRuleGraph, output_path: "str | Path") -> None:
    """Gera e salva a visualização HTML em um arquivo."""
    Path(output_path).write_text(generate_html(graph), encoding="utf-8")
    _log.info("Visualização salva em: %s", output_path)
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b2.py -v
```
Expected: 23 tests PASSED (15 anteriores + 8 novos).

- [ ] **Step 5: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: 502 passed, 0 failed.

- [ ] **Step 6: Commit**

```bash
git add src/phase_b2/html_visualizer.py tests/test_phase_b2.py
git commit -m "feat(b2): implement html_visualizer — vis.js hierarchical LR graph with intent sidebar"
```

---

## Task 4 — Entry point `__main__.py` + smoke test de integração

**Files:**
- Create: `src/phase_b2/__main__.py`
- Test: `tests/test_phase_b2.py` (adicionar)

- [ ] **Step 1: Adicionar smoke tests ao final de `tests/test_phase_b2.py`**

```python
# ── __main__ / integração ─────────────────────────────────────────────────

def test_phase_b2_package_imports_cleanly():
    import phase_b2
    import graph_assembler
    import html_visualizer
    assert True


def test_full_pipeline_mock(tmp_path):
    """Pipeline completo: DAG + norm_ir + intent → HTML + JSON."""
    import json
    from graph_assembler import build_graph
    from html_visualizer import save_html

    dag_file = tmp_path / "test_a2_dag.json"
    norm_file = tmp_path / "test_a15_norm.json"
    intent_file = tmp_path / "test_b1_intent.json"

    dag_file.write_text(json.dumps(_SAMPLE_DAG), encoding="utf-8")
    norm_file.write_text(json.dumps(_SAMPLE_NORM_IR), encoding="utf-8")
    intent_file.write_text(_SAMPLE_INTENT.model_dump_json(), encoding="utf-8")

    graph = build_graph(_SAMPLE_DAG, _SAMPLE_NORM_IR, _SAMPLE_INTENT)
    assert len(graph.nodes) >= 1

    html_out = tmp_path / "test_b2_graph.html"
    save_html(graph, html_out)
    assert html_out.exists()
    html_content = html_out.read_text(encoding="utf-8")
    assert "TestWB" in html_content
    assert "vis-network" in html_content

    json_out = tmp_path / "test_b2_graph.json"
    json_out.write_text(graph.model_dump_json(indent=2), encoding="utf-8")
    reloaded = StagedRuleGraph.model_validate_json(json_out.read_text())
    assert reloaded.workbook_name == "TestWB"
```

- [ ] **Step 2: Rodar e confirmar que os smoke tests PASSAM** (módulos já existem):

```bash
python -m pytest tests/test_phase_b2.py::test_phase_b2_package_imports_cleanly -v
python -m pytest tests/test_phase_b2.py::test_full_pipeline_mock -v
```
Expected: ambos PASSED.

- [ ] **Step 3: Criar `src/phase_b2/__main__.py`**

```python
"""
EXRS Phase B2 — Entry Point

Uso:
    python -m phase_b2 output/Pasta1

Requer que os seguintes arquivos existam:
  output/Pasta1_a2_dag.json       (Phase A2)
  output/Pasta1_a15_norm.json     (Phase A1.5)
  output/Pasta1_b1_intent.json    (Phase B1)

Produz:
  output/Pasta1_b2_graph.json     (StagedRuleGraph serializado)
  output/Pasta1_b2_graph.html     (Visualização interativa vis.js)
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from graph_assembler import load_graph_from_prefix
from html_visualizer import save_html


def main(output_prefix: str) -> None:
    print(f"Carregando pipeline outputs: {output_prefix}")
    graph, _, _ = load_graph_from_prefix(output_prefix)

    json_out = Path(f"{output_prefix}_b2_graph.json")
    html_out = Path(f"{output_prefix}_b2_graph.html")

    json_out.write_text(graph.model_dump_json(indent=2), encoding="utf-8")
    save_html(graph, html_out)

    print(f"\n✅ Grafo montado: {len(graph.nodes)} nós, {len(graph.edges)} arestas")
    print(f"   JSON : {json_out}")
    print(f"   HTML : {html_out}")
    print(f"\n   Abra {html_out} no browser para visualizar o grafo interativo.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m phase_b2 output/<workbook_prefix>")
        sys.exit(1)
    main(sys.argv[1])
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b2.py -v
```
Expected: 25 tests PASSED.

- [ ] **Step 5: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: 504 passed, 0 failed.

- [ ] **Step 6: Commit e push**

```bash
git add src/phase_b2/__main__.py tests/test_phase_b2.py
git commit -m "feat(b2): add __main__ entry point — python -m phase_b2 output/<prefix>"
git push
```

---

## Checklist de Self-Review

**1. Spec coverage:**

| Requisito B2 | Task | Coberto? |
|---|---|---|
| Receber IntentCapture do B1 | Task 2 (graph_assembler) | ✅ |
| Montar StagedRuleGraph com nós do DAG | Task 2 | ✅ |
| Filtrar para ≤150 nós relevantes | Task 2 (`_filter_nodes`) | ✅ |
| Marcar user inputs/outputs com flags | Task 2 | ✅ |
| Tipos concretos `GraphNode`, `GraphEdge` | Task 1 | ✅ |
| Visualização HTML interativa | Task 3 (html_visualizer) | ✅ |
| vis.js hierárquico LR (inputs → outputs) | Task 3 | ✅ |
| Sidebar com intenção do usuário | Task 3 | ✅ |
| Tooltips com fórmula e valor atual | Task 3 | ✅ |
| Salvar JSON + HTML | Task 4 (__main__) | ✅ |
| Entry point CLI | Task 4 | ✅ |
| Testes sem chamadas de rede | Tasks 1–4 (todos mock/local) | ✅ |

**2. Placeholder scan:** Nenhum TBD, TODO ou "similar ao Task N". Todos os passos têm código completo.

**3. Type consistency:**
- `GraphNode.node_type: GraphNodeType` — igual em Task 1 (definição), Task 2 (uso em `build_graph`), Task 3 (uso em `_node_color` e `_vis_nodes`).
- `StagedRuleGraph.nodes: list[GraphNode]` — igual em Tasks 1, 2, 3, 4.
- `load_graph_from_prefix(output_prefix)` retorna `tuple[StagedRuleGraph, dict, dict]` — definido em Task 2, usado em Task 4.
- `save_html(graph, output_path)` — definido em Task 3, usado em Task 4 e no smoke test.

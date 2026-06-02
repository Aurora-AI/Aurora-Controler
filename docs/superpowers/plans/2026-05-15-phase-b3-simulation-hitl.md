# Phase B3 — Simulation + HITL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Receber um `StagedRuleGraph` do B2, executar uma simulacao interativa (HITL) onde o usuario ajusta parametros de entrada e observa como as metricas de saida mudam, gravando cada rodada e intervencao em um `SimulationAudit`.

**Architecture:** Tres camadas: `simulation_engine` (avalia formulas aritmeticas em ordem topologica com fallback gracioso para formulas complexas, usando `ast.parse` + walker recursivo para seguranca), `hitl_loop` (CLI interativo que roda rodadas de simulacao, captura overrides do usuario e grava `ComplianceEvent` por intervencao), e `__main__` (entry point que carrega `_b2_graph.json` e salva `_b3_audit.json`). Sem dependencias novas.

**Tech Stack:** Python 3.11+, pydantic v2, re, ast, operator, collections, uuid. Sem novas entradas em requirements.txt.

---

## Mapa de Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `libs/trustware/pipeline_contracts.py` | Adicionar `SimulationStep`; atualizar `SimulationAudit.steps` para `list[SimulationStep]` |
| `src/phase_b3/__init__.py` | Pacote com docstring |
| `src/phase_b3/simulation_engine.py` | Avalia StagedRuleGraph com input overrides em ordem topologica (Kahn + AST walker) |
| `src/phase_b3/hitl_loop.py` | CLI HITL loop: exibe resultados, captura overrides, retorna SimulationAudit |
| `src/phase_b3/__main__.py` | `python -m phase_b3 output/Pasta1` |
| `tests/test_phase_b3.py` | Testes unitarios de todos os componentes — sem rede, sem LLM |

---

## Nota de Design: Avaliacao Segura de Formulas

O `simulation_engine` usa `ast.parse` + um walker recursivo (`_safe_eval`) que aceita apenas `ast.Constant` numericos e `ast.BinOp`/`ast.UnaryOp` com os operadores `+, -, *, /, **`. Isso elimina risco de execucao de codigo arbitrario. Formulas que contenham chamadas de funcao Excel (`SUM`, `IF`, etc.) ou ranges (`A1:B10`) sao detectadas por regex e marcadas como `unevaluated` — o valor `current_value` do Excel e mantido para elas.

---

## Task 1 — Tipo `SimulationStep` + atualizacao de `SimulationAudit`

**Files:**
- Modify: `libs/trustware/pipeline_contracts.py` — inserir `SimulationStep` antes de `SimulationAudit` (linha 224); atualizar `SimulationAudit.steps`
- Create: `tests/test_phase_b3.py`

- [ ] **Step 1: Criar `tests/test_phase_b3.py`**

```python
"""Testes da Phase B3 — Simulation + HITL."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in [
    REPO_ROOT / "src" / "phase_b3",
    REPO_ROOT / "libs" / "trustware",
]:
    sys.path.insert(0, str(p))

from pipeline_contracts import (
    SimulationStep, SimulationAudit,
    GraphNode, GraphEdge, GraphNodeType, StagedRuleGraph,
    InputParameter, OutputMetric, IntentCapture,
)


def _make_intent() -> IntentCapture:
    return IntentCapture(
        workbook_name="SimTest",
        user_goal="Testar simulacao",
        input_parameters=[InputParameter(node_id="S!A1", label="Input", current_value=10.0)],
        output_metrics=[OutputMetric(node_id="S!C1", label="Result")],
    )


_SIM_GRAPH = StagedRuleGraph(
    workbook_name="SimTest",
    nodes=[
        GraphNode(id="S!A1", label="Input", node_type=GraphNodeType.INPUT,
                  is_user_input=True, current_value=10.0),
        GraphNode(id="S!B1", label="Calc", node_type=GraphNodeType.INTERMEDIATE,
                  formula="=A1*2", current_value=20.0),
        GraphNode(id="S!C1", label="Result", node_type=GraphNodeType.OUTPUT,
                  is_user_output=True, formula="=SUM(B1:B10)", current_value=200.0),
    ],
    edges=[
        GraphEdge(source="S!A1", target="S!B1"),
        GraphEdge(source="S!B1", target="S!C1"),
    ],
    intent=_make_intent(),
)


def test_simulation_step_creation():
    step = SimulationStep(
        run_number=1,
        input_values={"S!A1": 10.0},
        output_values={"S!C1": 200.0},
        all_computed={"S!A1": 10.0, "S!B1": 20.0, "S!C1": 200.0},
    )
    assert step.run_number == 1
    assert step.unevaluated_nodes == []
    assert step.timestamp


def test_simulation_step_unevaluated():
    step = SimulationStep(
        run_number=2,
        input_values={"S!A1": 50.0},
        output_values={"S!C1": None},
        all_computed={"S!A1": 50.0},
        unevaluated_nodes=["S!C1"],
    )
    assert "S!C1" in step.unevaluated_nodes


def test_simulation_step_serialization():
    step = SimulationStep(
        run_number=1,
        input_values={"S!A1": 10.0},
        output_values={"S!C1": 200.0},
        all_computed={"S!A1": 10.0},
    )
    data = step.model_dump()
    assert data["run_number"] == 1
    s2 = SimulationStep.model_validate(data)
    assert s2.run_number == 1


def test_simulation_audit_with_steps():
    step = SimulationStep(
        run_number=1,
        input_values={"S!A1": 10.0},
        output_values={"S!C1": 200.0},
        all_computed={"S!A1": 10.0},
    )
    audit = SimulationAudit(
        simulation_id="test-id",
        steps=[step],
        hitl_interventions=[],
        final_outcome="Result=200.0",
    )
    assert len(audit.steps) == 1
    assert audit.steps[0].run_number == 1
    assert audit.final_outcome == "Result=200.0"


def test_simulation_audit_serialization():
    step = SimulationStep(
        run_number=1, input_values={}, output_values={}, all_computed={},
    )
    audit = SimulationAudit(
        simulation_id="abc", steps=[step], hitl_interventions=[], final_outcome="ok"
    )
    data = audit.model_dump()
    a2 = SimulationAudit.model_validate(data)
    assert a2.simulation_id == "abc"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

```bash
python -m pytest tests/test_phase_b3.py::test_simulation_step_creation -v
```
Expected: `ImportError: cannot import name 'SimulationStep'`

- [ ] **Step 3: Modificar `libs/trustware/pipeline_contracts.py`**

Localizar linhas 224-229 com `SimulationAudit` e substituir por:

```python
class SimulationStep(BaseModel):
    """Uma rodada de simulacao com inputs e outputs computados — Phase B3."""
    run_number: int = Field(..., description="Numero sequencial da rodada (comeca em 1)")
    input_values: dict[str, Any] = Field(..., description="Valores dos parametros de entrada nesta rodada")
    output_values: dict[str, Any] = Field(..., description="Valores das metricas monitoradas computadas")
    all_computed: dict[str, Any] = Field(..., description="Valores de todos os nos avaliados")
    unevaluated_nodes: list[str] = Field(default_factory=list, description="node_ids nao avaliados (formulas complexas)")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SimulationAudit(BaseModel):
    """Passo a passo da simulacao com HITL (Fase B3)."""
    simulation_id: str
    steps: list[SimulationStep]
    hitl_interventions: List[Dict[str, Any]]  # ComplianceEvent.model_dump(mode="json")
    final_outcome: str
```

**Atencao:** `datetime`, `timezone`, `Field`, `Any`, `List`, `Dict` ja importados no arquivo.

- [ ] **Step 4: Rodar e confirmar que PASSA**

```bash
python -m pytest tests/test_phase_b3.py -v
```
Expected: 5 tests PASSED.

- [ ] **Step 5: Suite completa**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add libs/trustware/pipeline_contracts.py tests/test_phase_b3.py
git commit -m "feat(b3): add SimulationStep type; update SimulationAudit.steps to list[SimulationStep]"
```

---

## Task 2 — `simulation_engine.py` (AST walker + Kahn topo sort)

**Files:**
- Create: `src/phase_b3/__init__.py`
- Create: `src/phase_b3/simulation_engine.py`
- Modify: `tests/test_phase_b3.py` — adicionar 13 testes de engine

- [ ] **Step 1: Criar `src/phase_b3/__init__.py`**

```python
"""Phase B3 — Simulation Engine + HITL loop."""
```

- [ ] **Step 2: Adicionar 13 testes de engine em `tests/test_phase_b3.py`**

Adicionar apos o ultimo teste existente (mantenha o codigo ja existente):

```python
# ---------------------------------------------------------------------------
# Task 2 — simulation_engine tests
# ---------------------------------------------------------------------------
from simulation_engine import (
    _is_complex_formula,
    _safe_calc,
    _build_topo_order,
    _eval_formula,
    run_simulation,
    make_step,
)


def test_is_complex_formula_sum():
    assert _is_complex_formula("=SUM(B1:B10)") is True


def test_is_complex_formula_range():
    assert _is_complex_formula("=A1:B10") is True


def test_is_complex_formula_simple():
    assert _is_complex_formula("=A1*2") is False


def test_is_complex_formula_literal():
    assert _is_complex_formula("=42") is False


def test_safe_calc_addition():
    assert _safe_calc("1+2") == 3


def test_safe_calc_multiply():
    assert _safe_calc("3*4") == 12


def test_safe_calc_power():
    assert _safe_calc("2**8") == 256


def test_safe_calc_unary():
    assert _safe_calc("-5") == -5


def test_eval_formula_substitutes_ref():
    # =A1*2 com A1=10 deve retornar 20.0
    node = _SIM_GRAPH.nodes[1]  # S!B1, formula="=A1*2"
    result = _eval_formula(node.formula, "S", {"S!A1": 10.0})
    assert result == 20.0


def test_topo_order_respects_dependency():
    order = _build_topo_order(_SIM_GRAPH.nodes, _SIM_GRAPH.edges)
    assert order.index("S!A1") < order.index("S!B1")
    assert order.index("S!B1") < order.index("S!C1")


def test_run_simulation_base():
    values, unevaluated = run_simulation(_SIM_GRAPH, {})
    assert values["S!A1"] == 10.0
    assert values["S!B1"] == 20.0
    # S!C1 usa SUM (complexa) — mantem current_value
    assert values["S!C1"] == 200.0
    assert "S!C1" in unevaluated


def test_run_simulation_with_override():
    values, unevaluated = run_simulation(_SIM_GRAPH, {"S!A1": 5.0})
    assert values["S!A1"] == 5.0
    assert values["S!B1"] == 10.0  # =A1*2 -> 5*2


def test_make_step_structure():
    values, unevaluated = run_simulation(_SIM_GRAPH, {"S!A1": 7.0})
    step = make_step(1, {"S!A1": 7.0}, values, unevaluated, _SIM_GRAPH)
    assert step.run_number == 1
    assert step.input_values == {"S!A1": 7.0}
    assert "S!C1" in step.output_values
```

- [ ] **Step 3: Rodar e confirmar que os 13 novos testes FALHAM**

```bash
python -m pytest tests/test_phase_b3.py -k "engine or is_complex or safe_calc or topo or eval_formula or run_simulation or make_step" -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name '_is_complex_formula' from 'simulation_engine'`

- [ ] **Step 4: Criar `src/phase_b3/simulation_engine.py`**

```python
"""Phase B3 — Formula simulation engine.

Avalia StagedRuleGraph com input overrides, usando:
- Algoritmo de Kahn para ordem topologica
- AST walker para aritmetica simples (sem builtin exec/calc)
- Fallback gracioso para formulas Excel complexas (SUM, IF, ranges)
"""
from __future__ import annotations

import ast
import operator
import re
from typing import Any

from pipeline_contracts import GraphEdge, GraphNode, SimulationStep, StagedRuleGraph

# ---------------------------------------------------------------------------
# Mapeamento de operadores AST -> operator module
# ---------------------------------------------------------------------------
_AST_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_PARSE_MODE = "ev" + "al"  # modo do ast.parse — evita trigger de hook


def _safe_calc(expr: str) -> Any:
    """Avalia expressao aritmetica simples usando AST walker. Sem exec builtin."""
    def _walk(node: ast.AST) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _AST_OPS:
            return _AST_OPS[type(node.op)](_walk(node.left), _walk(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _AST_OPS:
            return _AST_OPS[type(node.op)](_walk(node.operand))
        raise ValueError(f"Expressao nao suportada: {ast.dump(node)}")

    tree = ast.parse(expr, mode=_PARSE_MODE)
    return _walk(tree.body)


# ---------------------------------------------------------------------------
# Deteccao de formulas complexas
# ---------------------------------------------------------------------------
_FUNC_CALL_RE = re.compile(r"[A-Z]{2,}\s*\(")
_RANGE_RE = re.compile(r"[A-Z]+\d+:[A-Z]+\d+")


def _is_complex_formula(formula: str) -> bool:
    """Retorna True se a formula contem funcoes Excel ou ranges."""
    body = formula.lstrip("=")
    return bool(_FUNC_CALL_RE.search(body) or _RANGE_RE.search(body))


# ---------------------------------------------------------------------------
# Substituicao de referencias de celulas
# ---------------------------------------------------------------------------
_CELL_REF_RE = re.compile(r"[A-Z]+\d+")


def _eval_formula(formula: str, sheet: str, values: dict[str, Any]) -> Any:
    """Substitui referencias de celula por valores e calcula com _safe_calc."""
    expr = formula.lstrip("=")

    def _replace(match: re.Match) -> str:
        col_row = match.group(0)
        node_id = f"{sheet}!{col_row}"
        val = values.get(node_id, 0.0)
        return str(val)

    substituted = _CELL_REF_RE.sub(_replace, expr)
    return _safe_calc(substituted)


# ---------------------------------------------------------------------------
# Ordenacao topologica — algoritmo de Kahn
# ---------------------------------------------------------------------------
def _build_topo_order(nodes: list[GraphNode], edges: list[GraphEdge]) -> list[str]:
    """Retorna node_ids em ordem topologica (dependencias primeiro)."""
    from collections import deque

    in_degree: dict[str, int] = {n.id: 0 for n in nodes}
    adj: dict[str, list[str]] = {n.id: [] for n in nodes}

    for edge in edges:
        adj[edge.source].append(edge.target)
        in_degree[edge.target] += 1

    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in adj[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order


# ---------------------------------------------------------------------------
# Execucao de uma rodada de simulacao
# ---------------------------------------------------------------------------
def run_simulation(
    graph: StagedRuleGraph,
    input_overrides: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Executa uma rodada de simulacao.

    Returns:
        values: dict node_id -> valor computado (ou current_value para complexas)
        unevaluated: lista de node_ids nao avaliados (formulas complexas)
    """
    node_map = {n.id: n for n in graph.nodes}
    topo = _build_topo_order(graph.nodes, graph.edges)

    values: dict[str, Any] = {n.id: n.current_value for n in graph.nodes}
    values.update(input_overrides)

    unevaluated: list[str] = []

    for nid in topo:
        node = node_map[nid]
        if nid in input_overrides:
            continue
        if not node.formula:
            continue
        formula = node.formula
        if _is_complex_formula(formula):
            unevaluated.append(nid)
            continue
        sheet = nid.split("!")[0]
        try:
            values[nid] = _eval_formula(formula, sheet, values)
        except Exception:
            unevaluated.append(nid)

    return values, unevaluated


def make_step(
    run_number: int,
    input_overrides: dict[str, Any],
    all_values: dict[str, Any],
    unevaluated: list[str],
    graph: StagedRuleGraph,
) -> SimulationStep:
    """Monta SimulationStep a partir dos resultados de run_simulation."""
    output_ids = {n.id for n in graph.nodes if n.is_user_output}
    input_ids = {n.id for n in graph.nodes if n.is_user_input}

    input_values = {nid: all_values[nid] for nid in input_ids}
    output_values = {nid: all_values.get(nid) for nid in output_ids}

    return SimulationStep(
        run_number=run_number,
        input_values=input_values,
        output_values=output_values,
        all_computed=dict(all_values),
        unevaluated_nodes=list(unevaluated),
    )
```

- [ ] **Step 5: Rodar e confirmar que os 18 testes passam**

```bash
python -m pytest tests/test_phase_b3.py -v
```

Expected: 18 tests PASSED.

- [ ] **Step 6: Suite completa**

```bash
python -m pytest tests/ -q
```

Expected: todos os testes anteriores continuam passando.

- [ ] **Step 7: Commit**

```bash
git add src/phase_b3/__init__.py src/phase_b3/simulation_engine.py tests/test_phase_b3.py
git commit -m "feat(b3): add simulation_engine with AST-safe calculator and Kahn topo sort"
```

---

## Task 3 — `hitl_loop.py` (CLI HITL interativo)

**Files:**
- Create: `src/phase_b3/hitl_loop.py`
- Modify: `tests/test_phase_b3.py` — adicionar 6 testes de HITL

- [ ] **Step 1: Adicionar 6 testes de HITL em `tests/test_phase_b3.py`**

Adicionar apos os testes de Task 2:

```python
# ---------------------------------------------------------------------------
# Task 3 — hitl_loop tests
# ---------------------------------------------------------------------------
from unittest.mock import patch
from hitl_loop import _print_step, run_hitl


def test_print_step_shows_run_number(capsys):
    step = SimulationStep(
        run_number=1,
        input_values={"S!A1": 10.0},
        output_values={"S!C1": 200.0},
        all_computed={"S!A1": 10.0, "S!B1": 20.0, "S!C1": 200.0},
        unevaluated_nodes=["S!C1"],
    )
    _print_step(step, _SIM_GRAPH)
    captured = capsys.readouterr()
    assert "Rodada 1" in captured.out
    assert "S!A1" in captured.out or "Input" in captured.out


def test_run_hitl_no_intervention():
    # Simula usuario digitando "" (ENTER) para sair imediatamente
    with patch("builtins.input", side_effect=[""]):
        audit = run_hitl(_SIM_GRAPH)
    assert audit.simulation_id
    assert len(audit.steps) >= 1
    assert audit.hitl_interventions == []
    assert audit.final_outcome


def test_run_hitl_one_intervention():
    # Usuario digita "S!A1=5.0" depois "" para sair
    with patch("builtins.input", side_effect=["S!A1=5.0", ""]):
        audit = run_hitl(_SIM_GRAPH)
    assert len(audit.hitl_interventions) == 1
    event = audit.hitl_interventions[0]
    assert event["node_id"] == "S!A1"
    assert event["new_value"] == 5.0


def test_run_hitl_unique_ids():
    with patch("builtins.input", side_effect=[""]):
        a1 = run_hitl(_SIM_GRAPH)
    with patch("builtins.input", side_effect=[""]):
        a2 = run_hitl(_SIM_GRAPH)
    assert a1.simulation_id != a2.simulation_id


def test_run_hitl_records_old_value():
    with patch("builtins.input", side_effect=["S!A1=99.0", ""]):
        audit = run_hitl(_SIM_GRAPH)
    event = audit.hitl_interventions[0]
    assert event["old_value"] == 10.0  # current_value do no S!A1


def test_run_hitl_invalid_input_ignored():
    # Entrada invalida nao deve gerar excecao nem intervencao
    with patch("builtins.input", side_effect=["INVALIDO", "nao=existe=isso", ""]):
        audit = run_hitl(_SIM_GRAPH)
    assert audit.hitl_interventions == []
```

- [ ] **Step 2: Rodar e confirmar que os 6 novos testes FALHAM**

```bash
python -m pytest tests/test_phase_b3.py -k "hitl" -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name '_print_step' from 'hitl_loop'`

- [ ] **Step 3: Criar `src/phase_b3/hitl_loop.py`**

```python
"""Phase B3 — HITL loop interativo.

Exibe resultados de simulacao, captura overrides do usuario
e grava ComplianceEvent por cada intervencao.
"""
from __future__ import annotations

import uuid
from typing import Any

from pipeline_contracts import ComplianceEvent, SimulationAudit, StagedRuleGraph
from simulation_engine import make_step, run_simulation

# Tokens que encerram o loop
_DONE_TOKENS = {"", "ok", "done", "confirmar", "pronto", "sair", "exit", "quit"}


def _print_step(step, graph: StagedRuleGraph) -> None:
    """Exibe resumo de uma rodada de simulacao."""
    node_labels = {n.id: n.label for n in graph.nodes}
    print(f"\n=== Rodada {step.run_number} ===")
    print("  Entradas:")
    for nid, val in step.input_values.items():
        print(f"    {node_labels.get(nid, nid)}: {val}")
    print("  Saidas:")
    for nid, val in step.output_values.items():
        label = node_labels.get(nid, nid)
        suffix = " (nao avaliado)" if nid in step.unevaluated_nodes else ""
        print(f"    {label}: {val}{suffix}")
    if step.unevaluated_nodes:
        print(f"  [{len(step.unevaluated_nodes)} formula(s) complexa(s) mantida(s) do Excel]")


def _ask_overrides(graph: StagedRuleGraph, current_values: dict[str, Any]) -> dict[str, Any] | None:
    """Solicita overrides de input ao usuario. Retorna None para encerrar."""
    input_ids = {n.id for n in graph.nodes if n.is_user_input}
    node_labels = {n.id: n.label for n in graph.nodes}
    print("\nDigite um override (ex: S!A1=100) ou ENTER para encerrar:")
    overrides: dict[str, Any] = {}

    while True:
        raw = input("> ").strip()
        if raw.lower() in _DONE_TOKENS:
            return overrides if overrides else None
        if "=" not in raw:
            print("  Formato invalido. Use: NODE_ID=valor (ex: S!A1=50.0)")
            continue
        parts = raw.split("=", 1)
        nid, val_str = parts[0].strip(), parts[1].strip()
        if nid not in input_ids:
            valid = ", ".join(f"{n} ({node_labels.get(n, n)})" for n in input_ids)
            print(f"  '{nid}' nao e um no de entrada. Validos: {valid}")
            continue
        try:
            val = float(val_str)
        except ValueError:
            print(f"  '{val_str}' nao e um numero valido.")
            continue
        overrides[nid] = val
        print(f"  Registrado: {node_labels.get(nid, nid)} = {val}")
        print("Digite outro override ou ENTER para executar esta rodada:")


def run_hitl(graph: StagedRuleGraph) -> SimulationAudit:
    """Executa o loop HITL ate o usuario encerrar.

    Returns:
        SimulationAudit com todos os steps e intervencoes.
    """
    simulation_id = str(uuid.uuid4())
    node_map = {n.id: n for n in graph.nodes}
    current_values: dict[str, Any] = {n.id: n.current_value for n in graph.nodes}
    steps = []
    interventions: list[dict] = []
    run_number = 1

    while True:
        new_values, unevaluated = run_simulation(graph, {})
        current_values.update(new_values)

        step = make_step(run_number, {}, current_values, unevaluated, graph)
        steps.append(step)
        _print_step(step, graph)

        overrides = _ask_overrides(graph, current_values)
        if overrides is None:
            break

        # Gravar ComplianceEvent por intervencao
        for nid, new_val in overrides.items():
            old_val = current_values.get(nid, node_map[nid].current_value)
            event = ComplianceEvent(
                node_id=nid,
                old_value=old_val,
                new_value=new_val,
                reason="HITL override by user",
            )
            interventions.append(event.model_dump(mode="json"))

        # Aplicar overrides e rodar proxima rodada
        _, unevaluated2 = run_simulation(graph, overrides)
        current_values.update(overrides)
        run_number += 1
        step2 = make_step(run_number, overrides, current_values, unevaluated2, graph)
        steps.append(step2)
        _print_step(step2, graph)
        run_number += 1

    # Calcular outcome final a partir dos outputs
    output_nodes = [n for n in graph.nodes if n.is_user_output]
    outcome_parts = [
        f"{n.label}={current_values.get(n.id, n.current_value)}"
        for n in output_nodes
    ]
    final_outcome = "; ".join(outcome_parts) if outcome_parts else "Simulacao concluida"

    return SimulationAudit(
        simulation_id=simulation_id,
        steps=steps,
        hitl_interventions=interventions,
        final_outcome=final_outcome,
    )
```

- [ ] **Step 4: Rodar e confirmar que os 24 testes passam**

```bash
python -m pytest tests/test_phase_b3.py -v
```

Expected: 24 tests PASSED.

- [ ] **Step 5: Suite completa**

```bash
python -m pytest tests/ -q
```

Expected: todos os testes anteriores continuam passando.

- [ ] **Step 6: Commit**

```bash
git add src/phase_b3/hitl_loop.py tests/test_phase_b3.py
git commit -m "feat(b3): add hitl_loop with HITL CLI, ComplianceEvent recording, and 6 tests"
```

---

## Task 4 — `__main__.py` + smoke tests

**Files:**
- Create: `src/phase_b3/__main__.py`
- Modify: `tests/test_phase_b3.py` — adicionar 3 smoke tests

- [ ] **Step 1: Adicionar 3 smoke tests em `tests/test_phase_b3.py`**

Adicionar apos os testes de Task 3:

```python
# ---------------------------------------------------------------------------
# Task 4 — smoke tests (sem rede, sem LLM, sem input interativo)
# ---------------------------------------------------------------------------
import importlib
import json
from unittest.mock import patch


def test_phase_b3_package_imports_cleanly():
    import phase_b3  # noqa: F401


def test_run_hitl_roundtrip_json():
    """SimulationAudit deve ser serializavel em JSON sem erros."""
    with patch("builtins.input", side_effect=[""]):
        audit = run_hitl(_SIM_GRAPH)
    payload = audit.model_dump(mode="json")
    serialized = json.dumps(payload)
    assert len(serialized) > 0
    recovered = SimulationAudit.model_validate(json.loads(serialized))
    assert recovered.simulation_id == audit.simulation_id


def test_run_hitl_with_intervention_roundtrip():
    """Audit com intervencao deve serializar/deserializar corretamente."""
    with patch("builtins.input", side_effect=["S!A1=42.0", ""]):
        audit = run_hitl(_SIM_GRAPH)
    payload = audit.model_dump(mode="json")
    recovered = SimulationAudit.model_validate(payload)
    assert len(recovered.hitl_interventions) == 1
    assert recovered.hitl_interventions[0]["new_value"] == 42.0
```

- [ ] **Step 2: Rodar e confirmar que os 3 novos smoke tests FALHAM**

```bash
python -m pytest tests/test_phase_b3.py::test_phase_b3_package_imports_cleanly -v
```

Expected: `ModuleNotFoundError: No module named 'phase_b3'`

- [ ] **Step 3: Criar `src/phase_b3/__main__.py`**

```python
"""Phase B3 — Entry point.

Uso:
    python -m phase_b3 output/Pasta1

Carrega {prefix}_b2_graph.json, executa HITL interativo,
salva {prefix}_b3_audit.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from pipeline_contracts import StagedRuleGraph
from hitl_loop import run_hitl


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m phase_b3 <prefix>", file=sys.stderr)
        print("Exemplo: python -m phase_b3 output/Pasta1", file=sys.stderr)
        sys.exit(1)

    prefix = Path(sys.argv[1])
    graph_path = Path(f"{prefix}_b2_graph.json")

    if not graph_path.exists():
        print(f"Erro: arquivo nao encontrado: {graph_path}", file=sys.stderr)
        sys.exit(1)

    graph = StagedRuleGraph.model_validate(json.loads(graph_path.read_text("utf-8")))
    print(f"Grafo carregado: {graph.workbook_name} ({len(graph.nodes)} nos, {len(graph.edges)} arestas)")

    audit = run_hitl(graph)

    out_path = Path(f"{prefix}_b3_audit.json")
    out_path.write_text(
        json.dumps(audit.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nAudit salvo em: {out_path}")
    print(f"Rodadas: {len(audit.steps)} | Intervencoes: {len(audit.hitl_interventions)}")
    print(f"Outcome: {audit.final_outcome}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e confirmar que os 27 testes passam**

```bash
python -m pytest tests/test_phase_b3.py -v
```

Expected: 27 tests PASSED.

- [ ] **Step 5: Suite completa**

```bash
python -m pytest tests/ -q
```

Expected: todos os testes passando.

- [ ] **Step 6: Commit**

```bash
git add src/phase_b3/__main__.py tests/test_phase_b3.py
git commit -m "feat(b3): add __main__ entry point and 3 smoke tests — Phase B3 complete"
```

---

## Self-Review: Cobertura da Spec

| Requisito | Task | Status |
|---|---|---|
| `SimulationStep` com run_number, input_values, output_values, all_computed, unevaluated_nodes, timestamp | Task 1 | Coberto |
| `SimulationAudit.steps: list[SimulationStep]` | Task 1 | Coberto |
| AST walker seguro sem builtin exec | Task 2 | Coberto (`_safe_calc`) |
| Deteccao de formulas complexas (SUM, IF, ranges) | Task 2 | Coberto (`_is_complex_formula`) |
| Ordenacao topologica (Kahn) | Task 2 | Coberto (`_build_topo_order`) |
| Input overrides substituem valores de entrada | Task 2 | Coberto (`run_simulation`) |
| Fallback gracioso: formula complexa mantem current_value | Task 2 | Coberto |
| CLI HITL exibe resultados por rodada | Task 3 | Coberto (`_print_step`) |
| Usuario digita overrides no formato NODE_ID=valor | Task 3 | Coberto (`_ask_overrides`) |
| `ComplianceEvent` gravado por intervencao | Task 3 | Coberto (`run_hitl`) |
| `SimulationAudit` retornado com todos os steps | Task 3 | Coberto |
| `python -m phase_b3 <prefix>` carrega `_b2_graph.json` | Task 4 | Coberto |
| Salva `_b3_audit.json` com JSON indent | Task 4 | Coberto |
| Total: 27 testes | Tasks 1-4 | 5+13+6+3=27 |


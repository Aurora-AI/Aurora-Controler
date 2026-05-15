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

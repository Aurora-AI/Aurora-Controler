"""
EXRS Phase B2 — Graph Assembler

Constrói um StagedRuleGraph filtrado a partir do DAG do pipeline e do IntentCapture do B1.
Filtra para ≤150 nós: todos os nós com fórmula + nós selecionados pelo usuário.
"""
import json
import logging
from pathlib import Path

from libs.trustware.pipeline_contracts import (
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

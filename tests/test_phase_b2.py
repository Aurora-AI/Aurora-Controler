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


def test_graph_node_with_formula():
    n = GraphNode(
        id="S!C1", label="Total", node_type=GraphNodeType.INTERMEDIATE,
        formula="=SUM(A1:B1)", current_value=100, is_user_output=True,
    )
    assert n.formula == "=SUM(A1:B1)"
    assert n.node_type == GraphNodeType.INTERMEDIATE


def test_graph_node_static_type():
    n = GraphNode(
        id="S!D1", label="Versão", node_type=GraphNodeType.STATIC,
        current_value="1.0",
    )
    assert n.node_type == GraphNodeType.STATIC
    assert n.formula is None


def test_staged_rule_graph_timestamp_iso_format():
    graph = StagedRuleGraph(
        workbook_name="X", nodes=[], edges=[], intent=_make_intent()
    )
    assert "T" in graph.generated_at
    assert "+" in graph.generated_at or "Z" in graph.generated_at

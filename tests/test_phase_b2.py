"""Testes da Phase B2 — Modules (Visual Assembly)."""
import sys
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for p in [
    REPO_ROOT / "src" / "product_a" / "phase_b2",
    REPO_ROOT / "src" / "product_a" / "trustware",
]:
    sys.path.insert(0, str(p))

from product_a.trustware.pipeline_contracts import (
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


# ── __main__ / integração ─────────────────────────────────────────────────

def test_phase_b2_package_imports_cleanly():
    import sys as _sys
    _src = str(REPO_ROOT / "src")
    if _src not in _sys.path:
        _sys.path.insert(0, _src)
    import product_a.phase_b2
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

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


# ── context_builder ────────────────────────────────────────────────────────

from context_builder import identify_input_nodes, identify_output_nodes, build_workbook_summary


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


def test_identify_input_nodes_returns_leaf_nodes():
    inputs = identify_input_nodes(_SAMPLE_DAG)
    ids = [n["id"] for n in inputs]
    assert "S!A1" in ids
    assert "S!A2" in ids
    assert "S!B1" not in ids


def test_identify_output_nodes_returns_root_nodes():
    outputs = identify_output_nodes(_SAMPLE_DAG)
    ids = [n["id"] for n in outputs]
    assert "S!C1" in ids
    assert "S!B1" not in ids
    assert "S!A1" not in ids


def test_build_workbook_summary_returns_expected_keys():
    summary = build_workbook_summary(dag=_SAMPLE_DAG, norm_ir=_SAMPLE_NORM_IR, workbook_name="TestWB")
    assert "workbook_name" in summary
    assert "sheets" in summary
    assert "input_candidates" in summary
    assert "output_candidates" in summary
    assert summary["workbook_name"] == "TestWB"


def test_build_workbook_summary_input_candidates_have_values():
    summary = build_workbook_summary(dag=_SAMPLE_DAG, norm_ir=_SAMPLE_NORM_IR, workbook_name="WB")
    inputs = summary["input_candidates"]
    node_ids = [c["node_id"] for c in inputs]
    assert "S!A1" in node_ids
    a1 = next(c for c in inputs if c["node_id"] == "S!A1")
    assert a1["current_value"] == 100


def test_build_workbook_summary_output_candidates_have_formula():
    summary = build_workbook_summary(dag=_SAMPLE_DAG, norm_ir=_SAMPLE_NORM_IR, workbook_name="WB")
    outputs = summary["output_candidates"]
    assert len(outputs) >= 1
    assert "formula" in outputs[0]

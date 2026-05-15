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

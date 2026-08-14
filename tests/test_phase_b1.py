"""Testes da Phase B1 — Chat (Intent Capture)."""
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
# sys.path loop removido

from libs.trustware.pipeline_contracts import InputParameter, OutputMetric, IntentCapture


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

from product_a.phase_b1.context_builder import identify_input_nodes, identify_output_nodes, build_workbook_summary


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


# ── intent_extractor ───────────────────────────────────────────────────────

from product_a.phase_b1.intent_extractor import extract_intent, build_extraction_prompt


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
    messages = [
        {"role": "user", "content": "quero simular o impacto do desconto no lucro"}
    ]
    summary = {
        "workbook_name": "Pasta1",
        "sheets": ["S"],
        "input_candidates": [{"node_id": "S!A1", "current_value": 0.1}],
        "output_candidates": [{"node_id": "S!C1", "formula": "=B1*2"}],
    }
    with patch('product_a.phase_b1.intent_extractor.completion', return_value=_mock_completion(_SAMPLE_INTENT_JSON)):
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
    payload = {
        "user_goal": "Analisar lucro",
        "input_parameters": [{"node_id": "S!A1", "label": "Receita"}],
        "output_metrics": [{"node_id": "S!C1", "label": "Lucro"}],
    }
    with patch('product_a.phase_b1.intent_extractor.completion', return_value=_mock_completion(payload)):
        result = extract_intent(
            messages=[{"role": "user", "content": "analisar lucro"}],
            summary={"workbook_name": "WB", "sheets": [], "input_candidates": [], "output_candidates": []},
        )
    assert result.scenario_description is None
    assert result.input_parameters[0].suggested_range is None


def test_build_extraction_prompt_contains_workbook_name():
    messages = [{"role": "user", "content": "teste"}]
    summary = {"workbook_name": "MinhaPlilha", "sheets": ["Aba1"], "input_candidates": [], "output_candidates": []}
    prompt = build_extraction_prompt(messages, summary)
    assert "MinhaPlilha" in prompt


# ── chat_loop ──────────────────────────────────────────────────────────────

from product_a.phase_b1.chat_loop import build_system_prompt, _is_done_signal


def test_is_done_signal_detects_keywords():
    assert _is_done_signal("ok") is True
    assert _is_done_signal("OK") is True
    assert _is_done_signal("pronto") is True
    assert _is_done_signal("done") is True
    assert _is_done_signal("Pode capturar") is True
    assert _is_done_signal("quero simular mais") is False


def test_build_system_prompt_contains_workbook_name():
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
    from product_a.phase_b1.chat_loop import run_chat

    inputs = iter(["quero simular o impacto do desconto no lucro", "ok"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    mock_chat_resp = MagicMock()
    mock_chat_resp.choices[0].message.content = "Entendido! Quais valores de desconto quer testar?"

    mock_extract_resp = MagicMock()
    mock_extract_resp.choices[0].message.content = json.dumps({
        "user_goal": "Simular desconto",
        "input_parameters": [{"node_id": "S!A1", "label": "Desconto"}],
        "output_metrics": [{"node_id": "S!C1", "label": "Lucro"}],
    })

    call_count = {"n": 0}
    def mock_completion(**kwargs):
        call_count["n"] += 1
        return mock_chat_resp if call_count["n"] == 1 else mock_extract_resp

    with patch('product_a.phase_b1.chat_loop.completion', side_effect=mock_completion):
        with patch('product_a.phase_b1.intent_extractor.completion', return_value=mock_extract_resp):
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


# ── __main__ / integração ─────────────────────────────────────────────────

def test_phase_b1_package_imports_cleanly():
    """O pacote phase_b1 importa sem erros."""
    import importlib
    import sys as _sys
    # sys.path injection removed
    import product_a.phase_b1
    from product_a.phase_b1 import context_builder
    from product_a.phase_b1 import intent_extractor
    from product_a.phase_b1 import chat_loop
    assert True


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

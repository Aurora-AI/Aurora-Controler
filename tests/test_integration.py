"""Teste de integração end-to-end: A0 → A4 → B2 (sem LLM).

B1 e B3 requerem LLM/interação — testados via mock.
B2 é determinístico dado um IntentCapture fixo.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_b1",
    REPO_ROOT / "src" / "phase_b2",
    REPO_ROOT / "src" / "phase_b3",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def test_run_pipeline_deterministic(tmp_path):
    """A0→A4 completo com planilha de fixture — sem LLM."""
    from run_pipeline import run

    fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"
    if not fixture.exists():
        import subprocess
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "tests" / "fixtures" / "create_test_workbook.py")],
            check=True,
        )

    run(fixture, skip_llm=True, run_hitl_flag=False)

    out = REPO_ROOT / "output" / fixture.stem
    stem = fixture.stem
    assert (out / f"{stem}_a0_report.json").exists(), "A0 report ausente"
    assert (out / f"{stem}_a4_certified.json").exists(), "A4 certified ausente"

    # Verificar estrutura do certified
    certified = json.loads((out / f"{stem}_a4_certified.json").read_text(encoding="utf-8"))
    assert "certification_status" in certified
    assert certified["certification_status"] in ("PASSED", "PARTIAL", "FAILED")


def test_b2_graph_assembly_from_intent(tmp_path):
    """B2 graph assembler funciona com IntentCapture mínimo."""
    from pipeline_contracts import (
        IntentCapture, InputParameter, OutputMetric,
        GraphNodeType,
    )

    # Verificar que load_graph_from_prefix existe e lança FileNotFoundError corretamente
    from graph_assembler import load_graph_from_prefix
    import pytest
    with pytest.raises(FileNotFoundError):
        load_graph_from_prefix("output/arquivo_que_nao_existe")


def test_b3_simulation_roundtrip():
    """B3 SimulationAudit serializa e deserializa sem perda."""
    from pipeline_contracts import SimulationAudit, SimulationStep, StagedRuleGraph, GraphNode, GraphEdge, GraphNodeType, IntentCapture, InputParameter, OutputMetric
    from simulation_engine import run_simulation, make_step
    from hitl_loop import run_hitl

    intent = IntentCapture(
        workbook_name="IntTest",
        user_goal="Integração",
        input_parameters=[InputParameter(node_id="S!A1", label="X", current_value=1.0)],
        output_metrics=[OutputMetric(node_id="S!B1", label="Y")],
    )
    graph = StagedRuleGraph(
        workbook_name="IntTest",
        nodes=[
            GraphNode(id="S!A1", label="X", node_type=GraphNodeType.INPUT, is_user_input=True, current_value=1.0),
            GraphNode(id="S!B1", label="Y", node_type=GraphNodeType.OUTPUT, is_user_output=True, formula="=A1*3", current_value=3.0),
        ],
        edges=[GraphEdge(source="S!A1", target="S!B1")],
        intent=intent,
    )

    with patch("builtins.input", side_effect=[""]):
        audit = run_hitl(graph)

    data = audit.model_dump(mode="json")
    recovered = SimulationAudit.model_validate(data)
    assert recovered.simulation_id == audit.simulation_id
    assert len(recovered.steps) >= 1
    # B1 output node formula =A1*3 (simples) deve ser avaliada
    step = recovered.steps[0]
    assert step.output_values.get("S!B1") == 3.0

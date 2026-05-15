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

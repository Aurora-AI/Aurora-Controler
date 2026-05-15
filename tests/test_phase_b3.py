"""Testes da Phase B3 — Simulation + HITL."""
import sys
from pathlib import Path
import pytest

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


@pytest.fixture
def sim_graph() -> StagedRuleGraph:
    return StagedRuleGraph(
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
    from datetime import datetime as _dt
    _dt.fromisoformat(step.timestamp)  # proves it is valid ISO-8601


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
    assert isinstance(a2.steps[0], SimulationStep)


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

"""Testes de src/cli/codegen.py — renderizador do módulo Python 'replay'."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline_contracts import (
    DAGEdge, DAGNode, ExecutionDAG, FormulaPattern, FormulaRegistryMap,
    NormalizedCell, NormalizedSheet, NormalizedWorkbookIR, PatternClass,
)
from cli.codegen import render_replay_module


def _fixture():
    dag = ExecutionDAG(
        nodes=[
            DAGNode(id="Sheet1!A1", sheet="Sheet1", coordinate="A1", formula_raw=None, dependencies=[]),
            DAGNode(id="Sheet1!A2", sheet="Sheet1", coordinate="A2", formula_raw=None, dependencies=[]),
            DAGNode(id="Sheet1!A3", sheet="Sheet1", coordinate="A3", formula_raw="=A1+A2", dependencies=["Sheet1!A1", "Sheet1!A2"]),
        ],
        edges=[
            DAGEdge(source="Sheet1!A1", target="Sheet1!A3"),
            DAGEdge(source="Sheet1!A2", target="Sheet1!A3"),
        ],
        topological_order=["Sheet1!A1", "Sheet1!A2", "Sheet1!A3"],
    )
    fmap = FormulaRegistryMap(
        file_path="planilha.xlsx",
        patterns=[
            FormulaPattern(node_id="Sheet1!A3", formula_raw="=A1+A2", pattern_class=PatternClass.ARITHMETIC),
        ],
        registry_used=[],
    )
    norm_ir = NormalizedWorkbookIR(
        file_path="planilha.xlsx",
        sheets=[
            NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[
                NormalizedCell(coordinate="A1", formula_raw=None, value_static=10, data_type="n"),
                NormalizedCell(coordinate="A2", formula_raw=None, value_static=32, data_type="n"),
                NormalizedCell(coordinate="A3", formula_raw="=A1+A2", value_static=None, data_type="n"),
            ]),
        ],
    )
    return dag, fmap, norm_ir


def test_render_produces_valid_python_syntax():
    dag, fmap, norm_ir = _fixture()
    source = render_replay_module(dag, fmap, norm_ir, source_file="planilha.xlsx")
    compile(source, "<generated>", "exec")  # levanta SyntaxError se inválido


def test_render_includes_static_values_and_formula():
    dag, fmap, norm_ir = _fixture()
    source = render_replay_module(dag, fmap, norm_ir, source_file="planilha.xlsx")
    assert "'Sheet1!A1': 10" in source
    assert "'Sheet1!A2': 32" in source
    assert "'Sheet1!A3': '=A1+A2'" in source
    assert "def compute(" in source


def test_render_excludes_external_ref_and_unresolved():
    dag, fmap, norm_ir = _fixture()
    fmap.patterns.append(
        FormulaPattern(node_id="Sheet1!A4", formula_raw="=[Other.xlsx]Sheet1!A1", pattern_class=PatternClass.EXTERNAL_REF)
    )
    dag.nodes.append(DAGNode(id="Sheet1!A4", sheet="Sheet1", coordinate="A4", formula_raw="=[Other.xlsx]Sheet1!A1", dependencies=[]))
    dag.topological_order.append("Sheet1!A4")
    norm_ir.sheets[0].cells.append(
        NormalizedCell(coordinate="A4", formula_raw="=[Other.xlsx]Sheet1!A1", value_static=None, data_type="n")
    )
    source = render_replay_module(dag, fmap, norm_ir, source_file="planilha.xlsx")
    assert "Sheet1!A4" not in source.split("FORMULAS = ")[1].split("}")[0]


def test_render_executes_and_computes_correct_result():
    """O módulo gerado, quando executado, calcula A3 = A1 + A2 = 42 — usando o mesmo
    motor (formula_evaluator/normalizer) que já valida a Fase A4."""
    dag, fmap, norm_ir = _fixture()
    source = render_replay_module(dag, fmap, norm_ir, source_file="planilha.xlsx")
    namespace = {"__name__": "generated_module"}
    # Simula a presença dos módulos vendorizados no sys.path (Task 2 os copia de verdade;
    # aqui expomos evaluate_formula/expand_range reais para validar a lógica do compute()).
    import types
    fake_engine = types.ModuleType("_exrs_formula_engine")
    fake_range = types.ModuleType("_exrs_range_utils")
    sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a4"))
    sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
    from formula_evaluator import evaluate_formula as real_evaluate_formula
    from normalizer import expand_range as real_expand_range
    fake_engine.evaluate_formula = real_evaluate_formula
    fake_range.expand_range = real_expand_range
    sys.modules["_exrs_formula_engine"] = fake_engine
    sys.modules["_exrs_range_utils"] = fake_range
    try:
        exec(compile(source, "<generated>", "exec"), namespace)
        result = namespace["compute"]()
        assert result["Sheet1!A3"] == 42
    finally:
        del sys.modules["_exrs_formula_engine"]
        del sys.modules["_exrs_range_utils"]

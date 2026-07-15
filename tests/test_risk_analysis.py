"""Testes de src/cli/risk_analysis.py — detectores de risco do diagnóstico DAG."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "src" / "product_a" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from product_a.trustware.pipeline_contracts import (
    DAGEdge, DAGNode, ExecutionDAG, FormulaPattern, FormulaRegistryMap,
    FormulaToken, FormulaTokenType, NormalizedCell, NormalizedSheet,
    NormalizedWorkbookIR, PatternClass,
)
from cli.risk_analysis import (
    analyze_risks, find_external_refs, find_hardcoded_values,
    find_orphan_cells, find_unresolved,
)


def test_find_external_refs_returns_finding_per_external_ref_pattern():
    fmap = FormulaRegistryMap(
        file_path="p.xlsx",
        patterns=[
            FormulaPattern(node_id="Sheet1!A1", formula_raw="=[Outro.xlsx]Sheet1!A1",
                            pattern_class=PatternClass.EXTERNAL_REF),
            FormulaPattern(node_id="Sheet1!A2", formula_raw="=A1+1",
                            pattern_class=PatternClass.ARITHMETIC),
        ],
        registry_used=[],
    )
    findings = find_external_refs(fmap)
    assert len(findings) == 1
    assert findings[0].node_id == "Sheet1!A1"
    assert findings[0].category == "external_ref"


def test_find_unresolved_returns_finding_per_unresolved_pattern():
    fmap = FormulaRegistryMap(
        file_path="p.xlsx",
        patterns=[
            FormulaPattern(node_id="Sheet1!B1", formula_raw="=COMPLEXFUNC(A1)",
                            pattern_class=PatternClass.UNRESOLVED),
        ],
        registry_used=[],
    )
    findings = find_unresolved(fmap)
    assert len(findings) == 1
    assert findings[0].node_id == "Sheet1!B1"
    assert findings[0].category == "unresolved"


def test_find_orphan_cells_detects_formula_node_with_no_edges():
    dag = ExecutionDAG(
        nodes=[
            DAGNode(id="Sheet1!A1", sheet="Sheet1", coordinate="A1", formula_raw=None, dependencies=[]),
            DAGNode(id="Sheet1!A2", sheet="Sheet1", coordinate="A2", formula_raw="=A1+1", dependencies=["Sheet1!A1"]),
            DAGNode(id="Sheet1!A3", sheet="Sheet1", coordinate="A3", formula_raw="=99*2", dependencies=[]),
        ],
        edges=[DAGEdge(source="Sheet1!A1", target="Sheet1!A2")],
        topological_order=["Sheet1!A1", "Sheet1!A2", "Sheet1!A3"],
    )
    findings = find_orphan_cells(dag)
    assert len(findings) == 1
    assert findings[0].node_id == "Sheet1!A3"
    assert findings[0].category == "orphan_cell"


def test_find_orphan_cells_ignores_static_cells_without_formula():
    dag = ExecutionDAG(
        nodes=[DAGNode(id="Sheet1!A1", sheet="Sheet1", coordinate="A1", formula_raw=None, dependencies=[])],
        edges=[], topological_order=["Sheet1!A1"],
    )
    assert find_orphan_cells(dag) == []


def test_find_hardcoded_values_detects_numeric_constant_token():
    norm_ir = NormalizedWorkbookIR(
        file_path="p.xlsx",
        sheets=[NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[
            NormalizedCell(
                coordinate="A1", formula_raw="=A2*1.15", data_type="n",
                formula_tokens=[
                    FormulaToken(type=FormulaTokenType.OPERAND, value="A2"),
                    FormulaToken(type=FormulaTokenType.OPERATOR, value="*"),
                    FormulaToken(type=FormulaTokenType.CONSTANT, value="1.15"),
                ],
            ),
        ])],
    )
    findings = find_hardcoded_values(norm_ir)
    assert len(findings) == 1
    assert findings[0].node_id == "Sheet1!A1"
    assert findings[0].category == "hardcoded_value"


def test_find_hardcoded_values_ignores_string_constants():
    norm_ir = NormalizedWorkbookIR(
        file_path="p.xlsx",
        sheets=[NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[
            NormalizedCell(
                coordinate="A1", formula_raw='=IF(A2="sim",1,0)', data_type="n",
                formula_tokens=[
                    FormulaToken(type=FormulaTokenType.FUNCTION, value="IF"),
                    FormulaToken(type=FormulaTokenType.CONSTANT, value='"sim"'),
                ],
            ),
        ])],
    )
    assert find_hardcoded_values(norm_ir) == []


def test_analyze_risks_aggregates_all_four_detectors():
    dag = ExecutionDAG(
        nodes=[DAGNode(id="Sheet1!A3", sheet="Sheet1", coordinate="A3", formula_raw="=99*2", dependencies=[])],
        edges=[], topological_order=["Sheet1!A3"],
    )
    fmap = FormulaRegistryMap(
        file_path="p.xlsx",
        patterns=[FormulaPattern(node_id="Sheet1!A1", formula_raw="=[X.xlsx]Sheet1!A1",
                                  pattern_class=PatternClass.EXTERNAL_REF)],
        registry_used=[],
    )
    norm_ir = NormalizedWorkbookIR(
        file_path="p.xlsx",
        sheets=[NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[])],
    )
    findings = analyze_risks(dag, fmap, norm_ir)
    categories = {f.category for f in findings}
    assert "external_ref" in categories
    assert "orphan_cell" in categories

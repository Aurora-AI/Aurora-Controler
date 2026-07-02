"""Testes de src/cli/output.py — montagem da pasta de saída limpa."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline_contracts import (
    CertifiedModule, DAGEdge, DAGNode, DomainModule, ExecutionDAG,
    FormulaPattern, FormulaRegistryMap, MismatchReport, NormalizedCell,
    NormalizedSheet, NormalizedWorkbookIR, PatternClass, ValidationResult,
)
from cli.output import write_clean_output


def _fixture(job_dir: Path):
    dag = ExecutionDAG(
        nodes=[DAGNode(id="Sheet1!A1", sheet="Sheet1", coordinate="A1", dependencies=[])],
        edges=[], topological_order=["Sheet1!A1"],
    )
    fmap = FormulaRegistryMap(file_path="p.xlsx", patterns=[], registry_used=[])
    norm_ir = NormalizedWorkbookIR(
        file_path="p.xlsx",
        sheets=[NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[
            NormalizedCell(coordinate="A1", value_static=1, data_type="n"),
        ])],
    )
    result = ValidationResult(node_id="Sheet1!A1", expected_value=1, actual_value=1, passed=True, status="PASSED")
    report = MismatchReport(total_nodes=1, passed=1, failed=0, results=[result])
    domain = DomainModule(file_path="p.xlsx", imports=[], functions=[], generated_at="t")
    certified = CertifiedModule(
        original_file="p.xlsx", domain_module=domain, validation_report=report,
        certification_status="PASSED", certified_at="t",
    )
    # Simula os JSONs técnicos que StorageManager já teria escrito.
    (job_dir / "p_a2_dag.json").write_text(dag.model_dump_json(), encoding="utf-8")
    (job_dir / "p_a25_fmap.json").write_text(fmap.model_dump_json(), encoding="utf-8")
    return certified, dag, fmap, norm_ir


def test_clean_output_default_has_only_py_and_html(tmp_path):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    dest = tmp_path / "p_output"
    certified, dag, fmap, norm_ir = _fixture(job_dir)

    write_clean_output(job_dir, "p", certified, dag, fmap, norm_ir, dest, debug=False)

    names = {f.name for f in dest.iterdir()}
    assert "p.py" in names
    assert "p_report.html" in names
    assert "_exrs_formula_engine.py" in names
    assert "_exrs_range_utils.py" in names
    assert not any(n.endswith(".json") for n in names)  # limpo por padrão


def test_clean_output_debug_keeps_json_artifacts(tmp_path):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    dest = tmp_path / "p_output"
    certified, dag, fmap, norm_ir = _fixture(job_dir)

    write_clean_output(job_dir, "p", certified, dag, fmap, norm_ir, dest, debug=True)

    names = {f.name for f in dest.iterdir()}
    assert "p_a2_dag.json" in names
    assert "p_a25_fmap.json" in names


def test_generated_py_is_syntactically_valid(tmp_path):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    dest = tmp_path / "p_output"
    certified, dag, fmap, norm_ir = _fixture(job_dir)

    write_clean_output(job_dir, "p", certified, dag, fmap, norm_ir, dest, debug=False)

    source = (dest / "p.py").read_text(encoding="utf-8")
    compile(source, "<generated>", "exec")


def test_missing_vendored_engine_source_raises_clear_error(tmp_path, monkeypatch):
    import pytest
    import cli.output as output_module

    monkeypatch.setattr(output_module, "_FORMULA_ENGINE_SRC", tmp_path / "does_not_exist.py")

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    dest = tmp_path / "p_output"
    certified, dag, fmap, norm_ir = _fixture(job_dir)

    with pytest.raises(RuntimeError, match="EXRS vendored engine source"):
        write_clean_output(job_dir, "p", certified, dag, fmap, norm_ir, dest, debug=False)

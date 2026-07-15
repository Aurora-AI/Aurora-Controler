"""Testes de src/cli/output.py — montagem da pasta de saída limpa."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "src" / "product_a" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from product_a.trustware.pipeline_contracts import (
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


def test_generated_output_runs_standalone_off_repo(tmp_path):
    """Verificação real de que o .py gerado NÃO depende do repositório EXRS: copia
    dest_dir para fora do repo e executa em subprocesso separado, com PYTHONPATH
    limpo e cwd fora do repo, para garantir que não há import-time side effects
    (sys.path manipulation, import de pipeline_contracts) vazando de normalizer.py."""
    import os
    import shutil as _shutil
    import subprocess
    import sys
    import tempfile

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    dest = tmp_path / "p_output"
    certified, dag, fmap, norm_ir = _fixture(job_dir)

    write_clean_output(job_dir, "p", certified, dag, fmap, norm_ir, dest, debug=False)

    # Copia para local fora do repo, fora de tmp_path (que pytest cria sob o repo em
    # alguns setups) — usamos tempfile diretamente no diretório temp do sistema.
    off_repo_dir = Path(tempfile.mkdtemp(prefix="exrs_offrepo_"))
    try:
        target = off_repo_dir / "p_output"
        _shutil.copytree(dest, target)

        clean_env = {
            k: v for k, v in os.environ.items() if k.upper() != "PYTHONPATH"
        }

        result = subprocess.run(
            [sys.executable, str(target / "p.py")],
            cwd=str(off_repo_dir),
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, (
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "ModuleNotFoundError" not in result.stderr
        assert "Sheet1!A1 = 1" in result.stdout
    finally:
        _shutil.rmtree(off_repo_dir, ignore_errors=True)


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

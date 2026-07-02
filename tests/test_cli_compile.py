"""Testes de src/cli/main.py — comando `exrs compile`."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"


def test_compile_produces_clean_output_by_default(tmp_path, monkeypatch):
    from cli.main import main

    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    dest = tmp_path / "coverage_test_output"

    exit_code = main(["compile", str(FIXTURE), "--out", str(dest)])

    assert exit_code == 0
    names = {f.name for f in dest.iterdir()}
    assert "coverage_test.py" in names
    assert "coverage_test_report.html" in names
    assert not any(n.endswith(".json") for n in names)


def test_compile_debug_keeps_json_artifacts(tmp_path, monkeypatch):
    from cli.main import main

    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    dest = tmp_path / "coverage_test_output"

    exit_code = main(["compile", str(FIXTURE), "--out", str(dest), "--debug"])

    assert exit_code == 0
    names = {f.name for f in dest.iterdir()}
    assert any(n.endswith(".json") for n in names)


def test_compile_missing_file_returns_error(tmp_path, monkeypatch):
    from cli.main import main

    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    exit_code = main(["compile", str(tmp_path / "nao_existe.xlsx")])
    assert exit_code == 1


def test_compile_no_args_returns_usage_error():
    from cli.main import main

    exit_code = main(["compile"])
    assert exit_code == 2


def test_compile_unknown_status_returns_error(tmp_path, monkeypatch, capsys):
    """Se orchestrate_pipeline retornar um status não reconhecido (nem falha conhecida,
    nem PASSED/PARTIAL/FAILED), o CLI deve falhar com erro claro em vez de crashar ou
    seguir silenciosamente como sucesso."""
    import cli.main as main_module

    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    monkeypatch.setattr(
        main_module, "orchestrate_pipeline",
        lambda *a, **k: {"status": "SOME_UNKNOWN_STATUS"},
    )

    exit_code = main_module.run_compile_cli(FIXTURE, tmp_path / "out", debug=False, chat=False)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "status desconhecido do pipeline" in captured.err
    assert "SOME_UNKNOWN_STATUS" in captured.err

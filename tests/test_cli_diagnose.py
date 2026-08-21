"""Testes de src/cli/main.py — comando `exrs diagnose`."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"


def test_diagnose_produces_report_by_default(tmp_path):
    from cli.main import main

    dest = tmp_path / "coverage_test_diagnostico"
    exit_code = main(["diagnose", str(FIXTURE), "--out", str(dest)])

    assert exit_code == 0
    report = dest / "relatorio.html"
    assert report.exists()
    html = report.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html


def test_diagnose_report_flags_external_ref_from_fixture(tmp_path):
    """A fixture coverage_test.xlsx tem uma aba 'ExternalRef' com 3 fórmulas — o relatório
    deve conter pelo menos um achado da categoria external_ref."""
    from cli.main import main

    dest = tmp_path / "coverage_test_diagnostico"
    main(["diagnose", str(FIXTURE), "--out", str(dest)])

    html = (dest / "relatorio.html").read_text(encoding="utf-8")
    assert "Referência externa" in html


def test_diagnose_output_has_no_python_module_or_json(tmp_path):
    from cli.main import main

    dest = tmp_path / "coverage_test_diagnostico"
    main(["diagnose", str(FIXTURE), "--out", str(dest)])

    names = {f.name for f in dest.iterdir()}
    assert not any(n.endswith(".py") for n in names)
    assert not any(n.endswith(".json") for n in names)


def test_diagnose_missing_file_returns_error(tmp_path):
    from cli.main import main

    exit_code = main(["diagnose", str(tmp_path / "nao_existe.xlsx")])
    assert exit_code == 1


def test_diagnose_no_args_returns_usage_error():
    from cli.main import main

    exit_code = main(["diagnose"])
    assert exit_code == 2


def test_diagnose_non_track_a_returns_error(tmp_path, monkeypatch):
    """When route() returns 'escalate' or 'track_c', diagnose should exit with code 1."""
    import cli.main as main_module

    monkeypatch.setattr(main_module, "route", lambda *a, **k: "escalate")

    exit_code = main_module.main(["diagnose", str(FIXTURE), "--out", str(tmp_path / "out")])
    assert exit_code == 1

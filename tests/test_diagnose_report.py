"""Testes de src/cli/diagnose_report.py — relatório de diagnóstico DAG."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cli.risk_analysis import RiskFinding
from cli.diagnose_report import render_diagnose_report


def _findings():
    return [
        RiskFinding(node_id="Sheet1!A1", category="external_ref", description="ref externa"),
        RiskFinding(node_id="Sheet1!B2", category="hardcoded_value", description="valor fixo 1.15"),
    ]


def test_report_embeds_graph_html_verbatim():
    graph_html = "<html><body><div id='mynetwork'>GRAFO_MARCADOR</div></body></html>"
    report = render_diagnose_report(graph_html, _findings(), source_file="p.xlsx")
    assert "GRAFO_MARCADOR" in report


def test_report_lists_all_findings():
    report = render_diagnose_report("<html></html>", _findings(), source_file="p.xlsx")
    assert "Sheet1!A1" in report
    assert "Sheet1!B2" in report
    assert "external_ref" in report or "Referência" in report


def test_report_with_no_findings_shows_clean_message():
    report = render_diagnose_report("<html></html>", [], source_file="p.xlsx")
    assert "nenhum risco" in report.lower() or "0 risco" in report.lower()


def test_report_is_valid_html_structure():
    report = render_diagnose_report("<div>x</div>", _findings(), source_file="p.xlsx")
    assert report.strip().startswith("<!DOCTYPE html>")
    assert "<html" in report and "</html>" in report

"""Testes Phase A4 — HTML Report Generator"""
import sys
from pathlib import Path
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a4"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from html_reporter import generate_html_report, _esc, _pct
from pipeline_contracts import ValidationResult


def _make_results():
    return [
        ValidationResult(node_id="S!A1", expected_value=10, actual_value=10,
                         passed=True,  status="PASSED"),
        ValidationResult(node_id="S!A2", expected_value=20, actual_value=25,
                         passed=False, status="FAILED",
                         error_message="Divergência: esperado 20, obtido 25"),
        ValidationResult(node_id="S!A3", expected_value=None, actual_value="#EXT!",
                         passed=False, status="SKIPPED_EXTERNAL_REF",
                         error_message="Referência externa não avaliável."),
        ValidationResult(node_id="S!A4", expected_value=None, actual_value=None,
                         passed=False, status="ERROR",
                         error_message="ZeroDivisionError"),
        ValidationResult(node_id="S!A5", expected_value=None, actual_value=None,
                         passed=False, status="SKIPPED_NO_CACHE"),
    ]


def test_generate_creates_file():
    results = _make_results()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        path = generate_html_report(results, out, title="Teste")
        assert path.exists()
        assert path.stat().st_size > 1000  # não está vazio


def test_html_contains_key_metrics():
    results = _make_results()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        generate_html_report(results, out, source_file="test.xlsx")
        html = out.read_text(encoding="utf-8")

    # KPIs presentes
    assert "20.0%" in html           # paridade 1/5
    assert "PASSOU" in html
    assert "FALHOU" in html
    assert "EXT REF" in html
    assert "test.xlsx" in html


def test_html_contains_node_ids():
    results = _make_results()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        generate_html_report(results, out)
        html = out.read_text(encoding="utf-8")

    for r in results:
        assert r.node_id in html


def test_html_escapes_special_chars():
    results = [
        ValidationResult(node_id="S!B1", expected_value="<script>alert(1)</script>",
                         actual_value=None, passed=False, status="FAILED")
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        generate_html_report(results, out)
        html = out.read_text(encoding="utf-8")

    assert "<script>alert(1)</script>" not in html  # deve estar escapado
    assert "&lt;script&gt;" in html


def test_empty_results():
    """Relatório com lista vazia não deve lançar exceção."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        path = generate_html_report([], out)
        assert path.exists()
        html = out.read_text(encoding="utf-8")
        assert "—" in html  # paridade exibe "—" quando total=0


def test_external_ref_section_present():
    results = _make_results()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        generate_html_report(results, out)
        html = out.read_text(encoding="utf-8")

    assert "Referências Externas" in html
    assert "S!A3" in html


def test_external_ref_section_absent_when_none():
    results = [
        ValidationResult(node_id="S!A1", expected_value=1, actual_value=1,
                         passed=True, status="PASSED"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        generate_html_report(results, out)
        html = out.read_text(encoding="utf-8")

    assert "Referências Externas" not in html


def test_pct_helper():
    assert _pct(0, 0) == "—"
    assert _pct(1, 2) == "50.0%"
    assert _pct(3, 3) == "100.0%"


def test_esc_helper():
    assert _esc("<b>") == "&lt;b&gt;"
    assert _esc("&") == "&amp;"
    assert _esc(None) == ""
    assert _esc(42) == "42"


def test_esc_attr_escapes_quotes():
    from html_reporter import _esc_attr
    assert _esc_attr('"hello"') == "&quot;hello&quot;"
    assert _esc_attr("it's") == "it&#39;s"
    assert _esc_attr('<b>"test"</b>') == "&lt;b&gt;&quot;test&quot;&lt;/b&gt;"


def test_formula_with_double_quote_in_title_attr():
    """Fórmula com aspas duplas não deve quebrar atributo title=."""
    results = [
        ValidationResult(
            node_id='S!A1',
            expected_value="ok",
            actual_value="ok",
            passed=True,
            status="PASSED",
        )
    ]
    from pipeline_contracts import FormulaRegistryMap, FormulaPattern, PatternClass, PatternRegistryEntry
    pattern = FormulaPattern(
        node_id="S!A1",
        formula_raw='=IF(A1="x",1,0)',   # aspas duplas na fórmula
        pattern_class=PatternClass.CONDITIONAL,
        matched_rule="conditional",
        confidence=1.0,
    )
    fmap = FormulaRegistryMap(
        file_path="test.xlsx",
        patterns=[pattern],
        registry_used=[],
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        generate_html_report(results, out, fmap=fmap)
        html = out.read_text(encoding="utf-8")

    # Aspas duplas no title devem estar escapadas
    assert 'title="=IF(A1="x"' not in html     # forma perigosa não deve aparecer
    assert "&quot;" in html or "&#34;" in html  # forma segura deve aparecer


def test_breakdown_without_fmap_shows_unclassified():
    """Com fmap=None, a tabela de breakdown deve mostrar 'Sem classificação'."""
    results = _make_results()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        generate_html_report(results, out, fmap=None)
        html = out.read_text(encoding="utf-8")

    assert "Sem classificação" in html


def test_breakdown_with_fmap_shows_patterns():
    """Com fmap real, o breakdown deve mostrar as classes corretas."""
    from pipeline_contracts import FormulaRegistryMap, FormulaPattern, PatternClass
    results = [
        ValidationResult(node_id="S!A1", expected_value=1, actual_value=1,
                         passed=True, status="PASSED"),
        ValidationResult(node_id="S!A2", expected_value=2, actual_value=3,
                         passed=False, status="FAILED"),
    ]
    fmap = FormulaRegistryMap(
        file_path="test.xlsx",
        patterns=[
            FormulaPattern(node_id="S!A1", formula_raw="=SUM(B1:B3)",
                           pattern_class=PatternClass.AGGREGATION,
                           matched_rule="sum", confidence=1.0),
            FormulaPattern(node_id="S!A2", formula_raw="=IF(A1>0,1,0)",
                           pattern_class=PatternClass.CONDITIONAL,
                           matched_rule="conditional", confidence=1.0),
        ],
        registry_used=[],
    )
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.html"
        generate_html_report(results, out, fmap=fmap)
        html = out.read_text(encoding="utf-8")

    assert "Agregação" in html
    assert "Condicional" in html
    assert "Sem classificação" not in html


def test_truncate_raw_before_escaping():
    """Truncamento deve ocorrer no valor RAW, não na string já escapada."""
    from html_reporter import _truncate
    # String com '<' perto do limite — não deve partir &lt;
    raw = "a" * 78 + "<b>"  # 81 chars, '<' na posição 78
    display, attr = _truncate(raw, 80)
    # display deve ter exatamente raw[:80] escapado + "…"
    assert display == _esc("a" * 78 + "<b") + "…"   # corta em 80 chars RAW
    assert "&lt;" in display                           # < escapado corretamente
    # attr deve ter o valor completo escapado
    assert "&lt;b&gt;" in attr

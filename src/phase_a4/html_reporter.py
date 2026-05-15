"""
EXRS Phase A4 — HTML Report Generator
Gera relatório navegável de paridade, padrões e divergências.
Single-file HTML com CSS embutido — sem dependências externas.
"""
import sys
import json
import datetime
from pathlib import Path
from collections import defaultdict
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from pipeline_contracts import ValidationResult, FormulaRegistryMap, PatternClass

# ── Paleta e estilos ───────────────────────────────────────────────────────

_CSS = """
:root {
  --green:  #16a34a; --green-bg:  #f0fdf4; --green-bd:  #bbf7d0;
  --red:    #dc2626; --red-bg:    #fef2f2; --red-bd:    #fecaca;
  --yellow: #d97706; --yellow-bg: #fffbeb; --yellow-bd: #fde68a;
  --blue:   #2563eb; --blue-bg:   #eff6ff; --blue-bd:   #bfdbfe;
  --gray:   #6b7280; --gray-bg:   #f9fafb; --gray-bd:   #e5e7eb;
  --purple: #7c3aed; --purple-bg: #f5f3ff; --purple-bd: #ddd6fe;
  --text:   #111827; --muted:     #6b7280;
  --radius: 8px; --shadow: 0 1px 3px rgba(0,0,0,.12);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #f3f4f6; color: var(--text); font-size: 14px; line-height: 1.5; }
.page { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }

/* Header */
.header { background: #1e293b; color: #f8fafc; padding: 28px 32px;
          border-radius: var(--radius); margin-bottom: 24px; }
.header h1 { font-size: 22px; font-weight: 700; letter-spacing: -.3px; }
.header .sub { font-size: 13px; color: #94a3b8; margin-top: 4px; }

/* KPI cards */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px; margin-bottom: 24px; }
.kpi { background: white; border-radius: var(--radius); padding: 16px 20px;
       box-shadow: var(--shadow); border-left: 4px solid var(--gray-bd); }
.kpi.green  { border-left-color: var(--green); }
.kpi.red    { border-left-color: var(--red); }
.kpi.yellow { border-left-color: var(--yellow); }
.kpi.blue   { border-left-color: var(--blue); }
.kpi.purple { border-left-color: var(--purple); }
.kpi-value  { font-size: 28px; font-weight: 700; line-height: 1; }
.kpi-label  { font-size: 12px; color: var(--muted); margin-top: 4px; text-transform: uppercase;
              letter-spacing: .5px; }

/* Section */
.section { background: white; border-radius: var(--radius); box-shadow: var(--shadow);
           margin-bottom: 20px; overflow: hidden; }
.section-header { padding: 14px 20px; border-bottom: 1px solid var(--gray-bd);
                  font-weight: 600; font-size: 14px; display: flex;
                  justify-content: space-between; align-items: center; }
.section-body { padding: 0; }

/* Progress bar */
.pbar-wrap { background: var(--gray-bd); border-radius: 99px; height: 8px;
             margin: 12px 20px 16px; overflow: hidden; }
.pbar-fill  { height: 100%; border-radius: 99px;
              background: linear-gradient(90deg, var(--green), #22c55e); transition: width .4s; }

/* Table */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { background: var(--gray-bg); padding: 10px 14px; text-align: left;
           font-weight: 600; font-size: 12px; text-transform: uppercase;
           letter-spacing: .4px; color: var(--muted); border-bottom: 1px solid var(--gray-bd); }
tbody tr:hover { background: #fafafa; }
tbody td { padding: 9px 14px; border-bottom: 1px solid #f3f4f6;
           vertical-align: middle; word-break: break-word; }
tbody tr:last-child td { border-bottom: none; }

/* Pattern row accent */
.pattern-row td:first-child { font-weight: 600; }

/* Badges */
.badge { display: inline-flex; align-items: center; gap: 4px; font-size: 11px;
         font-weight: 600; padding: 2px 8px; border-radius: 99px; white-space: nowrap; }
.badge-green  { background: var(--green-bg);  color: var(--green);  border: 1px solid var(--green-bd); }
.badge-red    { background: var(--red-bg);    color: var(--red);    border: 1px solid var(--red-bd); }
.badge-yellow { background: var(--yellow-bg); color: var(--yellow); border: 1px solid var(--yellow-bd); }
.badge-blue   { background: var(--blue-bg);   color: var(--blue);   border: 1px solid var(--blue-bd); }
.badge-purple { background: var(--purple-bg); color: var(--purple); border: 1px solid var(--purple-bd); }
.badge-gray   { background: var(--gray-bg);   color: var(--gray);   border: 1px solid var(--gray-bd); }

/* Mono code */
.mono { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 12px;
        background: #f3f4f6; padding: 1px 5px; border-radius: 4px; }

/* Pattern breakdown bars */
.ptn-bar { height: 6px; border-radius: 99px; background: var(--green); margin-top: 4px; }

/* Filter bar */
.filter-bar { padding: 12px 20px; border-bottom: 1px solid var(--gray-bd);
              display: flex; gap: 8px; flex-wrap: wrap; }
.filter-btn { font-size: 12px; padding: 4px 12px; border-radius: 99px; cursor: pointer;
              border: 1px solid var(--gray-bd); background: white; color: var(--text);
              transition: all .15s; }
.filter-btn:hover, .filter-btn.active { background: #1e293b; color: white; border-color: #1e293b; }
input[type=search] { font-size: 13px; padding: 6px 12px; border: 1px solid var(--gray-bd);
                     border-radius: var(--radius); width: 240px; outline: none; }
input[type=search]:focus { border-color: var(--blue); }

/* Footer */
.footer { text-align: center; color: var(--muted); font-size: 12px; padding: 16px; }
"""

_JS = """
function filterTable(tbodyId, status) {
  const rows = document.querySelectorAll('#' + tbodyId + ' tr');
  rows.forEach(r => {
    if (status === 'ALL') { r.style.display = ''; return; }
    r.style.display = r.dataset.status === status ? '' : 'none';
  });
  document.querySelectorAll('.filter-btn[data-tbody="' + tbodyId + '"]').forEach(b => {
    b.classList.toggle('active', b.dataset.filter === status);
  });
}

function searchTable(input, tbodyId) {
  const q = input.value.toLowerCase();
  document.querySelectorAll('#' + tbodyId + ' tr').forEach(r => {
    r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

// Init: activate 'ALL' filter by default
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.filter-btn[data-filter="ALL"]').forEach(b => b.click());
});
"""

# ── Helpers ────────────────────────────────────────────────────────────────

_STATUS_BADGE = {
    "PASSED":               '<span class="badge badge-green">✓ PASSOU</span>',
    "FAILED":               '<span class="badge badge-red">✗ FALHOU</span>',
    "ERROR":                '<span class="badge badge-red">⚠ ERRO</span>',
    "SKIPPED_NO_CACHE":     '<span class="badge badge-gray">— S/CACHE</span>',
    "SKIPPED_EXTERNAL_REF": '<span class="badge badge-purple">⤴ EXT REF</span>',
    "CYCLIC_SKIP":          '<span class="badge badge-yellow">↺ CÍCLICO</span>',
}

_PATTERN_COLOR = {
    PatternClass.ARITHMETIC:          ("blue",   "Aritmética"),
    PatternClass.CONDITIONAL:         ("yellow", "Condicional"),
    PatternClass.LOOKUP:              ("purple", "Lookup"),
    PatternClass.AGGREGATION:         ("green",  "Agregação"),
    PatternClass.DATE_LOGIC:          ("blue",   "Data/Hora"),
    PatternClass.TEXT_TRANSFORMATION: ("yellow", "Texto"),
    PatternClass.RANKING:             ("purple", "Ranking"),
    PatternClass.THRESHOLD_LOGIC:     ("gray",   "Limiar"),
    PatternClass.UNRESOLVED:          ("red",    "Não resolvido"),
    PatternClass.EXTERNAL_REF:        ("purple", "Ref. Externa"),
}

def _esc(v: Any) -> str:
    """Escapa valor para conteúdo HTML (text nodes)."""
    s = "" if v is None else str(v)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _esc_attr(v: Any) -> str:
    """Escapa valor para uso dentro de atributos HTML delimitados por aspas duplas."""
    return _esc(v).replace('"', "&quot;").replace("'", "&#39;")

def _truncate(v: Any, max_len: int) -> tuple[str, str]:
    """Retorna (display_html, attr_html) truncando o valor RAW antes de escapar.
    Evita partir entidades HTML (&lt; etc.) no meio."""
    raw = "" if v is None else str(v)
    display = _esc(raw[:max_len]) + ("…" if len(raw) > max_len else "")
    attr    = _esc_attr(raw)
    return display, attr

def _pct(num: int, den: int) -> str:
    if den == 0: return "—"
    return f"{num/den*100:.1f}%"

def _badge(status: str) -> str:
    return _STATUS_BADGE.get(status, f'<span class="badge badge-gray">{_esc(status)}</span>')

def _filter_buttons(tbody_id: str, counts: dict) -> str:
    buttons = [
        f'<button class="filter-btn active" data-tbody="{tbody_id}" data-filter="ALL" '
        f'onclick="filterTable(\'{tbody_id}\',\'ALL\')">Todos ({sum(counts.values())})</button>'
    ]
    for status, label in [
        ("FAILED",               "Falhou"),
        ("ERROR",                "Erro"),
        ("PASSED",               "Passou"),
        ("SKIPPED_NO_CACHE",     "S/Cache"),
        ("SKIPPED_EXTERNAL_REF", "Ext Ref"),
        ("CYCLIC_SKIP",          "Cíclico"),
    ]:
        if counts.get(status, 0) > 0:
            buttons.append(
                f'<button class="filter-btn" data-tbody="{tbody_id}" data-filter="{status}" '
                f'onclick="filterTable(\'{tbody_id}\',\'{status}\')">'
                f'{label} ({counts[status]})</button>'
            )
    return "\n".join(buttons)

# ── Seções do relatório ────────────────────────────────────────────────────

def _build_kpi_cards(results: list[ValidationResult]) -> str:
    total   = len(results)
    passed  = sum(1 for r in results if r.status == "PASSED")
    failed  = sum(1 for r in results if r.status == "FAILED")
    errors  = sum(1 for r in results if r.status == "ERROR")
    skipped = sum(1 for r in results if r.status in ("SKIPPED_NO_CACHE", "SKIPPED_EXTERNAL_REF", "CYCLIC_SKIP"))
    parity  = f"{passed/total*100:.1f}%" if total else "—"

    return f"""
<div class="kpi-grid">
  <div class="kpi green">
    <div class="kpi-value">{parity}</div>
    <div class="kpi-label">Paridade Geral</div>
  </div>
  <div class="kpi green">
    <div class="kpi-value">{passed}</div>
    <div class="kpi-label">Aprovados</div>
  </div>
  <div class="kpi red">
    <div class="kpi-value">{failed}</div>
    <div class="kpi-label">Divergências</div>
  </div>
  <div class="kpi red">
    <div class="kpi-value">{errors}</div>
    <div class="kpi-label">Erros</div>
  </div>
  <div class="kpi yellow">
    <div class="kpi-value">{skipped}</div>
    <div class="kpi-label">Pulados</div>
  </div>
  <div class="kpi blue">
    <div class="kpi-value">{total}</div>
    <div class="kpi-label">Total de Nós</div>
  </div>
</div>
"""

def _build_parity_bar(results: list[ValidationResult]) -> str:
    total  = len(results)
    passed = sum(1 for r in results if r.status == "PASSED")
    pct    = round(passed / total * 100, 1) if total else 0
    return f"""
<div class="section">
  <div class="section-header">
    <span>📊 Paridade Geral</span>
    <span style="color:var(--green);font-weight:700">{pct}% ({passed}/{total})</span>
  </div>
  <div class="pbar-wrap">
    <div class="pbar-fill" style="width:{pct}%"></div>
  </div>
</div>
"""

def _build_pattern_breakdown(
    results: list[ValidationResult],
    fmap: FormulaRegistryMap | None,
) -> str:
    """Tabela de paridade por PatternClass."""
    # Mapear node_id → pattern_class
    node_to_class: dict[str, str] = {}
    if fmap:
        for p in fmap.patterns:
            node_to_class[p.node_id] = p.pattern_class

    # Acumular por classe
    _UNCLASSIFIED = "__unclassified__"
    class_stats: dict[str, dict] = defaultdict(lambda: {"passed": 0, "failed": 0, "error": 0, "skip": 0})

    for r in results:
        pc = node_to_class.get(r.node_id) or _UNCLASSIFIED
        if r.status == "PASSED":   class_stats[pc]["passed"] += 1
        elif r.status == "FAILED": class_stats[pc]["failed"] += 1
        elif r.status == "ERROR":  class_stats[pc]["error"]  += 1
        else:                      class_stats[pc]["skip"]   += 1

    rows = []
    for pc, stats in sorted(class_stats.items(), key=lambda x: -(x[1]["passed"] + x[1]["failed"])):
        if pc == _UNCLASSIFIED:
            color, label = "gray", "Sem classificação"
        else:
            try:
                pc_enum = PatternClass(pc)
                color, label = _PATTERN_COLOR.get(pc_enum, ("gray", pc))
            except Exception:
                color, label = "gray", pc or "Desconhecido"

        total_cls = stats["passed"] + stats["failed"] + stats["error"] + stats["skip"]
        pct_cls   = round(stats["passed"] / total_cls * 100, 1) if total_cls else 0
        bar_w     = max(4, pct_cls)

        rows.append(f"""
<tr class="pattern-row">
  <td><span class="badge badge-{color}">{label}</span></td>
  <td>{total_cls}</td>
  <td style="color:var(--green);font-weight:600">{stats['passed']}</td>
  <td style="color:var(--red)">{stats['failed']}</td>
  <td style="color:var(--red)">{stats['error']}</td>
  <td style="color:var(--muted)">{stats['skip']}</td>
  <td style="min-width:120px">
    {pct_cls}%
    <div class="ptn-bar" style="width:{bar_w}%;max-width:100%"></div>
  </td>
</tr>""")

    return f"""
<div class="section">
  <div class="section-header">🗂 Breakdown por Padrão de Fórmula</div>
  <div class="section-body">
    <table>
      <thead>
        <tr>
          <th>Padrão</th><th>Total</th><th>Passou</th>
          <th>Falhou</th><th>Erro</th><th>Pulado</th><th>Paridade</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</div>
"""

def _build_results_table(results: list[ValidationResult], fmap: FormulaRegistryMap | None) -> str:
    """Tabela completa de resultados com filtros e busca."""
    node_to_formula: dict[str, str] = {}
    node_to_class:   dict[str, str] = {}
    if fmap:
        for p in fmap.patterns:
            node_to_formula[p.node_id] = p.formula_raw
            node_to_class[p.node_id]   = p.pattern_class

    counts: dict[str, int] = defaultdict(int)
    for r in results:
        counts[r.status] += 1

    rows = []
    for r in results:
        raw_formula = node_to_formula.get(r.node_id, "")
        pc          = node_to_class.get(r.node_id, "")
        try:
            pc_label = _PATTERN_COLOR.get(PatternClass(pc), ("gray", pc))[1] if pc else "—"
            pc_color = _PATTERN_COLOR.get(PatternClass(pc), ("gray", pc))[0] if pc else "gray"
        except Exception:
            pc_label, pc_color = pc or "—", "gray"

        formula_disp, formula_attr = _truncate(raw_formula, 80)
        expected_disp, _           = _truncate(r.expected_value, 60)
        actual_disp,   _           = _truncate(r.actual_value,   60)
        err_disp,      _           = _truncate(r.error_message,  80)

        diff_style = ""
        if r.status == "FAILED": diff_style = "background:#fef2f2"
        elif r.status == "ERROR": diff_style = "background:#fff7ed"

        rows.append(f"""
<tr data-status="{r.status}" style="{diff_style}">
  <td><span class="mono">{_esc(r.node_id)}</span></td>
  <td><span class="badge badge-{pc_color}" style="font-size:10px">{pc_label}</span></td>
  <td>{_badge(r.status)}</td>
  <td><span class="mono" title="{formula_attr}">{formula_disp}</span></td>
  <td><span class="mono">{expected_disp}</span></td>
  <td><span class="mono">{actual_disp}</span></td>
  <td style="color:var(--muted);font-size:12px">{err_disp}</td>
</tr>""")

    tbody_id = "results-tbody"
    return f"""
<div class="section">
  <div class="section-header">
    <span>🔍 Resultados Detalhados</span>
    <input type="search" placeholder="Buscar célula, fórmula..."
           oninput="searchTable(this, '{tbody_id}')" />
  </div>
  <div class="filter-bar">
    {_filter_buttons(tbody_id, counts)}
  </div>
  <div class="section-body" style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>Nó</th><th>Padrão</th><th>Status</th>
          <th>Fórmula</th><th>Esperado</th><th>Obtido</th><th>Mensagem</th>
        </tr>
      </thead>
      <tbody id="{tbody_id}">{''.join(rows)}</tbody>
    </table>
  </div>
</div>
"""

def _build_external_refs_section(results: list[ValidationResult]) -> str:
    ext_results = [r for r in results if r.status == "SKIPPED_EXTERNAL_REF"]
    if not ext_results:
        return ""

    rows = "".join(
        f'<tr><td><span class="mono">{_esc(r.node_id)}</span></td>'
        f'<td><span class="badge badge-purple">⤴ EXT REF</span></td>'
        f'<td style="color:var(--muted);font-size:12px">{_esc(r.error_message)}</td></tr>'
        for r in ext_results
    )
    return f"""
<div class="section">
  <div class="section-header">
    <span>⤴ Referências Externas ({len(ext_results)} células)</span>
  </div>
  <div class="section-body">
    <table>
      <thead><tr><th>Nó</th><th>Status</th><th>Motivo</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>
"""

# ── API pública ────────────────────────────────────────────────────────────

def generate_html_report(
    results: list[ValidationResult],
    output_path: Path,
    fmap: FormulaRegistryMap | None = None,
    source_file: str = "",
    title: str = "EXRS — Relatório de Paridade",
) -> Path:
    """
    Gera relatório HTML de validação e salva em output_path.
    Retorna o Path do arquivo gerado.
    """
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    total  = len(results)
    passed = sum(1 for r in results if r.status == "PASSED")
    pct    = f"{passed/total*100:.1f}%" if total else "—"

    body = "\n".join([
        _build_kpi_cards(results),
        _build_parity_bar(results),
        _build_pattern_breakdown(results, fmap),
        _build_external_refs_section(results),
        _build_results_table(results, fmap),
    ])

    source_label = f"<br><span style='font-size:12px;color:#94a3b8'>Arquivo: {_esc(source_file)}</span>" if source_file else ""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_esc(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="page">
  <div class="header">
    <h1>📊 {_esc(title)}</h1>
    <div class="sub">Gerado em {now} · Paridade: {pct} ({passed}/{total} nós){source_label}</div>
  </div>
  {body}
  <div class="footer">ExcelReverseEngine · Phase A4 Report Generator</div>
</div>
<script>{_JS}</script>
</body>
</html>"""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EXRS HTML Report Generator")
    parser.add_argument("results_json", type=Path,
                        help="JSON com list[ValidationResult] exportado pelo runner")
    parser.add_argument("--fmap",    type=Path, default=None,
                        help="JSON com FormulaRegistryMap (opcional, enriquece padrões)")
    parser.add_argument("--output",  type=Path, default=None,
                        help="Caminho de saída .html (padrão: mesmo dir do JSON)")
    parser.add_argument("--title",   default="EXRS — Relatório de Paridade")
    parser.add_argument("--source",  default="")
    args = parser.parse_args()

    if not args.results_json.exists():
        parser.error(f"Arquivo não encontrado: {args.results_json}")

    raw = json.loads(args.results_json.read_text(encoding="utf-8"))
    results = [ValidationResult.model_validate(r) for r in raw]

    fmap = None
    if args.fmap and args.fmap.exists():
        fmap = FormulaRegistryMap.model_validate_json(args.fmap.read_text(encoding="utf-8"))

    out = args.output or args.results_json.with_suffix(".html")
    path = generate_html_report(results, out, fmap=fmap, source_file=args.source, title=args.title)
    print(f"[OK] Relatório gerado: {path}")

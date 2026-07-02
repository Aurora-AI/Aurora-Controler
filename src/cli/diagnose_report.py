"""
EXRS CLI — Relatório de diagnóstico DAG (`exrs diagnose`).

Combina o HTML do grafo (gerado por phase_b2/html_visualizer.py, embutido sem modificação)
com uma tabela de riscos abaixo dele. O destaque visual dos riscos acontece na tabela, não
por recoloração dentro do canvas do grafo — decisão registrada em
docs/superpowers/specs/2026-07-02-exrs-diagnose-dag-design.md (evita modificar
html_visualizer.py, já testado).
"""
import datetime

from cli.risk_analysis import RiskFinding

_CATEGORY_LABELS = {
    "external_ref": "Referência externa",
    "unresolved": "Fórmula não classificada",
    "orphan_cell": "Célula órfã",
    "hardcoded_value": "Valor hardcoded",
}

_CATEGORY_COLORS = {
    "external_ref": "#DC2626",
    "unresolved": "#D97706",
    "orphan_cell": "#7C3AED",
    "hardcoded_value": "#2563EB",
}


def _esc(v: str) -> str:
    return (
        str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_findings_table(findings: list[RiskFinding]) -> str:
    if not findings:
        return "<p class='clean'>✅ Nenhum risco detectado nesta planilha.</p>"
    rows = "\n".join(
        f"<tr><td>{_esc(f.node_id)}</td>"
        f"<td><span class='badge' style='background:{_CATEGORY_COLORS.get(f.category, '#64748B')}'>"
        f"{_esc(_CATEGORY_LABELS.get(f.category, f.category))}</span></td>"
        f"<td>{_esc(f.description)}</td></tr>"
        for f in findings
    )
    return f"""
    <table class="risks">
      <thead><tr><th>Célula</th><th>Categoria</th><th>Descrição</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def render_diagnose_report(graph_html: str, findings: list[RiskFinding], source_file: str) -> str:
    """Retorna o HTML completo do relatório de diagnóstico."""
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    css = """
    body { font-family: -apple-system, sans-serif; background:#0F172A; color:#E2E8F0; margin:0; }
    .page { max-width: 1100px; margin: 0 auto; padding: 24px; }
    h1 { color:#F8FAFC; }
    .sub { color:#94A3B8; font-size:13px; margin-bottom:24px; }
    .graph-frame { border:1px solid #334155; border-radius:8px; overflow:hidden; margin-bottom:24px; }
    table.risks { width:100%; border-collapse:collapse; margin-top:12px; }
    table.risks th, table.risks td { text-align:left; padding:8px 12px; border-bottom:1px solid #334155; font-size:13px; }
    table.risks th { color:#94A3B8; font-weight:600; }
    .badge { color:#fff; padding:2px 8px; border-radius:4px; font-size:11px; }
    .clean { color:#4ADE80; }
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <title>EXRS — Diagnóstico de {_esc(source_file)}</title>
  <style>{css}</style>
</head>
<body>
<div class="page">
  <h1>🔍 Diagnóstico DAG — {_esc(source_file)}</h1>
  <div class="sub">Gerado em {now} · {len(findings)} risco(s) detectado(s)</div>
  <div class="graph-frame">{graph_html}</div>
  <h2>Riscos Detectados</h2>
  {_build_findings_table(findings)}
</div>
</body>
</html>"""

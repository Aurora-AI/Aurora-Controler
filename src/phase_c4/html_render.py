"""Fase C4 — Renderização do DashboardSpec em HTML + ECharts.

C4 é renderizador puro: lê o DashboardSpec, monta o HTML. Não calcula,
não interpreta, não altera o spec.
"""
from __future__ import annotations

import json

from dashboard_contracts import DashboardSpec

_ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"

_RENDER_JS = """
SPEC.components.forEach(function (comp) {
  var el = document.getElementById('comp-' + comp.id);
  if (!el) return;
  var dv = SPEC.data_views[comp.id];
  if (!dv) return;
  if (comp.type === 'kpi_cards') {
    el.className = 'kpi-row';
    dv.rows.forEach(function (r) {
      var card = document.createElement('div');
      card.className = 'kpi';
      card.innerHTML = '<div class="label">' + r.label + '</div>' +
        '<div class="value">' + (r.display_value || r.value) + '</div>';
      el.appendChild(card);
    });
  } else {
    var chart = echarts.init(el, 'dark');
    var keys = dv.rows.map(function (r) { return r.key; });
    var vals = dv.rows.map(function (r) { return r.value; });
    chart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 240, right: 80, top: 32, bottom: 32 },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: keys.slice().reverse() },
      series: [{ type: 'bar', data: vals.slice().reverse(),
                 itemStyle: { color: '#3b82f6' } }]
    });
  }
});
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<script src="__ECHARTS__"></script>
<style>
  body { margin:0; background:#0e1117; color:#e6e6e6;
         font-family:'Segoe UI',Arial,sans-serif;
         width:__WIDTH__px; height:__HEIGHT__px; }
  h1 { padding:32px 48px 0; font-size:44px; font-weight:700; }
  .grid { display:flex; flex-direction:column; gap:24px; padding:24px 48px; }
  .row { display:flex; gap:24px; }
  .panel { flex:1; background:#161b22; border-radius:12px; height:560px; }
  .kpi-row { display:flex; gap:24px; flex:1; }
  .kpi { flex:1; background:#161b22; border-radius:12px; padding:36px; }
  .kpi .label { font-size:26px; color:#8b949e; }
  .kpi .value { font-size:68px; font-weight:700; margin-top:12px; }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<div class="grid">__GRID__</div>
<script>
const SPEC = __SPEC_JSON__;
__RENDER_JS__
</script>
</body>
</html>
"""


def render_html(spec: DashboardSpec) -> str:
    """Renderiza o DashboardSpec num documento HTML autocontido."""
    comp_by_id = {c.id: c for c in spec.components}

    grid = ""
    for row in spec.layout.rows:
        cells = ""
        for cid in row:
            comp = comp_by_id.get(cid)
            if comp is None:
                continue
            css = "kpi-row" if comp.type == "kpi_cards" else "panel"
            cells += f'<div class="{css}" id="comp-{cid}"></div>'
        grid += f'<div class="row">{cells}</div>'

    spec_json = json.dumps(spec.model_dump(), ensure_ascii=False)

    html = _TEMPLATE
    html = html.replace("__TITLE__", spec.title)
    html = html.replace("__ECHARTS__", _ECHARTS_CDN)
    html = html.replace("__WIDTH__", str(spec.resolution.width))
    html = html.replace("__HEIGHT__", str(spec.resolution.height))
    html = html.replace("__GRID__", grid)
    html = html.replace("__SPEC_JSON__", spec_json)
    html = html.replace("__RENDER_JS__", _RENDER_JS)
    return html

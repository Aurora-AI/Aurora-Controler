"""
EXRS Phase B2 — HTML Visualizer

Gera uma visualização HTML self-contained do StagedRuleGraph usando vis-network.
Layout hierárquico LR: inputs à esquerda, outputs à direita.
Sem dependências além do vis-network via CDN.
"""
import json
import logging
from pathlib import Path

from pipeline_contracts import GraphNodeType, StagedRuleGraph

_log = logging.getLogger(__name__)

_VIS_CDN = "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/dist/vis-network.min.js"

# Paleta: alinhada com as CSS vars do html_reporter.py existente
_COLORS: dict[GraphNodeType, dict] = {
    GraphNodeType.INPUT: {
        "background": "#FEF3C7", "border": "#D97706",
        "highlight": {"background": "#FDE68A", "border": "#B45309"},
    },
    GraphNodeType.OUTPUT: {
        "background": "#D1FAE5", "border": "#059669",
        "highlight": {"background": "#A7F3D0", "border": "#047857"},
    },
    GraphNodeType.INTERMEDIATE: {
        "background": "#DBEAFE", "border": "#2563EB",
        "highlight": {"background": "#BFDBFE", "border": "#1D4ED8"},
    },
    GraphNodeType.STATIC: {
        "background": "#F3F4F6", "border": "#9CA3AF",
        "highlight": {"background": "#E5E7EB", "border": "#6B7280"},
    },
}


def _node_color(node_type: GraphNodeType) -> str:
    """Retorna a cor de borda para um tipo de nó (usada nos testes)."""
    return _COLORS[node_type]["border"]


def _vis_nodes(graph: StagedRuleGraph) -> list[dict]:
    """Converte GraphNodes para o formato de nós do vis.js."""
    nodes = []
    for n in graph.nodes:
        tooltip_parts = [f"<b>{n.id}</b>"]
        if n.formula:
            tooltip_parts.append(f"Fórmula: <code>{n.formula}</code>")
        if n.current_value is not None:
            tooltip_parts.append(f"Valor: {n.current_value}")
        if n.is_user_input:
            tooltip_parts.append("<i>📥 Parâmetro de entrada</i>")
        if n.is_user_output:
            tooltip_parts.append("<i>📤 Métrica monitorada</i>")

        node_dict = {
            "id": n.id,
            "label": n.label,
            "title": "<br/>".join(tooltip_parts),
            "color": _COLORS[n.node_type],
            "font": {"size": 13, "face": "monospace" if not (n.is_user_input or n.is_user_output) else "sans-serif"},
            "borderWidth": 3 if (n.is_user_input or n.is_user_output) else 1,
            "shadow": n.is_user_input or n.is_user_output,
        }
        nodes.append(node_dict)
    return nodes


def _vis_edges(graph: StagedRuleGraph) -> list[dict]:
    """Converte GraphEdges para o formato de arestas do vis.js."""
    return [
        {
            "from": e.source,
            "to": e.target,
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
            "color": {"color": "#CBD5E1", "highlight": "#94A3B8"},
            "smooth": {"type": "cubicBezier"},
        }
        for e in graph.edges
    ]


def generate_html(graph: StagedRuleGraph) -> str:
    """
    Gera uma string HTML self-contained com a visualização do StagedRuleGraph.

    Args:
        graph: StagedRuleGraph produzido pelo graph_assembler

    Returns:
        String HTML completa, pronta para salvar em arquivo.
    """
    vis_nodes_json = json.dumps(_vis_nodes(graph), ensure_ascii=False, indent=2)
    vis_edges_json = json.dumps(_vis_edges(graph), ensure_ascii=False, indent=2)

    intent = graph.intent
    inputs_html = "".join(
        f'<li><code>{p.node_id}</code> — {p.label}'
        + (f' <span class="range">[{p.suggested_range[0]}, {p.suggested_range[1]}]</span>'
           if p.suggested_range else "")
        + "</li>"
        for p in intent.input_parameters
    ) or "<li><em>Nenhum selecionado</em></li>"

    outputs_html = "".join(
        f'<li><code>{m.node_id}</code> — {m.label}</li>'
        for m in intent.output_metrics
    ) or "<li><em>Nenhum selecionado</em></li>"

    legend_html = "".join(
        f'<span class="leg-item"><span class="leg-dot" style="background:{_COLORS[t]["background"]};border:2px solid {_COLORS[t]["border"]}"></span>{label}</span>'
        for t, label in [
            (GraphNodeType.INPUT, "Entrada"),
            (GraphNodeType.OUTPUT, "Saída"),
            (GraphNodeType.INTERMEDIATE, "Intermediário"),
            (GraphNodeType.STATIC, "Estático"),
        ]
    )

    node_count = len(graph.nodes)
    edge_count = len(graph.edges)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>EXRS B2 — {graph.workbook_name}</title>
  <script src="{_VIS_CDN}"></script>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#F1F5F9;color:#1E293B;display:flex;height:100vh;overflow:hidden}}
    #sidebar{{width:300px;min-width:220px;background:#1E293B;color:#F8FAFC;padding:24px 18px;overflow-y:auto;flex-shrink:0}}
    #sidebar h1{{font-size:15px;font-weight:700;letter-spacing:-.2px;margin-bottom:4px;color:#F8FAFC}}
    #sidebar .sub{{font-size:11px;color:#94A3B8;margin-bottom:16px}}
    #sidebar h2{{font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.6px;color:#94A3B8;margin:16px 0 6px}}
    #sidebar .goal{{font-size:13px;color:#CBD5E1;line-height:1.5;background:#0F172A;padding:10px;border-radius:6px}}
    #sidebar ul{{list-style:none;padding:0}}
    #sidebar ul li{{font-size:12px;color:#CBD5E1;padding:4px 0;border-bottom:1px solid #334155}}
    #sidebar ul li code{{background:#334155;padding:1px 4px;border-radius:3px;font-size:11px;color:#93C5FD}}
    .range{{color:#FCD34D;font-size:11px}}
    #main{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
    #toolbar{{background:#fff;border-bottom:1px solid #E2E8F0;padding:10px 16px;display:flex;align-items:center;gap:16px;font-size:12px;color:#64748B}}
    .leg-item{{display:inline-flex;align-items:center;gap:5px}}
    .leg-dot{{width:14px;height:14px;border-radius:3px;display:inline-block}}
    .stats{{margin-left:auto;color:#94A3B8}}
    #network{{flex:1}}
  </style>
</head>
<body>
  <div id="sidebar">
    <h1>📊 {graph.workbook_name}</h1>
    <div class="sub">Phase B2 — Visual Assembly</div>
    <h2>Intenção</h2>
    <div class="goal">{intent.user_goal}</div>
    <h2>Entradas</h2>
    <ul>{inputs_html}</ul>
    <h2>Saídas</h2>
    <ul>{outputs_html}</ul>
    {f'<h2>Cenário</h2><div class="goal">{intent.scenario_description}</div>' if intent.scenario_description else ''}
  </div>
  <div id="main">
    <div id="toolbar">
      {legend_html}
      <span class="stats">{node_count} nós · {edge_count} arestas</span>
    </div>
    <div id="network"></div>
  </div>
  <script>
    const nodes = new vis.DataSet({vis_nodes_json});
    const edges = new vis.DataSet({vis_edges_json});
    const container = document.getElementById('network');
    const options = {{
      layout: {{
        hierarchical: {{
          enabled: true,
          direction: 'LR',
          sortMethod: 'directed',
          levelSeparation: 180,
          nodeSpacing: 120,
          treeSpacing: 200,
        }}
      }},
      nodes: {{shape: 'box', margin: 8, widthConstraint: {{maximum: 160}}}},
      edges: {{smooth: {{type: 'cubicBezier', forceDirection: 'horizontal'}}}},
      physics: {{enabled: false}},
      interaction: {{hover: true, tooltipDelay: 100, navigationButtons: true, keyboard: true}},
    }};
    new vis.Network(container, {{nodes, edges}}, options);
  </script>
</body>
</html>"""


def save_html(graph: StagedRuleGraph, output_path: "str | Path") -> None:
    """Gera e salva a visualização HTML em um arquivo."""
    Path(output_path).write_text(generate_html(graph), encoding="utf-8")
    _log.info("Visualização salva em: %s", output_path)

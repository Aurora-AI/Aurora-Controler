"""
EXRS Phase B2 — Entry Point

Uso:
    python -m phase_b2 output/Pasta1

Requer que os seguintes arquivos existam:
  output/Pasta1_a2_dag.json       (Phase A2)
  output/Pasta1_a15_norm.json     (Phase A1.5)
  output/Pasta1_b1_intent.json    (Phase B1)

Produz:
  output/Pasta1_b2_graph.json     (StagedRuleGraph serializado)
  output/Pasta1_b2_graph.html     (Visualização interativa vis.js)
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]

from graph_assembler import load_graph_from_prefix
from html_visualizer import save_html


def main(output_prefix: str) -> None:
    print(f"Carregando pipeline outputs: {output_prefix}")
    graph, _, _ = load_graph_from_prefix(output_prefix)

    json_out = Path(f"{output_prefix}_b2_graph.json")
    html_out = Path(f"{output_prefix}_b2_graph.html")

    json_out.write_text(graph.model_dump_json(indent=2), encoding="utf-8")
    save_html(graph, html_out)

    print(f"\n✅ Grafo montado: {len(graph.nodes)} nós, {len(graph.edges)} arestas")
    print(f"   JSON : {json_out}")
    print(f"   HTML : {html_out}")
    print(f"\n   Abra {html_out} no browser para visualizar o grafo interativo.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m phase_b2 output/<workbook_prefix>")
        sys.exit(1)
    main(sys.argv[1])

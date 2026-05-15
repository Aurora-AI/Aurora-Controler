"""Phase B3 — Entry point.

Uso:
    python -m phase_b3 output/Pasta1

Carrega {prefix}_b2_graph.json, executa HITL interativo,
salva {prefix}_b3_audit.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from pipeline_contracts import StagedRuleGraph
from hitl_loop import run_hitl


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m phase_b3 <prefix>", file=sys.stderr)
        print("Exemplo: python -m phase_b3 output/Pasta1", file=sys.stderr)
        sys.exit(1)

    prefix = Path(sys.argv[1])
    graph_path = Path(f"{prefix}_b2_graph.json")

    if not graph_path.exists():
        print(f"Erro: arquivo nao encontrado: {graph_path}", file=sys.stderr)
        sys.exit(1)

    graph = StagedRuleGraph.model_validate(json.loads(graph_path.read_text("utf-8")))
    print(f"Grafo carregado: {graph.workbook_name} ({len(graph.nodes)} nos, {len(graph.edges)} arestas)")

    audit = run_hitl(graph)

    out_path = Path(f"{prefix}_b3_audit.json")
    out_path.write_text(
        json.dumps(audit.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nAudit salvo em: {out_path}")
    print(f"Rodadas: {len(audit.steps)} | Intervencoes: {len(audit.hitl_interventions)}")
    print(f"Outcome: {audit.final_outcome}")


if __name__ == "__main__":
    main()

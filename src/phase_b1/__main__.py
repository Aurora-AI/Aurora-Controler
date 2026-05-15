"""
EXRS Phase B1 — Entry Point

Uso:
    python -m phase_b1 output/Pasta1

Onde 'output/Pasta1' é o prefixo dos arquivos do pipeline
(sem sufixo _a2_dag.json, _a15_norm.json, etc.).

O resultado é salvo em output/Pasta1_b1_intent.json.
"""
import json
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

# Setup paths
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from context_builder import load_summary_from_prefix
from chat_loop import run_chat


def main(output_prefix: str) -> None:
    print(f"Carregando workbook: {output_prefix}")
    summary = load_summary_from_prefix(output_prefix)

    intent = run_chat(summary)

    out_path = Path(f"{output_prefix}_b1_intent.json")
    out_path.write_text(intent.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n✅ IntentCapture salvo em: {out_path}")
    print(f"   Objetivo: {intent.user_goal}")
    print(f"   Entradas: {len(intent.input_parameters)} parâmetro(s)")
    print(f"   Saídas:   {len(intent.output_metrics)} métrica(s)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m phase_b1 output/<workbook_prefix>")
        sys.exit(1)
    main(sys.argv[1])

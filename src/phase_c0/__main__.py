"""Fase C0 — Entry point. Uso: python -m phase_c0 <arquivo.xlsx|.csv>"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]

from phase_c0.unpivot import build_c0_dataset


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m phase_c0 <arquivo.xlsx|.csv>", file=sys.stderr)
        sys.exit(1)

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"Erro: arquivo não encontrado: {src}", file=sys.stderr)
        sys.exit(1)

    try:
        dataset = build_c0_dataset(str(src))
    except (ValueError, OSError) as exc:
        print(f"Erro ao ingerir {src}: {exc}", file=sys.stderr)
        sys.exit(1)

    out_path = src.with_name(f"{src.stem}_c0_dataset.json")
    out_path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")

    vs = dataset.validation_summary
    print(f"C0 OK: {src.name} -> {out_path.name}")
    print(f"  Estratégia: {dataset.ingestion_strategy.used}")
    print(f"  Estrutura : {dataset.detected_structure.table_kind}")
    print(f"  Dataset   : {vs.dataset_rows_emitted} linhas | "
          f"descartadas: {vs.source_rows_discarded}")


if __name__ == "__main__":
    main()

"""Fase C1 — Entry point. Uso: python -m phase_c1 output/<prefix>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]

from libs.trustware.dashboard_contracts import C0Dataset
from phase_c1.semantic import build_semantic_model


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m phase_c1 output/<prefix>", file=sys.stderr)
        sys.exit(1)

    prefix = Path(sys.argv[1])
    c0_path = Path(f"{prefix}_c0_dataset.json")
    if not c0_path.exists():
        print(f"Erro: arquivo não encontrado: {c0_path}", file=sys.stderr)
        sys.exit(1)

    try:
        c0 = C0Dataset.model_validate(json.loads(c0_path.read_text(encoding="utf-8")))
    except Exception as exc:  # JSONDecodeError | ValidationError
        print(f"Erro: C0Dataset inválido em {c0_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    model = build_semantic_model(c0)
    out_path = Path(f"{prefix}_c1_semantic.json")
    out_path.write_text(model.model_dump_json(indent=2), encoding="utf-8")

    print(f"C1 OK: {out_path.name}")
    print(f"  Campos: {len(model.fields)} | "
          f"dimensão primária: {model.primary_dimension}")


if __name__ == "__main__":
    main()

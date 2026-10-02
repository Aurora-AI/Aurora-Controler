"""Fase C2 — Entry point. Uso: python -m phase_c2 output/<prefix>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]

from libs.trustware.dashboard_contracts import C0Dataset, SemanticModel
from phase_c2.metrics import build_metrics_report


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m phase_c2 output/<prefix>", file=sys.stderr)
        sys.exit(1)

    prefix = Path(sys.argv[1])
    c0_path = Path(f"{prefix}_c0_dataset.json")
    c1_path = Path(f"{prefix}_c1_semantic.json")
    for path in (c0_path, c1_path):
        if not path.exists():
            print(f"Erro: arquivo não encontrado: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        c0 = C0Dataset.model_validate(json.loads(c0_path.read_text(encoding="utf-8")))
        c1 = SemanticModel.model_validate(json.loads(c1_path.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"Erro: artefato inválido: {exc}", file=sys.stderr)
        sys.exit(1)

    report = build_metrics_report(c0, c1)
    out_path = Path(f"{prefix}_c2_metrics.json")
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print(f"C2 OK: {out_path.name}")
    print(f"  KPIs: {len(report.kpis)} | agregações: {len(report.aggregations)} "
          f"| anomalias: {len(report.anomalies)}")


if __name__ == "__main__":
    main()

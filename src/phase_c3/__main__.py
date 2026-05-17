"""Fase C3 — Entry point. Uso: python -m phase_c3 output/<prefix> [--llm]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dashboard_contracts import MetricsReport, SemanticModel
from spec_builder import build_dashboard_spec, validate_spec_self_contained
from narrative import generate_narrative


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_llm = "--llm" in sys.argv
    if not args:
        print("Uso: python -m phase_c3 output/<prefix> [--llm]", file=sys.stderr)
        sys.exit(1)

    prefix = Path(args[0])
    c1_path = Path(f"{prefix}_c1_semantic.json")
    c2_path = Path(f"{prefix}_c2_metrics.json")
    for path in (c1_path, c2_path):
        if not path.exists():
            print(f"Erro: arquivo não encontrado: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        c1 = SemanticModel.model_validate(json.loads(c1_path.read_text(encoding="utf-8")))
        c2 = MetricsReport.model_validate(json.loads(c2_path.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"Erro: artefato inválido: {exc}", file=sys.stderr)
        sys.exit(1)

    spec = build_dashboard_spec(
        c1, c2, dashboard_id=prefix.name, title=f"Dashboard — {prefix.name}",
        llm_used=use_llm,
    )
    if use_llm:
        spec.narrative = generate_narrative(c2)
        spec.llm_used = bool(spec.narrative)

    validate_spec_self_contained(spec)

    out_path = Path(f"{prefix}_c3_dashboard_spec.json")
    out_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    print(f"C3 OK: {out_path.name}")
    print(f"  Componentes: {len(spec.components)} | LLM: {spec.llm_used}")


if __name__ == "__main__":
    main()

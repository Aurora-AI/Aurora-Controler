"""
EXRS — Full Pipeline Runner (A0 → A3)
Executa todas as fases deterministicamente e gera artefatos JSON.
A fase A4 é executada apenas se existir cache de gabarito no Excel.
"""
import sys, json
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent
for mod_path in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_a0",
    REPO_ROOT / "src" / "phase_a1",
    REPO_ROOT / "src" / "phase_a1_5",
    REPO_ROOT / "src" / "phase_a2",
    REPO_ROOT / "src" / "phase_a2_5",
    REPO_ROOT / "src" / "phase_a3",
    REPO_ROOT / "src" / "phase_a4",
]:
    sys.path.insert(0, str(mod_path))

from classifier import classify_workbook
from extractor import extract_structure
from normalizer import normalize_workbook
from graph_builder import build_dag
from pattern_registry import classify_workbook as classify_patterns
from gabarito_extractor import extract_gabarito
from runner import validate_workbook
from repair_orchestrator import identify_repair_candidates
from pipeline_contracts import CertifiedModule

import math


def run(xlsx_path: Path, skip_llm: bool = True):
    out_dir = REPO_ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    stem = xlsx_path.stem

    print("\n" + "="*60)
    print(f"  EXRS Pipeline — {xlsx_path.name}")
    print("="*60)

    # ── A0: Classifier ────────────────────────────────────────
    print("\n[A0] Classificando workbook...")
    report = classify_workbook(xlsx_path)
    (out_dir / f"{stem}_a0_report.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    print(f"     Classe   : {report.workbook_class.value}")
    print(f"     Decisão  : {report.compile_decision.value}")
    if report.escalate_reasons:
        for r in report.escalate_reasons:
            print(f"     ⚠ {r}")

    from pipeline_contracts import CompileDecision
    if report.compile_decision == CompileDecision.ESCALATE:
        print("\n[!] Pipeline interrompido: workbook UNSUPPORTED.")
        return

    # ── A1: Extractor ─────────────────────────────────────────
    print("\n[A1] Extraindo estrutura...")
    raw_ir = extract_structure(xlsx_path)
    total_cells = sum(len(s.cells) for s in raw_ir.sheets)
    total_formulas = sum(1 for s in raw_ir.sheets for c in s.cells if c.formula)
    print(f"     Planilhas : {len(raw_ir.sheets)}")
    print(f"     Células   : {total_cells}")
    print(f"     Fórmulas  : {total_formulas}")
    (out_dir / f"{stem}_a1_ir.json").write_text(
        raw_ir.model_dump_json(indent=2), encoding="utf-8"
    )

    # ── A1.5: Normalizer ──────────────────────────────────────
    print("\n[A1.5] Normalizando IR...")
    norm_ir = normalize_workbook(raw_ir)
    locale = norm_ir.normalization_info.get("locale", "?")
    print(f"     Locale detectado: {locale}")
    (out_dir / f"{stem}_a15_norm.json").write_text(
        norm_ir.model_dump_json(indent=2), encoding="utf-8"
    )

    # ── A2: Graph Builder ─────────────────────────────────────
    print("\n[A2] Construindo DAG...")
    dag = build_dag(norm_ir)
    print(f"     Nós         : {len(dag.nodes)}")
    print(f"     Arestas     : {len(dag.edges)}")
    print(f"     Ciclos      : {len(dag.cycles)}")
    if dag.cycles:
        for cycle in dag.cycles[:3]:
            print(f"     ↺ {cycle.cycle_type.value}: {' → '.join(cycle.node_ids[:4])}")
    (out_dir / f"{stem}_a2_dag.json").write_text(
        dag.model_dump_json(indent=2), encoding="utf-8"
    )

    # ── A2.5: Pattern Registry ────────────────────────────────
    print("\n[A2.5] Classificando padrões de fórmula...")
    from pattern_registry import build_registry
    fmap = classify_patterns(norm_ir, build_registry())
    from pipeline_contracts import PatternClass
    counts = {}
    for p in fmap.patterns:
        counts[p.pattern_class.value] = counts.get(p.pattern_class.value, 0) + 1
    for cls, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"     {cls:<25} : {n}")
    (out_dir / f"{stem}_a25_fmap.json").write_text(
        fmap.model_dump_json(indent=2), encoding="utf-8"
    )

    unresolved_count = counts.get("unresolved", 0)

    # ── A3: LLM Translator ────────────────────────────────────
    if unresolved_count == 0:
        print(f"\n[A3] Nenhuma fórmula UNRESOLVED — LLM não necessário.")
        from pipeline_contracts import DomainModule
        domain = DomainModule(
            file_path=str(xlsx_path),
            imports=[],
            functions=[],
            generated_at=datetime.now().isoformat(),
            translation_metadata={"total_unresolved": 0, "total_functions": 0}
        )
    elif skip_llm:
        print(f"\n[A3] {unresolved_count} fórmula(s) UNRESOLVED (LLM pulado em modo --no-llm).")
        from pipeline_contracts import DomainModule
        domain = DomainModule(
            file_path=str(xlsx_path),
            imports=[],
            functions=[],
            generated_at=datetime.now().isoformat(),
            translation_metadata={"total_unresolved": unresolved_count, "total_functions": 0}
        )
    else:
        print(f"\n[A3] Traduzindo {unresolved_count} fórmula(s) UNRESOLVED via LLM...")
        from translator import translate_workbook
        domain = translate_workbook(norm_ir, fmap)
        print(f"     Funções geradas: {len(domain.functions)}")

    (out_dir / f"{stem}_a3_domain.json").write_text(
        domain.model_dump_json(indent=2), encoding="utf-8"
    )

    # ── A4: Validation ────────────────────────────────────────
    print("\n[A4] Extraindo gabarito e validando...")
    gabarito, missing_cache = extract_gabarito(xlsx_path)
    if not gabarito:
        print("     ⚠ Gabarito vazio (Excel sem cache calculado). Pulando validação.")
        print("\n[DONE] Pipeline A0→A3 concluído. Artefatos em:", out_dir)
        return

    results = validate_workbook(dag, domain, fmap, norm_ir, gabarito, missing_cache)
    passed   = [r for r in results if r.passed]
    failed   = [r for r in results if not r.passed and r.status != "SKIPPED_NO_CACHE"]
    skipped  = [r for r in results if r.status == "SKIPPED_NO_CACHE"]
    evaluated = len(results) - len(skipped)
    parity = len(passed) / evaluated if evaluated > 0 else 1.0

    print(f"     Avaliados : {evaluated}")
    print(f"     ✓ Passou  : {len(passed)}")
    print(f"     ✗ Falhou  : {len(failed)}")
    print(f"     ⊘ Pulados : {len(skipped)}")
    print(f"     Paridade  : {parity:.1%}")

    validation_report = identify_repair_candidates(results, fmap)
    status = "PASSED" if parity >= 1.0 else ("PARTIAL" if parity > 0 else "FAILED")
    certified = CertifiedModule(
        original_file=xlsx_path.name,
        domain_module=domain,
        validation_report=validation_report,
        certification_status=status,
        certified_at=datetime.now().isoformat(),
    )
    (out_dir / f"{stem}_a4_certified.json").write_text(
        certified.model_dump_json(indent=2), encoding="utf-8"
    )

    failed_results = [r for r in results if not r.passed and r.status != "SKIPPED_NO_CACHE"]
    if failed_results:
        print(f"\n     Primeiras divergências:")
        for r in failed_results[:5]:
            print(f"     • {r.node_id}: esperado={r.expected_value}, obtido={r.actual_value}")

    print(f"\n[DONE] Pipeline completo. Artefatos em: {out_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EXRS Full Pipeline Runner")
    parser.add_argument("xlsx", type=Path, help="Caminho para o arquivo .xlsx")
    parser.add_argument("--llm", action="store_true", help="Ativar LLM para fórmulas UNRESOLVED")
    args = parser.parse_args()

    if not args.xlsx.exists():
        print(f"Erro: arquivo não encontrado: {args.xlsx}")
        sys.exit(1)

    run(args.xlsx, skip_llm=not args.llm)

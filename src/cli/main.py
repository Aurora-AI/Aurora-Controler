"""
EXRS CLI — entry point `exrs`.

`exrs compile <arquivo.xlsx>` roda a Trilha A (A0→A4) local, sem servidor, sem
Celery/Redis, e monta uma pasta de saída limpa com o .py replay + relatório .html.
`exrs ui` sobe uma interface web local (ver src/cli/web_app.py, Task 4).
"""
import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

from libs.trustware.pipeline_contracts import ExecutionDAG, FormulaRegistryMap, NormalizedWorkbookIR
from orchestrator.storage_manager import StorageManager
from orchestrator.pipeline_orchestrator import orchestrate_pipeline

from cli.output import write_clean_output

from kernel.phase_a0.classifier import classify_workbook as classify_a0
from kernel.phase_a1.extractor import extract_structure
from kernel.phase_a1_5.normalizer import normalize_workbook
from product_a.phase_a2.graph_builder import build_dag
from product_a.phase_a2_5.pattern_registry import classify_workbook as classify_patterns, build_registry
from orchestrator.pipeline_orchestrator import route
from libs.trustware.pipeline_contracts import IntentCapture
from product_a.phase_b2.graph_assembler import build_graph
from product_a.phase_b2.html_visualizer import generate_html

from cli.risk_analysis import analyze_risks
from cli.diagnose_report import render_diagnose_report

from product_b.oracle.column_mapper import ColumnMappingError, DateAmbiguityError
from product_b.oracle.commercial_auditor import run_audit
from cli.audit_report import render_audit_report


def run_compile_cli(xlsx_path: Path, dest_dir: Path | None, debug: bool, chat: bool) -> int:
    if not xlsx_path.exists():
        print(f"Erro: arquivo não encontrado: {xlsx_path}", file=sys.stderr)
        return 1

    stem = xlsx_path.stem
    storage = StorageManager(job_id=stem)
    result = orchestrate_pipeline(xlsx_path, storage, skip_llm=not chat)

    status = result.get("status")
    if status in {"ESCALATED", "NOT_IMPLEMENTED", "SKIPPED_NO_CACHE", "GATE_REJECTED"}:
        print(f"[EXRS] Não foi possível gerar código: {status}", file=sys.stderr)
        reason = result.get("reason")
        if reason:
            print(f"       Motivo: {reason}", file=sys.stderr)
        return 1

    if status not in {"PASSED", "PARTIAL", "FAILED"}:
        print(f"[EXRS] Erro interno: status desconhecido do pipeline: {status}", file=sys.stderr)
        return 1

    certified = result.get("certified")
    if certified is None:
        print("[EXRS] Erro interno: pipeline concluiu sem CertifiedModule.", file=sys.stderr)
        return 1

    dag = ExecutionDAG.model_validate_json(
        (storage.output_dir / f"{stem}_a2_dag.json").read_text(encoding="utf-8")
    )
    fmap = FormulaRegistryMap.model_validate_json(
        (storage.output_dir / f"{stem}_a25_fmap.json").read_text(encoding="utf-8")
    )
    norm_ir = NormalizedWorkbookIR.model_validate_json(
        (storage.output_dir / f"{stem}_a15_norm.json").read_text(encoding="utf-8")
    )

    dest = dest_dir or Path.cwd() / f"{stem}_output"
    write_clean_output(storage.output_dir, stem, certified, dag, fmap, norm_ir, dest, debug=debug)

    print(f"[EXRS] Status: {status}")
    print(f"[EXRS] Saída: {dest}")
    return 0


def run_diagnose_cli(xlsx_path: Path, dest_dir: Path | None) -> int:
    if not xlsx_path.exists():
        print(f"Erro: arquivo não encontrado: {xlsx_path}", file=sys.stderr)
        return 1

    stem = xlsx_path.stem

    report = classify_a0(xlsx_path)
    track = route(report.workbook_class, report.compile_decision, xlsx_path)
    if track != "track_a":
        print(f"[EXRS] Diagnóstico não aplicável a este arquivo (classificação: {track}).",
              file=sys.stderr)
        if report.escalate_reasons:
            print(f"       Motivos: {', '.join(report.escalate_reasons)}", file=sys.stderr)
        return 1

    raw_ir = extract_structure(xlsx_path)
    norm_ir = normalize_workbook(raw_ir)
    dag = build_dag(norm_ir)
    fmap = classify_patterns(norm_ir, build_registry())

    findings = analyze_risks(dag, fmap, norm_ir)

    intent = IntentCapture(workbook_name=stem, user_goal="", input_parameters=[], output_metrics=[])
    graph = build_graph(dag.model_dump(), norm_ir.model_dump(), intent)
    graph_html = generate_html(graph)

    report_html = render_diagnose_report(graph_html, findings, source_file=xlsx_path.name)

    dest = dest_dir or Path.cwd() / f"{stem}_diagnostico"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "relatorio.html").write_text(report_html, encoding="utf-8")

    print(f"[EXRS] Diagnóstico concluído: {len(findings)} risco(s) detectado(s).")
    print(f"[EXRS] Relatório: {dest / 'relatorio.html'}")
    return 0


def run_audit_cli(path: Path, dest_dir: Path | None, mapping_path: Path | None) -> int:
    if not path.exists():
        print(f"Erro: caminho não encontrado: {path}", file=sys.stderr)
        return 1

    mapping_override = None
    if mapping_path is not None:
        mapping_override = json.loads(mapping_path.read_text(encoding="utf-8"))

    try:
        report, identity_map = run_audit(
            path, mapping_override=mapping_override, return_identity_map=True,
        )
    except (ColumnMappingError, DateAmbiguityError) as e:
        print(f"[EXRS] Não foi possível auditar: {e}", file=sys.stderr)
        return 1

    if report.cleaning.rows_accepted == 0:
        print("[EXRS] Nenhuma linha de venda válida após a limpeza.", file=sys.stderr)
        print(f"       Resumo da limpeza: {report.cleaning.model_dump()}", file=sys.stderr)
        return 1

    dest = dest_dir or Path.cwd() / f"{path.stem}_auditoria"
    dest.mkdir(parents=True, exist_ok=True)

    (dest / "audit_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (dest / "identity_map.json").write_text(json.dumps({
        "_aviso": "Este arquivo contém identidades REAIS de clientes — NÃO enviar a "
                  "serviços externos/nuvem. Use apenas para tradução local no ecrã.",
        "identity_map": identity_map,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    report_html = render_audit_report(report, identity_map, source_label=path.name)
    (dest / "relatorio.html").write_text(report_html, encoding="utf-8")

    print(f"[EXRS] Auditoria concluída: {len(report.revenue_leaks)} vazamento(s) de receita, "
          f"{len(report.churn_findings)} cliente(s) em churn.")
    print(f"[EXRS] Saída: {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="exrs", description="EXRS — Reversão de planilhas Excel para Python")
    sub = parser.add_subparsers(dest="command")

    compile_parser = sub.add_parser("compile", help="Reverte uma planilha .xlsx em código Python")
    compile_parser.add_argument("xlsx", nargs="?", type=Path, help="Caminho para o arquivo .xlsx")
    compile_parser.add_argument("--out", type=Path, default=None, help="Pasta de saída (padrão: ./<nome>_output)")
    compile_parser.add_argument("--debug", action="store_true", help="Mantém os JSONs técnicos por fase na saída")
    compile_parser.add_argument("--chat", action="store_true", help="Ativa captura de intenção via LLM (Trilha B)")

    diagnose_parser = sub.add_parser("diagnose", help="Gera um relatório de diagnóstico (grafo + riscos)")
    diagnose_parser.add_argument("xlsx", nargs="?", type=Path, help="Caminho para o arquivo .xlsx")
    diagnose_parser.add_argument("--out", type=Path, default=None, help="Pasta de saída (padrão: ./<nome>_diagnostico)")

    audit_parser = sub.add_parser("audit", help="Auditoria forense comercial (Data Oracle) — pasta ou arquivo de vendas")
    audit_parser.add_argument("path", nargs="?", type=Path, help="Pasta ou arquivo .xlsx/.csv de histórico de vendas")
    audit_parser.add_argument("--out", type=Path, default=None, help="Pasta de saída (padrão: ./<nome>_auditoria)")
    audit_parser.add_argument("--mapping", type=Path, default=None, help="JSON de mapeamento manual de colunas")

    sub.add_parser("ui", help="Abre a interface web local")

    args = parser.parse_args(argv)

    if args.command == "compile":
        if args.xlsx is None:
            compile_parser.print_usage(sys.stderr)
            return 2
        return run_compile_cli(args.xlsx, args.out, args.debug, args.chat)

    if args.command == "diagnose":
        if args.xlsx is None:
            diagnose_parser.print_usage(sys.stderr)
            return 2
        return run_diagnose_cli(args.xlsx, args.out)

    if args.command == "audit":
        if args.path is None:
            audit_parser.print_usage(sys.stderr)
            return 2
        return run_audit_cli(args.path, args.out, args.mapping)

    if args.command == "ui":
        from cli.web_app import serve
        serve()
        return 0

    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

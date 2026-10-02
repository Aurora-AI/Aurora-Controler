"""
EXRS — Full Pipeline Runner (CLI Wrapper)
Executa o pipeline chamando o pipeline_orchestrator com um StorageManager.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent

from orchestrator.storage_manager import StorageManager
from orchestrator.pipeline_orchestrator import orchestrate_pipeline

def _setup_b_paths():
    """Adiciona módulos das fases B ao sys.path (Removido)."""
    pass

def run(xlsx_path: Path, skip_llm: bool = True, run_hitl_flag: bool = False, job_id: str = None):
    stem = xlsx_path.stem
    if job_id is None:
        job_id = stem
        
    out_dir = REPO_ROOT / "output" / job_id
    storage = StorageManager(job_id=job_id, output_base_dir=REPO_ROOT / "output")

    print("\n" + "="*60)
    print(f"  EXRS Pipeline Orchestrator — {xlsx_path.name}")
    print(f"  Job ID: {job_id}")
    print("="*60)

    result = orchestrate_pipeline(xlsx_path, storage, skip_llm=skip_llm)
    
    status = result.get("status")
    print(f"\n[PIPELINE] A0→A4 concluído. Status: {status}")
    print(f"[PIPELINE] Artefatos salvos em: {out_dir}")

    # ── B1: Intent Capture ────────────────────────────────────
    if not skip_llm:
        print("\n[B1] Capturando intenção do usuário via chat...")
        _setup_b_paths()
        from product_a.phase_b1.context_builder import load_summary_from_prefix
        from product_a.phase_b1.chat_loop import run_chat
        summary = load_summary_from_prefix(str(out_dir / f"{stem}"))
        intent = run_chat(summary)
        storage.write_artifact(stem, "b1_intent", intent)
        print(f"     Objetivo: {intent.user_goal}")

        # ── B2: Visual Assembly ───────────────────────────────
        print("\n[B2] Montando grafo visual...")
        from product_a.phase_b2.graph_assembler import load_graph_from_prefix
        from product_a.phase_b2.html_visualizer import save_html
        graph, _, _ = load_graph_from_prefix(str(out_dir / f"{stem}"))
        storage.write_artifact(stem, "b2_graph", graph)
        save_html(graph, out_dir / f"{stem}_b2_graph.html")
        print(f"     {len(graph.nodes)} nós | {len(graph.edges)} arestas")

        # ── B3: Simulation + HITL ─────────────────────────────
        if run_hitl_flag:
            print("\n[B3] Iniciando simulação HITL interativa...")
            from product_a.phase_b3.hitl_loop import run_hitl
            audit = run_hitl(graph)
            storage.write_artifact(stem, "b3_audit", audit)
            print(f"     Rodadas: {len(audit.steps)} | Intervenções: {len(audit.hitl_interventions)}")
            print(f"     Outcome: {audit.final_outcome}")
        else:
            print("\n[B3] Simulação HITL pulada (use --hitl para ativar).")
    else:
        print("\n[B1/B2/B3] Fases B puladas (use --llm para ativar).")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EXRS Full Pipeline Runner")
    parser.add_argument("xlsx", type=Path, help="Caminho para o arquivo .xlsx")
    parser.add_argument("--llm", action="store_true", help="Ativar LLM para fórmulas UNRESOLVED")
    parser.add_argument("--hitl", action="store_true", help="Ativar simulação HITL interativa (B3)")
    parser.add_argument("--job-id", type=str, help="ID customizado do job (opcional)", default=None)
    args = parser.parse_args()

    if not args.xlsx.exists():
        print(f"Erro: arquivo não encontrado: {args.xlsx}")
        sys.exit(1)

    run(args.xlsx, skip_llm=not args.llm, run_hitl_flag=args.hitl, job_id=args.job_id)

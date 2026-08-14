"""
EXRS Phase A4 — Deterministic Validation Orchestrator
Fecha o ciclo de compilação com validação e certificação.
"""
import sys, json, os
from pathlib import Path
from datetime import datetime

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[2]


from product_a.phase_a4.gabarito_extractor import extract_gabarito
from product_a.phase_a4.runner import validate_workbook
from product_a.phase_a4.repair_orchestrator import identify_repair_candidates
from libs.trustware.pipeline_contracts import (
    ExecutionDAG, DomainModule, FormulaRegistryMap, NormalizedWorkbookIR,
    CertifiedModule, ValidationResult
)

def run_phase_a4(
    xlsx_path: Path,
    dag_path: Path,
    domain_path: Path,
    fmap_path: Path,
    norm_path: Path,
    output_path: Path
):
    print(f"[*] Iniciando Phase A4: Validação Determinística para {xlsx_path.name}")
    
    # 1. Carregar artefatos anteriores
    with open(dag_path, 'r') as f: dag = ExecutionDAG(**json.load(f))
    with open(domain_path, 'r') as f: domain = DomainModule(**json.load(f))
    with open(fmap_path, 'r') as f: fmap = FormulaRegistryMap(**json.load(f))
    with open(norm_path, 'r') as f: norm = NormalizedWorkbookIR(**json.load(f))
    
    # 2. Extrair Gabarito (Double Pass)
    print("[*] Extraindo gabarito do Excel...")
    gabarito, missing_cache = extract_gabarito(xlsx_path)
    
    # 3. Executar Validação
    print("[*] Executando simulação e comparação bit-a-bit...")
    results = validate_workbook(dag, domain, fmap, norm, gabarito, missing_cache)
    
    # 4. Analisar Resultados
    passed_count = len([r for r in results if r.passed])
    failed_count = len([r for r in results if not r.passed and r.status not in ("SKIPPED_NO_CACHE", "SKIPPED_EXTERNAL_REF", "CYCLIC_SKIP")])
    skipped_count = len([r for r in results if r.status in ("SKIPPED_NO_CACHE", "SKIPPED_EXTERNAL_REF", "CYCLIC_SKIP")])
    
    mismatches = identify_repair_candidates(results, fmap)
    parity_score = (passed_count / (len(results) - skipped_count)) if (len(results) - skipped_count) > 0 else 1.0
    
    # 5. Gerar Módulo Certificado
    certified = CertifiedModule(
        file_path=xlsx_path.name,
        domain_module=domain,
        validation_results=results,
        parity_score=parity_score,
        certification_date=datetime.now().isoformat(),
        mismatch_reports=mismatches,
        audit_logs=[f"Validated {len(results)} nodes. Parity: {parity_score:.2%}"]
    )
    
    # Salvar resultado
    with open(output_path, 'w') as f:
        f.write(certified.model_dump_json(indent=2))
        
    print(f"[+] Phase A4 Concluída. Score de Paridade: {parity_score:.2%}")
    print(f"[+] Artefato gerado: {output_path}")
    
    if mismatches:
        print(f"[!] {len(mismatches)} divergências detectadas. Repair Loop necessário.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--dag", type=Path, required=True)
    parser.add_argument("--domain", type=Path, required=True)
    parser.add_argument("--fmap", type=Path, required=True)
    parser.add_argument("--norm", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "certified_module.json")
    args = parser.parse_args()
    
    run_phase_a4(args.xlsx, args.dag, args.domain, args.fmap, args.norm, args.output)

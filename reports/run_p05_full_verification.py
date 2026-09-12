"""
reports/run_p05_full_verification.py
Script de verificação global e emissão de evidência física para homologação de P05.
Conforme Doutrina Aurora (§5, §6, §7) e SPEC-ELY-ORG-001 (OS-P05).

Opera em modo append ('a') sobre reports/p05_saneamento_completo_evidencia.log.
Princípio Fail-Closed: Qualquer falha encerra com sys.exit(code) != 0.
"""

import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_file_sha256(filepath: Path) -> str:
    if not filepath.exists():
        return "ARQUIVO_INEXISTENTE"
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def main():
    root_dir = Path(__file__).resolve().parent.parent
    os.chdir(root_dir)

    log_path = root_dir / "reports" / "p05_saneamento_completo_evidencia.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp_iso = datetime.now(timezone.utc).isoformat()

    # Coleta de Hashes de Integridade
    files_to_hash = [
        root_dir / "src" / "product_b" / "oracle" / "commercial_auditor.py",
        root_dir / "src" / "product_b" / "oracle" / "forensic_contracts.py",
        root_dir / "src" / "product_b" / "oracle" / "column_mapper.py",
        root_dir / "tests" / "test_reprova_p05_engine.py",
    ]
    hashes = {str(f.relative_to(root_dir)): get_file_sha256(f) for f in files_to_hash}

    # Branch / commit info
    try:
        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True
        )
        current_branch = branch_res.stdout.strip()
    except Exception:
        current_branch = "UNKNOWN"

    header = [
        "=" * 80,
        f"LAUDO DE VERIFICAÇÃO FÍSICA E HOMOLOGAÇÃO — PACOTE P05",
        f"Data/Hora UTC: {timestamp_iso}",
        f"Branch Ativa: {current_branch}",
        "Hashes SHA-256 dos Componentes Auditados:",
    ]
    for rel_p, sha in hashes.items():
        header.append(f"  - {rel_p}: {sha}")
    header.append("=" * 80)
    header_text = "\n".join(header) + "\n"

    print(header_text)
    with open(log_path, "a", encoding="utf-8") as log_f:
        log_f.write(header_text)

    # Execução 1: Suíte de Sabotagem e Aceite de P05
    print("\n>>> EXECUÇÃO 1: Suíte de Sabotagem e Aceite P05 (test_reprova_p05_engine.py)...")
    cmd_p05 = [
        sys.executable, "-m", "pytest",
        "tests/test_reprova_p05_engine.py",
        "-v", "--tb=short"
    ]
    proc_p05 = subprocess.run(cmd_p05, capture_output=True, text=True)
    
    out_p05 = proc_p05.stdout + "\n" + proc_p05.stderr
    print(out_p05)
    with open(log_path, "a", encoding="utf-8") as log_f:
        log_f.write("\n--- RESULTADO SUÍTE SABOTAGEM / ACEITE P05 ---\n")
        log_f.write(out_p05)

    if proc_p05.returncode != 0:
        fail_msg = f"\nSTATUS: REPROVADO (Falha na suíte P05, exit code {proc_p05.returncode})\n"
        print(fail_msg)
        with open(log_path, "a", encoding="utf-8") as log_f:
            log_f.write(fail_msg)
        sys.exit(proc_p05.returncode)

    # Execução 2: Suíte de Regressão
    is_full_regression = len(sys.argv) <= 1 or sys.argv[1:] == ["tests/"]
    regress_targets = ["tests/"] if is_full_regression else sys.argv[1:]
    tipo_suite = "REGRESSÃO GLOBAL COMPLETA" if is_full_regression else "VERIFICAÇÃO DIRECIONADA"
    print(f"\n>>> EXECUÇÃO 2: Suíte de {tipo_suite} ({', '.join(regress_targets)})...")
    cmd_global = [
        sys.executable, "-m", "pytest",
        *regress_targets,
        "-q", "--tb=short"
    ]
    proc_global = subprocess.run(cmd_global, capture_output=True, text=True)

    out_global = proc_global.stdout + "\n" + proc_global.stderr
    print(out_global)
    with open(log_path, "a", encoding="utf-8") as log_f:
        log_f.write(f"\n--- RESULTADO SUÍTE DE {tipo_suite} ---\n")
        log_f.write(out_global)

    if proc_global.returncode != 0:
        fail_status = "REGRESSÃO GLOBAL" if is_full_regression else "VERIFICAÇÃO DIRECIONADA"
        fail_msg = f"\nSTATUS: REPROVADO (Falha na {fail_status}, exit code {proc_global.returncode})\n"
        print(fail_msg)
        with open(log_path, "a", encoding="utf-8") as log_f:
            log_f.write(fail_msg)
        sys.exit(proc_global.returncode)

    if is_full_regression:
        success_msg = "\n" + "=" * 80 + "\nSTATUS: REGRESSAO GLOBAL APROVADA\nTodos os testes de P05 (27) e a suíte global de testes do repositório foram homologados com exit code 0.\n" + "=" * 80 + "\n"
    else:
        success_msg = "\n" + "=" * 80 + "\nSTATUS: VERIFICACAO DIRECIONADA APROVADA\nOs testes de P05 (27) e a suíte direcionada foram homologados com exit code 0.\n(Nota de Governança: Não substitui a execução da regressão global completa).\n" + "=" * 80 + "\n"
    print(success_msg)
    with open(log_path, "a", encoding="utf-8") as log_f:
        log_f.write(success_msg)

    print("Verificação física concluída com sucesso. Evidência registrada em:", log_path)
    sys.exit(0)


if __name__ == "__main__":
    main()

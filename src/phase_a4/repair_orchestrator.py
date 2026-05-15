"""
EXRS Phase A4 — Repair Orchestrator
Identifica divergências e aciona o LLM para correção ou escala para auditoria humana.
"""
import sys, os
from pathlib import Path
from typing import List

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a3"))

from pipeline_contracts import (
    ValidationResult, MismatchReport, DomainModule, DomainFunction,
    FormulaRegistryMap, PatternClass
)
# Note: I'll need to use litellm or similar here too if I want automated repair.

def identify_repair_candidates(results: List[ValidationResult], fmap: FormulaRegistryMap) -> MismatchReport:
    """Consolida todos os resultados em um MismatchReport sumário."""
    passed   = sum(1 for r in results if r.passed)
    failed   = sum(1 for r in results if not r.passed and r.status != "SKIPPED_NO_CACHE")
    skipped  = sum(1 for r in results if r.status == "SKIPPED_NO_CACHE")

    return MismatchReport(
        total_nodes=len(results),
        passed=passed,
        failed=failed,
        skipped_no_cache=skipped,
        results=results,
        repair_attempts=0,
    )

def generate_repair_prompt(mismatch: MismatchReport, function: DomainFunction) -> str:
    """Gera prompt para o LLM corrigir a função."""
    return f"""
O sistema de validação detectou uma divergência na função Python traduzida.

Nó: {mismatch.node_id}
Valor esperado (Excel): {mismatch.expected_value}
Valor obtido (Python): {mismatch.actual_value}
Erro: {mismatch.error_message}

Código atual:
```python
{function.code}
```

Por favor, analise a lógica e corrija o código Python para garantir a paridade com o Excel.
Retorne APENAS o código Python corrigido dentro de um bloco de código.
"""

# No MVP, vamos apenas listar os reparos necessários.
# A execução real do litellm seria similar à Phase A3.

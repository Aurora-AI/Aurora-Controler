"""
EXRS Phase A4 — Repair Orchestrator  [STUB MVP]

Estado atual: apenas agrega estatísticas de divergência (identify_repair_candidates).
O loop de reparo automático via LLM NÃO está implementado nesta fase.

Para implementar o reparo automático no futuro:
  1. Integrar litellm (ou anthropic SDK) como feito na Phase A3 (src/product_a/phase_a3/translator.py)
  2. Para cada ValidationResult com status="FAILED" e pattern_class != EXTERNAL_REF:
     - Chamar generate_repair_prompt(mismatch, function)
     - Enviar ao LLM e extrair o bloco de código Python corrigido
     - Re-executar via execute_in_sandbox e validar novamente
  3. Registrar repair_attempts no MismatchReport
"""
import sys, os
from pathlib import Path
from typing import List

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(REPO_ROOT / "src"))

from product_a.trustware.pipeline_contracts import (
    ValidationResult, MismatchReport, DomainModule, DomainFunction,
    FormulaRegistryMap, PatternClass
)

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

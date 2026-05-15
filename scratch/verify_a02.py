import sys
import os
from pathlib import Path

# Add the project root to sys.path
root = Path("C:/Projetos/ExcelReverseEngine")
trustware_path = root / "libs" / "trustware"
sys.path.insert(0, str(trustware_path))

try:
    from pipeline_contracts import WorkbookClass, CompileDecision, CompatibilityReport
    print("[CHECK] Schemas já existem e são importáveis.")
    
    r = CompatibilityReport(
        workbook_class=WorkbookClass.SUPPORTED,
        compile_decision=CompileDecision.PROCEED
    )
    print("[CHECK] CompatibilityReport instanciável.")
    
    assert hasattr(r, "escalate_reasons")
    assert hasattr(r, "restricted_items")
    assert hasattr(r, "construct_details")
    print("[CHECK] Todos os campos presentes.")
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

import sys
import os
sys.path.insert(0, 'C:/Projetos/ExcelReverseEngine/libs/trustware')
from pipeline_contracts import WorkbookClass, CompileDecision, CompatibilityReport
import json

try:
    # Validação de integridade dos Enums
    assert WorkbookClass.SUPPORTED.value == 'supported'
    assert WorkbookClass.RESTRICTED.value == 'restricted'
    assert WorkbookClass.UNSUPPORTED.value == 'unsupported'
    assert CompileDecision.PROCEED.value == 'proceed'
    assert CompileDecision.PROCEED_WITH_RESTRICTIONS.value == 'proceed_with_restrictions'
    assert CompileDecision.ESCALATE.value == 'escalate'

    # Validação de instância com serialização
    report = CompatibilityReport(
        workbook_class=WorkbookClass.SUPPORTED,
        compile_decision=CompileDecision.PROCEED,
        escalate_reasons=None,
        restricted_items=None,
        construct_details=[]
    )
    data = json.loads(report.model_dump_json())
    assert data['workbook_class'] == 'supported'
    assert data['compile_decision'] == 'proceed'
    assert data['escalate_reasons'] is None
    print('[GATE A0.2] Schemas Trustware íntegros e validados.')
except Exception as e:
    print(f'[ERROR] {e}')
    sys.exit(1)

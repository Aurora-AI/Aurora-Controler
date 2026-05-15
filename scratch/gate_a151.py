import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path("C:/Projetos/ExcelReverseEngine")
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from pipeline_contracts import (
    NormalizedWorkbookIR, NormalizedSheet, NormalizedCell,
    FormulaToken, FormulaTokenType
)
# Validar instanciação
cell = NormalizedCell(
    coordinate='A1',
    formula_raw='=SOMA(B1:B10)',
    formula_tokens=[
        FormulaToken(type=FormulaTokenType.FUNCTION, value='SOMA', position=1),
        FormulaToken(type=FormulaTokenType.LPAREN, value='(', position=5),
        FormulaToken(type=FormulaTokenType.OPERAND, value='B1:B10', position=6),
        FormulaToken(type=FormulaTokenType.RPAREN, value=')', position=12),
    ],
    dependencies=['B1','B2','B3','B4','B5','B6','B7','B8','B9','B10'],
    data_type='e',
    locale_original='pt-BR'
)
ir = NormalizedWorkbookIR(
    file_path='test.xlsx',
    sheets=[NormalizedSheet(name='Sheet1', index=0, state='visible', cells=[cell])],
    normalization_info={'locale': 'pt-BR', 'functions_translated': ['SOMA->SUM']}
)
json_str = ir.model_dump_json()
assert 'SOMA' in json_str
print('[GATE A1.5.1] Schemas de normalização válidos.')

import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path("C:/Projetos/ExcelReverseEngine")
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from normalizer import normalize_workbook
from pipeline_contracts import WorkbookIR, SheetData, SheetInfo, CellData

raw = WorkbookIR(
    file_path='test.xlsx',
    sheets=[
        SheetData(
            info=SheetInfo(name='Sheet1', index=0, state='visible'),
            cells=[
                CellData(coordinate='A1', value=10, formula=None, data_type='n'),
                CellData(coordinate='A2', value=20, formula=None, data_type='n'),
                CellData(coordinate='A3', value=None, formula='=SUM(A1:A2)', data_type='n')
            ]
        )
    ]
)

norm = normalize_workbook(raw)
assert norm.file_path == 'test.xlsx'
assert len(norm.sheets) == 1
sheet = norm.sheets[0]
assert len(sheet.cells) == 3

a3 = next(c for c in sheet.cells if c.coordinate == 'A3')
assert a3.formula_raw == '=SUM(A1:A2)'
assert 'A1' in a3.dependencies
assert 'A2' in a3.dependencies
assert len(a3.formula_tokens) > 0

print('[GATE A1.5.5] Orquestrador de normalização funcional.')

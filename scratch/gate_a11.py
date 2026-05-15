import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))
from pipeline_contracts import WorkbookIR, SheetData, SheetInfo, NamedRangeInfo, CellData

# Validar instanciação
ir = WorkbookIR(
    file_path='teste.xlsx',
    sheets=[
        SheetData(
            info=SheetInfo(name='Sheet1', index=0, state='visible'),
            cells=[CellData(coordinate='A1', value='Hello', formula=None, data_type='s')]
        )
    ],
    named_ranges=[NamedRangeInfo(name='Total', refers_to='=Sheet1!A1:A10')],
    metadata={'creator': 'Test'}
)
json_str = ir.model_dump_json()
assert 'Sheet1' in json_str
assert 'Total' in json_str
print('[GATE A1.1] Schemas WorkbookIR válidos e prontos para extração.')

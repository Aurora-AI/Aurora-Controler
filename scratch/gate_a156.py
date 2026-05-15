import sys, json
from pathlib import Path

# Setup paths
REPO_ROOT = Path("C:/Projetos/ExcelReverseEngine")
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from normalizer import normalize_workbook
from pipeline_contracts import WorkbookIR, SheetData, SheetInfo, CellData, NamedRangeInfo

# Simulação de IR bruto complexo
raw = WorkbookIR(
    file_path='projeto_industrial.xlsx',
    sheets=[
        SheetData(
            info=SheetInfo(name='Data', index=0, state='visible'),
            cells=[
                CellData(coordinate='A1', value='Receita', formula=None, data_type='s'),
                CellData(coordinate='B1', value=5000.50, formula=None, data_type='n'),
                CellData(coordinate='A2', value='Imposto', formula=None, data_type='s'),
                CellData(coordinate='B2', value=None, formula='=B1*0.15', data_type='n')
            ]
        ),
        SheetData(
            info=SheetInfo(name='Calculo', index=1, state='hidden'),
            cells=[
                CellData(coordinate='A1', value=None, formula='=Data!B1-Data!B2', data_type='n')
            ]
        )
    ],
    named_ranges=[
        NamedRangeInfo(name='TAX_RATE', refers_to='=0.15', scope=None)
    ]
)

# Executar normalização
norm = normalize_workbook(raw)

# DEBUG
data_sheet = next(s for s in norm.sheets if s.name == 'Data')
b2_data = next(c for c in data_sheet.cells if c.coordinate == 'B2')
print(f"Tokens for B2: {[ (t.value, t.type) for t in b2_data.formula_tokens ]}")

# Verificações de Integração
assert norm.normalization_info['locale'] in ['en-US', 'pt-BR']
assert len(norm.sheets) == 2

calc_sheet = next(s for s in norm.sheets if s.name == 'Calculo')
a1_calc = next(c for c in calc_sheet.cells if c.coordinate == 'A1')
assert 'Data!B1' in a1_calc.dependencies
assert 'Data!B2' in a1_calc.dependencies

assert any(t.value == 'B1' and t.type == 'operand' for t in b2_data.formula_tokens)
assert any(t.value == '*' and t.type == 'operator' for t in b2_data.formula_tokens)

print('[GATE A1.5.6] Integração completa A1.5 concluída com sucesso.')

import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path("C:/Projetos/ExcelReverseEngine")
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from normalizer import detect_locale, tokenize_formula, translate_function_name
from pipeline_contracts import FormulaTokenType

# Teste de detecção de locale
class DummyCell:
    def __init__(self, formula):
        self.formula = formula
class DummySheet:
    def __init__(self, cells):
        self.cells = cells
class DummyIR:
    def __init__(self, sheets):
        self.sheets = sheets

ir_pt = DummyIR([DummySheet([DummyCell('=SOMA(A1:A10)'), DummyCell('=SE(B1>0;"SIM";"NÃO")')])])
ir_en = DummyIR([DummySheet([DummyCell('=SUM(A1:A10)'), DummyCell('=IF(B1>0,"YES","NO")')])])

assert detect_locale(ir_pt) == 'pt-BR'
assert detect_locale(ir_en) == 'en-US'

# Teste de tokenização
tokens = tokenize_formula('=SUM(A1:A10)', 'en-US')
assert len(tokens) >= 3
assert tokens[0].type == FormulaTokenType.FUNCTION
assert tokens[0].value == 'SUM'

# Teste de tradução
assert translate_function_name('SOMA', 'pt-BR') == 'SUM'
assert translate_function_name('SE', 'pt-BR') == 'IF'

print('[GATE A1.5.2] Tokenizador e tradução de locale funcionais.')

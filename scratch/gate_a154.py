import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path("C:/Projetos/ExcelReverseEngine")
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from normalizer import expand_range, extract_dependencies, FormulaToken, FormulaTokenType

# Teste expansão A1:B2
res = expand_range('A1:B2')
assert sorted(res) == ['A1', 'A2', 'B1', 'B2']

# Teste OOM A:A (limitado a 2000 por default no expand_range se max_row é None)
res_full = expand_range('A:A', max_row=10)
assert len(res_full) == 10
assert res_full[0] == 'A1'
assert res_full[-1] == 'A10'

# Teste dependências
tokens = [
    FormulaToken(type=FormulaTokenType.FUNCTION, value='SUM', position=1),
    FormulaToken(type=FormulaTokenType.OPERAND, value='A1:A2', position=5)
]
deps = extract_dependencies(tokens, 'Sheet1')
assert deps == ['A1', 'A2']

# Teste cross-sheet
tokens_ws = [
    FormulaToken(type=FormulaTokenType.OPERAND, value='Sheet2!B5', position=1)
]
deps_ws = extract_dependencies(tokens_ws, 'Sheet1')
assert deps_ws == ['Sheet2!B5']

print('[GATE A1.5.4] Resolução de referências e expansão de ranges funcional.')

import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path("C:/Projetos/ExcelReverseEngine")
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from normalizer import normalize_value, is_null_value

# Teste numérico
assert normalize_value(100, 'n') == 100
assert normalize_value('1.234,56', 'n', 'pt-BR') == 1234.56
assert normalize_value('1234.56', 'n', 'en-US') == 1234.56

# Teste booleano
assert normalize_value('TRUE', 'b') == True
assert normalize_value(True, 'b') == True

# Teste null
assert is_null_value(None, 's') == True
assert is_null_value('', 's') == True
assert is_null_value('#REF!', 'e') == False

print('[GATE A1.5.3] Normalização de tipos e null semantics funcional.')

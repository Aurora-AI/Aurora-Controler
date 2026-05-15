import sys
import os
from pathlib import Path

# Add the src/phase_a0 to sys.path
sys.path.insert(0, 'C:/Projetos/ExcelReverseEngine/src/phase_a0')
from classifier import classify_formula, VOLATILE_FUNCTIONS

try:
    # Teste de classificação de fórmulas
    assert classify_formula(None) == 'SUPPORTED'
    assert classify_formula('=SUM(A1:A10)') == 'SUPPORTED'
    assert classify_formula('=VLOOKUP(B1, C1:D10, 2, FALSE)') == 'SUPPORTED'
    assert classify_formula('=NOW()') == 'RESTRICTED'
    assert classify_formula('=SUM(OFFSET(A1, 1, 1, 10, 1))') == 'RESTRICTED'
    assert classify_formula('=1+RAND()') == 'RESTRICTED'
    assert classify_formula('=INDIRECT("Sheet2!A1")') == 'RESTRICTED'

    # Verificar que VOLATILE_FUNCTIONS contém as funções obrigatórias
    assert 'NOW' in VOLATILE_FUNCTIONS
    assert 'OFFSET' in VOLATILE_FUNCTIONS
    assert 'INDIRECT' in VOLATILE_FUNCTIONS
    assert 'RAND' in VOLATILE_FUNCTIONS

    print('[GATE A0.3] Classifier importado e funções auxiliares validadas.')
except Exception as e:
    print(f'[ERROR] {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

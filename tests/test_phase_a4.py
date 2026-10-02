import sys, json, os
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[1]


from product_a.phase_a4.gabarito_extractor import extract_gabarito
from product_a.phase_a4.runner import execute_in_sandbox, validate_workbook
from libs.trustware.pipeline_contracts import (
    ExecutionDAG, DAGNode, DomainModule, DomainFunction,
    FormulaRegistryMap, FormulaPattern, PatternClass,
    NormalizedWorkbookIR, NormalizedSheet, NormalizedCell
)

class TestPhaseA4(unittest.TestCase):
    @unittest.skip("Docker not available")
    def test_execute_in_sandbox(self):
        code = "def test_func(a, b): return a + b"
        res = execute_in_sandbox(code, "test_func", {"a": 10, "b": 32})
        self.assertEqual(res, 42)

    def test_validate_workbook_logic(self):
        # 1. Setup Mock DAG (Topological: A1, B1 -> A2)
        dag = ExecutionDAG(
            nodes=[
                DAGNode(id='Sheet1!A1', sheet='Sheet1', coordinate='A1', formula_raw=None, data_type='n', dependencies=[]),
                DAGNode(id='Sheet1!B1', sheet='Sheet1', coordinate='B1', formula_raw=None, data_type='n', dependencies=[]),
                DAGNode(id='Sheet1!A2', sheet='Sheet1', coordinate='A2', formula_raw='=SUM(A1, B1)', data_type='n', dependencies=['Sheet1!A1', 'Sheet1!B1'])
            ],
            edges=[],
            topological_order=['Sheet1!A1', 'Sheet1!B1', 'Sheet1!A2']
        )
        
        # 2. Setup Mock FMap
        fmap = FormulaRegistryMap(
            file_path='test.xlsx',
            patterns=[
                FormulaPattern(node_id='Sheet1!A2', formula_raw='=SUM(A1, B1)', pattern_class=PatternClass.AGGREGATION, matched_rule='sum', confidence=1.0)
            ],
            registry_used=[]
        )
        
        # 3. Setup Mock Normalized IR
        norm = NormalizedWorkbookIR(
            file_path='test.xlsx',
            sheets=[NormalizedSheet(
                name='Sheet1', index=0, state='visible',
                cells=[
                    NormalizedCell(coordinate='A1', formula_raw=None, formula_tokens=[], dependencies=[], value_static=10, data_type='n'),
                    NormalizedCell(coordinate='B1', formula_raw=None, formula_tokens=[], dependencies=[], value_static=5, data_type='n'),
                    NormalizedCell(coordinate='A2', formula_raw='=SUM(A1, B1)', formula_tokens=[], dependencies=['A1', 'B1'], data_type='n')
                ]
            )]
        )
        
        # 4. Setup Mock Domain
        domain = DomainModule(file_path='test_domain.py', functions=[])
        
        # 5. Setup Mock Gabarito (10 + 5 = 15)
        gabarito = {'Sheet1!A1': 10, 'Sheet1!B1': 5, 'Sheet1!A2': 15}
        missing_cache = set()
        
        results = validate_workbook(dag, domain, fmap, norm, gabarito, missing_cache)
        
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].passed, f"Failed: {results[0].error_message}")
        self.assertEqual(results[0].node_id, 'Sheet1!A2')
        self.assertEqual(results[0].actual_value, 15)

    def test_skipped_no_cache(self):
        dag = ExecutionDAG(
            nodes=[DAGNode(id='S!A1', sheet='S', coordinate='A1', formula_raw='=1', data_type='n', dependencies=[])], 
            edges=[],
            topological_order=['S!A1']
        )
        fmap = FormulaRegistryMap(
            file_path='f', 
            patterns=[FormulaPattern(node_id='S!A1', formula_raw='=1', pattern_class=PatternClass.ARITHMETIC)],
            registry_used=[]
        )
        norm = NormalizedWorkbookIR(
            file_path='f', 
            sheets=[NormalizedSheet(name='S', index=0, state='v', cells=[NormalizedCell(coordinate='A1', formula_raw='=1', data_type='n')])]
        )
        domain = DomainModule(file_path='d', functions=[])
        gabarito = {}
        missing_cache = {'S!A1'}
        
        results = validate_workbook(dag, domain, fmap, norm, gabarito, missing_cache)
        self.assertEqual(results[0].status, "SKIPPED_NO_CACHE")
        self.assertFalse(results[0].passed)

    def test_duplicate_reference_in_sum(self):
        """Valida que referências duplicadas (ex: SUM(A1, A1)) não são de-duplicadas."""
        dag = ExecutionDAG(
            nodes=[
                DAGNode(id='S!A1', sheet='S', coordinate='A1', formula_raw=None, dependencies=[]),
                DAGNode(id='S!A2', sheet='S', coordinate='A2', formula_raw='=SUM(A1, A1)', dependencies=['S!A1', 'S!A1'])
            ],
            edges=[],
            topological_order=['S!A1', 'S!A2']
        )
        fmap = FormulaRegistryMap(
            file_path='f', 
            patterns=[FormulaPattern(node_id='S!A2', formula_raw='=SUM(A1,A1)', pattern_class=PatternClass.AGGREGATION, matched_rule='sum')],
            registry_used=[]
        )
        norm = NormalizedWorkbookIR(
            file_path='f', 
            sheets=[NormalizedSheet(name='S', index=0, state='v', cells=[
                NormalizedCell(coordinate='A1', value_static=10, data_type='n'),
                NormalizedCell(coordinate='A2', formula_raw='=SUM(A1, A1)', data_type='n')
            ])]
        )
        # O resultado esperado de SUM(10, 10) é 20, não 10.
        gabarito = {'S!A1': 10, 'S!A2': 20}
        results = validate_workbook(dag, DomainModule(file_path='d', functions=[]), fmap, norm, gabarito, set())
        
        self.assertTrue(results[0].passed)
        self.assertEqual(results[0].actual_value, 20)

    def test_safe_arithmetic_executor(self):
        """Valida o executor de aritmética real."""
        dag = ExecutionDAG(
            nodes=[
                DAGNode(id='S!A1', sheet='S', coordinate='A1', formula_raw=None, dependencies=[]),
                DAGNode(id='S!B1', sheet='S', coordinate='B1', formula_raw='=A1*2+5', dependencies=['S!A1'])
            ],
            edges=[],
            topological_order=['S!A1', 'S!B1']
        )
        fmap = FormulaRegistryMap(
            file_path='f', 
            patterns=[FormulaPattern(node_id='S!B1', formula_raw='=A1*2+5', pattern_class=PatternClass.ARITHMETIC)],
            registry_used=[]
        )
        norm = NormalizedWorkbookIR(
            file_path='f', 
            sheets=[NormalizedSheet(name='S', index=0, state='v', cells=[
                NormalizedCell(coordinate='A1', value_static=10, data_type='n'),
                NormalizedCell(coordinate='B1', formula_raw='=A1*2+5', data_type='n')
            ])]
        )
        # 10 * 2 + 5 = 25
        gabarito = {'S!A1': 10, 'S!B1': 25}
        results = validate_workbook(dag, DomainModule(file_path='d', functions=[]), fmap, norm, gabarito, set())
        
        self.assertTrue(results[0].passed)
        self.assertEqual(results[0].actual_value, 25)

    @unittest.skip("Docker not available")
    def test_signature_handshake(self):
        """Valida que parâmetros posicionais funcionam mesmo se o nome for diferente no DomainModule."""
        code = "def translated_logic(val_a, val_b): return val_a * val_b"
        inputs = {"Sheet1!A1": 10, "Sheet1!B1": 5}
        # O sandbox deve mapear A1 -> val_a e B1 -> val_b por ordem se os nomes não baterem
        res = execute_in_sandbox(code, "translated_logic", inputs)
        self.assertEqual(res, 50)

if __name__ == "__main__":
    unittest.main()

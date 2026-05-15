import sys, json, os
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a3"))

from translator import extract_unresolved, build_prompt, translate_formula, translate_workbook
from pipeline_contracts import (
    FormulaRegistryMap, FormulaPattern, PatternClass,
    NormalizedWorkbookIR, NormalizedSheet, NormalizedCell,
    FormulaToken, FormulaTokenType, SemanticTranslationRequest
)

class TestPhaseA3(unittest.TestCase):
    def setUp(self):
        # Simular um registry map com 1 unresolved e 1 resolved
        self.fmap = FormulaRegistryMap(
            file_path='test.xlsx',
            patterns=[
                FormulaPattern(
                    node_id='Sheet1!A1',
                    formula_raw='=10+20',
                    pattern_class=PatternClass.ARITHMETIC,
                    matched_rule='simple',
                    confidence=1.0,
                    logic_density_index=0.5
                ),
                FormulaPattern(
                    node_id='Sheet1!B1',
                    formula_raw='=COMPLEX_FUNC(A1)',
                    pattern_class=PatternClass.UNRESOLVED,
                    confidence=0.0,
                    logic_density_index=0.8
                )
            ],
            registry_used=[],
            unresolved_count=1
        )

        # Simular normalized IR
        self.norm = NormalizedWorkbookIR(
            file_path='test.xlsx',
            sheets=[NormalizedSheet(
                name='Sheet1', index=0, state='visible',
                cells=[
                    NormalizedCell(
                        coordinate='A1', formula_raw='=10+20',
                        formula_tokens=[FormulaToken(type=FormulaTokenType.CONSTANT, value='10', position=1)],
                        dependencies=[], data_type='n'
                    ),
                    NormalizedCell(
                        coordinate='B1', formula_raw='=COMPLEX_FUNC(A1)',
                        formula_tokens=[FormulaToken(type=FormulaTokenType.FUNCTION, value='COMPLEX_FUNC', position=1)],
                        dependencies=['A1'], data_type='e'
                    )
                ]
            )],
            named_ranges=[],
            metadata={},
            normalization_info={}
        )

    def test_extract_unresolved(self):
        reqs = extract_unresolved(self.fmap, self.norm)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].node_id, 'Sheet1!B1')
        self.assertIn('COMPLEX_FUNC', reqs[0].formula_raw)

    def test_build_prompt_with_context(self):
        reqs = extract_unresolved(self.fmap, self.norm)
        # Manually create a resolved context for dependency A1 (Sheet1!A1 in fmap)
        # Note: In real use, get_resolved_context does this.
        resolved_context = [
            {
                "node_id": "Sheet1!A1",
                "pattern_class": "ARITHMETIC",
                "matched_rule": "simple",
                "template": "a + b"
            }
        ]
        prompt = build_prompt(reqs[0], resolved_context)
        self.assertIn("RESOLVED DEPENDENCIES", prompt)
        self.assertIn("Sheet1!A1", prompt)
        self.assertIn("ARITHMETIC", prompt)

    @patch('litellm.completion')
    def test_translate_formula_mock(self, mock_completion):
        # Mock LLM output
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "function_name": "complex_business_logic",
            "python_code": "def complex_business_logic(a1):\n    return a1 * 2",
            "input_params": ["a1"],
            "output_type": "float",
            "docstring": "Calculates complex logic.",
            "business_intent": "Double the value for tax reasons.",
            "confidence": 0.9
        })
        mock_completion.return_value = mock_response
        
        reqs = extract_unresolved(self.fmap, self.norm)
        result = translate_formula(reqs[0], self.fmap)
        
        self.assertEqual(result.function_name, "complex_business_logic")
        self.assertEqual(result.confidence, 0.9)
        self.assertIn("def complex_business_logic", result.python_code)

    @patch('translator.translate_formula')
    def test_translate_workbook(self, mock_translate):
        from pipeline_contracts import SemanticTranslationResult
        mock_translate.return_value = SemanticTranslationResult(
            node_id='Sheet1!B1',
            function_name='complex_func',
            python_code='def complex_func(a1): return a1',
            input_params=['a1'],
            output_type='Any',
            docstring='desc',
            business_intent='intent',
            confidence=1.0
        )
        
        domain = translate_workbook(self.norm, self.fmap)
        self.assertEqual(len(domain.functions), 1)
        self.assertEqual(domain.functions[0].name, 'complex_func')
        self.assertIn('from typing import Any', domain.imports[0])

if __name__ == "__main__":
    unittest.main()

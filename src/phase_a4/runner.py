"""
EXRS Phase A4 — DAG Runner & Sandbox
Executa o código traduzido e as regras determinísticas respeitando a ordem topológica.
"""
import sys, math, statistics, ast, operator, inspect
from pathlib import Path
from typing import Any, Callable

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a4"))

from pipeline_contracts import (
    ExecutionDAG, DomainModule, ValidationResult, PatternClass,
    FormulaRegistryMap, NormalizedWorkbookIR
)
from formula_evaluator import evaluate_formula, ExcelError
from normalizer import expand_range

# Implementações determinísticas padrão (A2.5)
DETERMINISTIC_EXECUTORS: dict[str, Callable] = {
    "sum": lambda values: sum(v for v in values if isinstance(v, (int, float))),
    "average": lambda values: statistics.mean(v for v in values if isinstance(v, (int, float))) if any(isinstance(v, (int, float)) for v in values) else 0,
    "count": lambda values: len([v for v in values if v is not None]),
    "min": lambda values: min(v for v in values if isinstance(v, (int, float))) if any(isinstance(v, (int, float)) for v in values) else 0,
    "max": lambda values: max(v for v in values if isinstance(v, (int, float))) if any(isinstance(v, (int, float)) for v in values) else 0,
    "if_simple": lambda condition, t_val, f_val: t_val if condition else f_val,
    "inline_arithmetic": None, # será resolvido via eval seguro ou sandbox
}

class SafeArithmeticEvaluator(ast.NodeVisitor):
    """Avaliador AST seguro para expressões aritméticas simples."""
    def __init__(self, variables: dict):
        self.variables = variables
        self.operators = {
            ast.Add: operator.add, ast.Sub: operator.sub,
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.USub: operator.neg, ast.UAdd: operator.pos
        }

    def evaluate(self, node):
        if isinstance(node, ast.Expression):
            return self.evaluate(node.body)
        elif isinstance(node, ast.BinOp):
            left = self.evaluate(node.left)
            right = self.evaluate(node.right)
            op_type = type(node.op)
            if op_type not in self.operators:
                raise TypeError(f"Operador não suportado: {op_type.__name__}")
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                raise TypeError(
                    f"Operação aritmética requer números, obtido: "
                    f"{type(left).__name__} e {type(right).__name__}"
                )
            return self.operators[op_type](left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self.evaluate(node.operand)
            if not isinstance(operand, (int, float)):
                raise TypeError(f"Operação unária requer número, obtido: {type(operand).__name__}")
            return self.operators[type(node.op)](operand)
        elif isinstance(node, (ast.Num, ast.Constant)):
            return node.n if isinstance(node, ast.Num) else node.value
        elif isinstance(node, ast.Name):
            if node.id in self.variables:
                return self.variables[node.id]
            raise ValueError(f"Variable '{node.id}' not found in state_memory.")
        else:
            raise TypeError(f"Unsupported AST node: {type(node).__name__}")

def execute_in_sandbox(func_code: str, func_name: str, inputs: dict) -> Any:
    """Executa função traduzida (A3) com Signature Handshake."""
    sandbox_globals = {
        "__builtins__": __builtins__,
        "math": math, "statistics": statistics, "Any": Any,
    }
    try:
        exec(func_code, sandbox_globals)
        func = sandbox_globals.get(func_name)
        if not callable(func):
            raise ValueError(f"'{func_name}' is not a callable function.")
        
        # --- Signature Handshake ---
        sig = inspect.signature(func)
        expected_params = list(sig.parameters.keys())
        final_args = {}
        input_values_list = list(inputs.values())
        
        for i, param_name in enumerate(expected_params):
            if param_name in inputs:
                final_args[param_name] = inputs[param_name]
            elif i < len(input_values_list):
                final_args[param_name] = input_values_list[i]
        
        return func(**final_args)
    except Exception as e:
        return f"RUNTIME_ERROR: {str(e)}"

def validate_workbook(
    dag: ExecutionDAG,
    domain: DomainModule,
    fmap: FormulaRegistryMap,
    norm_ir: NormalizedWorkbookIR,
    gabarito: dict,
    missing_cache: set
) -> list[ValidationResult]:
    """
    Valida o workbook completo seguindo a ordem topológica do DAG.
    """
    state_memory: dict[str, Any] = {}
    results: list[ValidationResult] = []
    
    # 1. Carregar valores estáticos (inputs)
    for sheet in norm_ir.sheets:
        for cell in sheet.cells:
            node_id = f"{sheet.name}!{cell.coordinate}"
            if not cell.formula_raw:
                state_memory[node_id] = cell.value_static
    
    # Mapas de busca rápida
    functions_map = {f.source_nodes[0]: f for f in domain.functions if f.source_nodes}
    patterns_map = {p.node_id: p for p in fmap.patterns}
    
        # 2. Executar em ordem topológica
    for nid in dag.topological_order:
        # Se já é um valor estático, pula (já carregado)
        if nid in state_memory:
            continue
            
        pattern = patterns_map.get(nid)
        if not pattern:
            continue
            
        # Obter inputs das dependências (usando state_memory)
        deps_ids = []
        # Encontrar o nó no DAG
        dag_node = next((n for n in dag.nodes if n.id == nid), None)
        if dag_node:
            deps_ids = dag_node.dependencies
            
        # Usar sentinel para deps ausentes vs deps que falharam (None)
        _MISSING = object()
        inputs_values = {dep: (state_memory[dep] if dep in state_memory else 0) for dep in deps_ids}
        inputs_list = [(state_memory[dep] if dep in state_memory else 0) for dep in deps_ids]
        
        actual_value = None
        status = "PENDING"
        error_msg = None
        
        try:
            # Fórmulas com referência externa → não avaliáveis, retornar placeholder
            if pattern.pattern_class == PatternClass.EXTERNAL_REF:
                state_memory[nid] = '#EXT!'
                results.append(ValidationResult(
                    node_id=nid,
                    expected_value=gabarito.get(nid),
                    actual_value='#EXT!',
                    passed=False,
                    status="SKIPPED_EXTERNAL_REF",
                    error_message="Referência externa ([workbook]) não avaliável sem acesso ao arquivo fonte.",
                ))
                continue

            # Fórmulas UNRESOLVED traduzidas via LLM → sandbox Python
            if pattern.pattern_class == PatternClass.UNRESOLVED:
                func_meta = functions_map.get(nid)
                if func_meta:
                    actual_value = execute_in_sandbox(func_meta.code, func_meta.name, inputs_values)
                else:
                    actual_value = "ERROR: Missing translated function"

            else:
                # Avaliador unificado para ARITHMETIC, CONDITIONAL, AGGREGATION, etc.
                current_sheet = nid.split('!')[0] if '!' in nid else ''
                actual_value = evaluate_formula(
                    pattern.formula_raw,
                    state_memory,
                    current_sheet,
                    expand_range,
                )

            state_memory[nid] = actual_value
            
            # 3. Comparação com Gabarito
            expected_value = gabarito.get(nid)
            
            if nid in missing_cache:
                status = "SKIPPED_NO_CACHE"
                passed = False
                error_msg = "Gabarito não disponível (cache vazio)."
            elif expected_value is None and nid not in gabarito:
                status = "ERROR"
                passed = False
                error_msg = "Nó ausente no gabarito."
            else:
                # Comparação numérica com tolerância
                if isinstance(actual_value, (int, float)) and isinstance(expected_value, (int, float)):
                    passed = math.isclose(actual_value, expected_value, rel_tol=1e-7)
                else:
                    passed = str(actual_value) == str(expected_value)
                
                status = "PASSED" if passed else "FAILED"
                if not passed:
                    error_msg = f"Divergência: esperado {expected_value}, obtido {actual_value}"
            
            results.append(ValidationResult(
                node_id=nid,
                expected_value=expected_value,
                actual_value=actual_value,
                passed=passed,
                status=status,
                error_message=error_msg
            ))
            
        except Exception as e:
            # Gravar ExcelError no state_memory — propagação limpa via operadores.
            # Nós dependentes receberão o ExcelError e propaga via __add__/__mul__ etc.,
            # produzindo o mesmo código de erro em vez de None silencioso ou string duplicada.
            error_code = f'#ERROR! ({type(e).__name__})'
            error_sentinel = ExcelError(error_code)
            state_memory[nid] = error_sentinel
            results.append(ValidationResult(
                node_id=nid,
                expected_value=gabarito.get(nid),
                actual_value=error_code,
                passed=False,
                status="ERROR",
                error_message=str(e)
            ))
            
    return results

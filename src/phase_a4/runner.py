"""
EXRS Phase A4 — DAG Runner & Sandbox
Executa o código traduzido e as regras determinísticas respeitando a ordem topológica.
"""
import sys, os, math, statistics, ast, operator, inspect, subprocess, tempfile, json, shutil, uuid
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

SANDBOX_IMAGE = "python:3.14-slim"

# Script ESTÁTICO executado dentro do container. NÃO contém código do usuário:
# o código traduzido (A3), a assinatura e os inputs chegam por stdin (JSON), evitando
# injeção via repr e mantendo o user-code como dado, não como fonte do runner.
_SANDBOX_RUNNER = r'''
import json, sys, math, statistics

_WHITELIST = {
    "abs": abs, "min": min, "max": max, "sum": sum, "round": round,
    "len": len, "bool": bool, "int": int, "float": float, "str": str,
    "list": list, "dict": dict, "tuple": tuple, "set": set,
    "any": any, "all": all, "range": range, "enumerate": enumerate,
}

def _main():
    payload = json.loads(sys.stdin.read())
    func_code = payload["code"]
    func_name = payload["func_name"]
    inputs = payload["inputs"]
    params = payload["params"]

    g = {"__builtins__": _WHITELIST, "math": math, "statistics": statistics}
    exec(func_code, g)
    func = g.get(func_name)
    if not callable(func):
        raise ValueError(func_name + " is not callable")

    final_args = {}
    values = list(inputs.values())
    for i, name in enumerate(params):
        if name in inputs:
            final_args[name] = inputs[name]
        elif i < len(values):
            final_args[name] = values[i]
    return func(**final_args)

try:
    print(json.dumps({"status": "ok", "result": _main()}))
except Exception as e:
    print(json.dumps({"status": "error", "error": type(e).__name__ + ": " + str(e)}))
'''


def _docker_available() -> bool:
    """Verifica fisicamente se o engine Docker responde (sem assumir)."""
    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True, text=True, timeout=10,
        )
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        return False


def _extract_params(func_code: str, func_name: str) -> list[str]:
    """Extrai a ordem dos parâmetros estaticamente via ast no host (sem inspect no sandbox)."""
    tree = ast.parse(func_code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return [a.arg for a in node.args.args]
    return []


def _sanitize(value: Any) -> Any:
    """Torna os inputs serializáveis: ExcelError → string; nan/inf → None; recursivo."""
    if isinstance(value, ExcelError):
        return str(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return value


def execute_in_sandbox(func_code: str, func_name: str, inputs: dict, timeout_sec: int = 30) -> Any:
    """
    Executa a função traduzida (A3) em um CONTAINER Docker efêmero e sem privilégios.

    O isolamento real vem das flags do container (--network none, --read-only, --user
    nobody, limites de recurso), não da whitelist de builtins — esta é apenas
    defesa-em-profundidade. Mesmo que o código gerado escape do exec restrito (ex.: via
    travessia de subclasses), não há FS de host montado gravável, rede, nem privilégios.
    """
    if not _docker_available():
        # Falha explícita — NUNCA cair para exec local (reintroduziria o vetor de RCE).
        return "RUNTIME_ERROR: SANDBOX_UNAVAILABLE: docker engine não acessível (FACTORY_TOOL_UNAVAILABLE)"

    params = _extract_params(func_code, func_name)
    payload = json.dumps({
        "code": func_code,
        "func_name": func_name,
        "inputs": _sanitize(inputs),
        "params": params,
    })

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(_SANDBOX_RUNNER)
        temp_path = f.name
    # NamedTemporaryFile nasce 0600 (só dono). O container roda como nobody (uid 65534) e
    # precisa LER o script montado — no Linux as permissões são aplicadas (no Windows não).
    os.chmod(temp_path, 0o644)

    container_name = f"exrs_sbx_{uuid.uuid4().hex[:12]}"
    cmd = [
        "docker", "run", "--rm", "-i",
        "--name", container_name,
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:size=16m",
        "--memory", "256m", "--cpus", "1",
        "--pids-limit", "64",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        "-v", f"{temp_path}:/sandbox/run.py:ro",
        SANDBOX_IMAGE, "python", "/sandbox/run.py",
    ]

    try:
        proc = subprocess.run(
            cmd, input=payload, capture_output=True, text=True, timeout=timeout_sec
        )
        if proc.returncode != 0:
            return f"RUNTIME_ERROR: Sandbox container failed - {proc.stderr.strip() or proc.stdout.strip()}"
        try:
            out_data = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return f"RUNTIME_ERROR: Invalid output from sandbox - {proc.stdout}"
        if out_data.get("status") == "ok":
            return out_data.get("result")
        return f"RUNTIME_ERROR: {out_data.get('error')}"
    except subprocess.TimeoutExpired:
        # O cliente docker foi morto, mas o container pode persistir — remover à força.
        subprocess.run(["docker", "rm", "-f", container_name],
                       capture_output=True, text=True)
        return f"RUNTIME_ERROR: TimeoutError: Execution exceeded {timeout_sec} seconds"
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass

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

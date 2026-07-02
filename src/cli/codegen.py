"""
EXRS CLI — Codegen do módulo Python 'replay'.

Gera um .py standalone que reproduz o grafo de cálculo de uma planilha sem depender de
Excel nem de LLM: usa o MESMO motor (evaluate_formula + expand_range) que a Fase A4 já usa
para validar o workbook (src/phase_a4/runner.py::validate_workbook), só que emitido como
código-fonte estático em vez de executado inline. Fórmulas EXTERNAL_REF e UNRESOLVED são
excluídas (não avaliáveis deterministicamente — mesma regra do validador).
"""
from pipeline_contracts import (
    ExecutionDAG, FormulaRegistryMap, NormalizedWorkbookIR, PatternClass,
)

_EXCLUDED = {PatternClass.EXTERNAL_REF, PatternClass.UNRESOLVED}


def render_replay_module(
    dag: ExecutionDAG,
    fmap: FormulaRegistryMap,
    norm_ir: NormalizedWorkbookIR,
    source_file: str,
) -> str:
    """Retorna o texto-fonte Python completo do módulo replay."""
    # Um formula cell só entra em FORMULAS se tiver um FormulaPattern correspondente
    # em fmap.patterns E essa entrada não estiver em _EXCLUDED. pattern_registry.py
    # pode pular a classificação inteiramente (cell sem formula_tokens) — nesse caso
    # não há entrada em fmap.patterns, e a célula deve ser tratada como não avaliável
    # deterministicamente (mesma cautela aplicada a EXTERNAL_REF/UNRESOLVED).
    included_formula_nodes = {
        p.node_id for p in fmap.patterns if p.pattern_class not in _EXCLUDED
    }

    static_values: dict[str, object] = {}
    formulas: dict[str, str] = {}
    sheet_of: dict[str, str] = {}

    excluded_formula_nodes: set[str] = set()

    for sheet in norm_ir.sheets:
        for cell in sheet.cells:
            node_id = f"{sheet.name}!{cell.coordinate}"
            sheet_of[node_id] = sheet.name
            if cell.formula_raw:
                if node_id in included_formula_nodes:
                    formulas[node_id] = cell.formula_raw
                else:
                    excluded_formula_nodes.add(node_id)
            else:
                static_values[node_id] = cell.value_static

    topo_order = [nid for nid in dag.topological_order if nid not in excluded_formula_nodes]

    lines = [
        '"""',
        f"Módulo gerado automaticamente pelo EXRS — reproduz {source_file} sem Excel.",
        "Motor de fórmulas vendorizado em _exrs_formula_engine.py / _exrs_range_utils.py",
        "(cópia exata dos módulos já validados pela Fase A4 do EXRS).",
        '"""',
        "from _exrs_formula_engine import evaluate_formula",
        "from _exrs_range_utils import expand_range",
        "",
        f"STATIC_VALUES = {static_values!r}",
        "",
        f"FORMULAS = {formulas!r}",
        "",
        f"SHEET_OF = {sheet_of!r}",
        "",
        f"TOPOLOGICAL_ORDER = {topo_order!r}",
        "",
        "",
        "def compute(overrides: dict | None = None) -> dict:",
        '    """Recalcula todas as células na ordem topológica. `overrides` permite',
        '    substituir valores de entrada, ex: compute({"Sheet1!A1": 42})."""',
        "    state = dict(STATIC_VALUES)",
        "    if overrides:",
        "        state.update(overrides)",
        "    for node_id in TOPOLOGICAL_ORDER:",
        "        if node_id in state:",
        "            continue",
        "        formula = FORMULAS.get(node_id)",
        "        if formula is None:",
        "            continue",
        "        state[node_id] = evaluate_formula(formula, state, SHEET_OF[node_id], expand_range)",
        "    return state",
        "",
        "",
        'if __name__ == "__main__":',
        "    for _node_id, _value in compute().items():",
        "        print(f\"{_node_id} = {_value!r}\")",
        "",
    ]
    return "\n".join(lines)

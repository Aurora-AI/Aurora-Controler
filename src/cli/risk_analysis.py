"""
EXRS CLI — Detectores de risco do diagnóstico DAG (`exrs diagnose`).

Cada detector é uma função pura sobre os artefatos já produzidos por A0→A2.5 (nenhum
parser de fórmula novo — reaproveita a classificação da Fase A2.5 e a tokenização da
Fase A1.5). `RiskFinding` é local a este módulo, não um contrato compartilhado com o SaaS.
"""
from pydantic import BaseModel

from product_a.trustware.pipeline_contracts import (
    ExecutionDAG, FormulaRegistryMap, FormulaTokenType, NormalizedWorkbookIR, PatternClass,
)


class RiskFinding(BaseModel):
    """Um risco individual detectado na planilha."""
    node_id: str
    category: str  # "external_ref" | "unresolved" | "orphan_cell" | "hardcoded_value"
    description: str


def find_external_refs(fmap: FormulaRegistryMap) -> list[RiskFinding]:
    """Referências a outros arquivos (`[Outro.xlsx]`) — dependência externa frágil."""
    return [
        RiskFinding(
            node_id=p.node_id, category="external_ref",
            description=f"Referência externa a outro arquivo: {p.formula_raw}",
        )
        for p in fmap.patterns if p.pattern_class == PatternClass.EXTERNAL_REF
    ]


def find_unresolved(fmap: FormulaRegistryMap) -> list[RiskFinding]:
    """Fórmulas que o classificador determinístico não conseguiu entender."""
    return [
        RiskFinding(
            node_id=p.node_id, category="unresolved",
            description=f"Fórmula não classificada (lógica de caixa-preta): {p.formula_raw}",
        )
        for p in fmap.patterns if p.pattern_class == PatternClass.UNRESOLVED
    ]


def find_orphan_cells(dag: ExecutionDAG) -> list[RiskFinding]:
    """Células com fórmula mas sem nenhuma aresta (nem entrada nem saída) no DAG —
    possível célula morta ou hardcoding disfarçado de fórmula."""
    touched = {e.source for e in dag.edges} | {e.target for e in dag.edges}
    return [
        RiskFinding(
            node_id=n.id, category="orphan_cell",
            description="Célula com fórmula isolada do grafo — não depende de nada nem é usada por outra fórmula.",
        )
        for n in dag.nodes if n.formula_raw and n.id not in touched
    ]


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def find_hardcoded_values(norm_ir: NormalizedWorkbookIR) -> list[RiskFinding]:
    """Valores numéricos fixados diretamente dentro de fórmulas (ex: `=A1*1.15`), em vez
    de referenciar uma célula de parâmetro — reaproveita a tokenização já feita na Fase A1.5."""
    findings: list[RiskFinding] = []
    for sheet in norm_ir.sheets:
        for cell in sheet.cells:
            for token in cell.formula_tokens:
                if token.type == FormulaTokenType.CONSTANT and _is_numeric(token.value):
                    findings.append(RiskFinding(
                        node_id=f"{sheet.name}!{cell.coordinate}", category="hardcoded_value",
                        description=f"Valor numérico fixo embutido na fórmula: {token.value}",
                    ))
                    break  # 1 achado por célula, não 1 por token
    return findings


def analyze_risks(
    dag: ExecutionDAG, fmap: FormulaRegistryMap, norm_ir: NormalizedWorkbookIR,
) -> list[RiskFinding]:
    """Agrega os 4 detectores."""
    return (
        find_external_refs(fmap)
        + find_unresolved(fmap)
        + find_orphan_cells(dag)
        + find_hardcoded_values(norm_ir)
    )

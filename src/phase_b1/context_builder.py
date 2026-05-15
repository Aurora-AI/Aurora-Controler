"""
EXRS Phase B1 — Context Builder

Lê os outputs do pipeline A0–A4 e constrói um resumo compacto do workbook
para uso como contexto do LLM no chat de captura de intenção.
"""
import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


def identify_input_nodes(dag: dict) -> list[dict]:
    """
    Retorna nós folha (leaf nodes): células sem dependências.
    São candidatos naturais a parâmetros de entrada para simulação.
    """
    return [n for n in dag["nodes"] if not n.get("dependencies")]


def identify_output_nodes(dag: dict) -> list[dict]:
    """
    Retorna nós raiz (root nodes): células com fórmula que não são
    dependência de nenhum outro nó. São candidatos a métricas de saída.
    """
    all_deps: set[str] = set()
    for node in dag["nodes"]:
        all_deps.update(node.get("dependencies", []))
    return [
        n for n in dag["nodes"]
        if n.get("formula_raw") and n["id"] not in all_deps
    ]


def _get_cell_value(norm_ir: dict, node_id: str) -> object:
    """Busca o valor estático de uma célula no normalized IR."""
    parts = node_id.split("!")
    if len(parts) != 2:
        return None
    sheet_name, coord = parts
    for sheet in norm_ir.get("sheets", []):
        if sheet["name"] == sheet_name:
            for cell in sheet.get("cells", []):
                if cell["coordinate"] == coord:
                    return cell.get("value_static")
    return None


def build_workbook_summary(dag: dict, norm_ir: dict, workbook_name: str) -> dict:
    """
    Constrói um dicionário resumo do workbook para o LLM.

    Args:
        dag: dict deserializado do arquivo _a2_dag.json
        norm_ir: dict deserializado do arquivo _a15_norm.json
        workbook_name: nome do workbook (ex: "Pasta1")

    Returns:
        dict com: workbook_name, sheets, input_candidates, output_candidates
    """
    sheets = [s["name"] for s in norm_ir.get("sheets", [])]

    input_nodes = identify_input_nodes(dag)
    output_nodes = identify_output_nodes(dag)

    input_candidates = [
        {
            "node_id": n["id"],
            "current_value": _get_cell_value(norm_ir, n["id"]),
        }
        for n in input_nodes[:20]
    ]

    output_candidates = [
        {
            "node_id": n["id"],
            "formula": n.get("formula_raw", ""),
        }
        for n in output_nodes[:10]
    ]

    return {
        "workbook_name": workbook_name,
        "sheets": sheets,
        "input_candidates": input_candidates,
        "output_candidates": output_candidates,
    }


def load_summary_from_prefix(output_prefix: str) -> dict:
    """
    Carrega os arquivos _a2_dag.json e _a15_norm.json a partir de um prefixo
    (ex: "output/Pasta1") e retorna o summary dict.
    """
    prefix = Path(output_prefix)
    workbook_name = prefix.name

    dag_path = Path(f"{output_prefix}_a2_dag.json")
    norm_path = Path(f"{output_prefix}_a15_norm.json")

    if not dag_path.exists():
        raise FileNotFoundError(f"DAG não encontrado: {dag_path}")
    if not norm_path.exists():
        raise FileNotFoundError(f"Normalized IR não encontrado: {norm_path}")

    with open(dag_path, encoding="utf-8") as f:
        dag = json.load(f)
    with open(norm_path, encoding="utf-8") as f:
        norm_ir = json.load(f)

    return build_workbook_summary(dag, norm_ir, workbook_name)

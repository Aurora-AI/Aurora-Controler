"""Fase C0 — Detecção de estrutura e un-pivot para o modelo canônico longo."""
from __future__ import annotations

from typing import Any

from dashboard_contracts import DetectedStructure

# Valores que indicam linha de total geral (case-insensitive)
_GRAND_TOTAL_TOKENS = ("total geral", "grand total")


def _parse_number(text: str) -> float:
    """Converte string numérica em float. Heurística: o último separador
    (`.` ou `,`) é o decimal; o anterior é separador de milhar.

    Aceita pt-BR (1.234,56) e en-US (1,234.56).
    """
    s = text.strip()
    if not s:
        raise ValueError("string vazia")
    last_dot = s.rfind(".")
    last_comma = s.rfind(",")
    if last_dot == -1 and last_comma == -1:
        return float(s)
    if last_comma > last_dot:
        # vírgula é o decimal (pt-BR): remove pontos, vírgula vira ponto
        s = s.replace(".", "").replace(",", ".")
    else:
        # ponto é o decimal (en-US): remove vírgulas
        s = s.replace(",", "")
    return float(s)


def _is_number(value: Any) -> bool:
    """True se o valor é numérico (aceita locale pt-BR e en-US)."""
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            _parse_number(value)
            return True
        except ValueError:
            return False
    return False


def _to_number(value: Any) -> float:
    """Converte célula numérica em float (aceita locale pt-BR e en-US)."""
    if isinstance(value, (int, float)):
        return float(value)
    return _parse_number(str(value))


def classify_columns(
    header: list[str], data_rows: list[list[Any]]
) -> tuple[list[int], list[int]]:
    """Retorna (índices de colunas-dimensão, índices de colunas-measure).

    Uma coluna é measure se todos os seus valores não-vazios são numéricos.
    """
    dim_idx: list[int] = []
    measure_idx: list[int] = []
    for col in range(len(header)):
        values = [
            r[col] for r in data_rows
            if col < len(r) and r[col] not in (None, "")
        ]
        if values and all(_is_number(v) for v in values):
            measure_idx.append(col)
        else:
            dim_idx.append(col)
    return dim_idx, measure_idx


def detect_structure(
    header: list[str], data_rows: list[list[Any]]
) -> DetectedStructure:
    """Detecta se a tabela é `flat` (já longa) ou `wide` (precisa un-pivot)."""
    _, measure_idx = classify_columns(header, data_rows)
    if len(measure_idx) >= 2:
        return DetectedStructure(
            table_kind="wide",
            unpivot_source_columns=[header[i] for i in measure_idx],
            canonical_dimension_from_columns="status",
            canonical_measure="quantidade",
        )
    return DetectedStructure(table_kind="flat")


def unpivot_wide(
    header: list[str],
    data_rows: list[list[Any]],
    dim_idx: list[int],
    measure_idx: list[int],
) -> list[dict[str, Any]]:
    """Un-pivot: cada coluna-measure vira um valor da dimensão `status`.

    1 linha larga com N colunas-measure -> N linhas longas.
    """
    long_rows: list[dict[str, Any]] = []
    for row in data_rows:
        base = {header[i]: row[i] for i in dim_idx if i < len(row)}
        for mi in measure_idx:
            if mi >= len(row) or row[mi] in (None, ""):
                continue
            entry = dict(base)
            entry["status"] = header[mi]
            entry["quantidade"] = _to_number(row[mi])
            long_rows.append(entry)
    return long_rows

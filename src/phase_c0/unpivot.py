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


def _col_letter(idx: int) -> str:
    """Converte índice 0-based em letra de coluna estilo Excel (0->A, 1->B)."""
    letters = ""
    n = idx
    while True:
        letters = chr(ord("A") + n % 26) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return letters


def _is_grand_total(row: list[Any]) -> bool:
    """True se a linha é um total geral (primeira célula com token conhecido)."""
    if not row or row[0] in (None, ""):
        return False
    return any(tok in str(row[0]).strip().lower() for tok in _GRAND_TOTAL_TOKENS)


def _is_empty(row: list[Any]) -> bool:
    """True se todas as células da linha estão vazias."""
    return all(c in (None, "") for c in row)


def build_c0_dataset(path: str):
    """Lê o arquivo, detecta estrutura, un-pivota se preciso e monta o C0Dataset."""
    from ingest import read_table
    from dashboard_contracts import (
        C0Dataset, IngestionStrategy, SourceMapEntry,
        DiscardedRow, ValidationSummary,
    )

    sheet, raw_rows = read_table(path)
    if not raw_rows:
        raise ValueError(f"Arquivo vazio: {path}")

    header = [str(c) if c is not None else "" for c in raw_rows[0]]
    body = raw_rows[1:]
    total_rows_read = len(body)

    # Classificar linhas do corpo
    discarded: list[DiscardedRow] = []
    kept: list[tuple[int, list[Any]]] = []  # (origin_row_1based, row)
    for offset, row in enumerate(body):
        origin_row = offset + 2  # +1 header, +1 base-1
        if _is_empty(row):
            discarded.append(DiscardedRow(origin_row=origin_row, reason="empty", raw=list(row)))
        elif _is_grand_total(row):
            discarded.append(DiscardedRow(origin_row=origin_row, reason="grand_total", raw=list(row)))
        else:
            kept.append((origin_row, row))

    kept_rows = [r for _, r in kept]
    structure = detect_structure(header, kept_rows)
    dim_idx, measure_idx = classify_columns(header, kept_rows)

    # Emitir dataset longo
    dataset: list[dict[str, Any]] = []
    source_map: list[SourceMapEntry] = []
    row_id = 0

    if structure.table_kind == "wide":
        used, reason = "grid_scraping", "pivot-like wide table detected"
        for origin_row, row in kept:
            base = {header[i]: row[i] for i in dim_idx if i < len(row)}
            for mi in measure_idx:
                if mi >= len(row) or row[mi] in (None, ""):
                    continue
                row_id += 1
                entry = {"row_id": row_id, **base,
                         "status": header[mi], "quantidade": _to_number(row[mi])}
                dataset.append(entry)
                cells = {header[i]: f"{_col_letter(i)}{origin_row}"
                         for i in dim_idx if i < len(row)}
                cells["status"] = f"{_col_letter(mi)}1"
                cells["quantidade"] = f"{_col_letter(mi)}{origin_row}"
                source_map.append(SourceMapEntry(row_id=row_id, origin_sheet=sheet,
                                                 origin_cells=cells))
    else:
        used, reason = "structured_model", "clean flat table"
        for origin_row, row in kept:
            row_id += 1
            entry: dict[str, Any] = {"row_id": row_id}
            cells: dict[str, str] = {}
            for i, name in enumerate(header):
                if i >= len(row):
                    continue
                val = row[i]
                entry[name] = _to_number(val) if (i in measure_idx and _is_number(val)) else val
                cells[name] = f"{_col_letter(i)}{origin_row}"
            dataset.append(entry)
            source_map.append(SourceMapEntry(row_id=row_id, origin_sheet=sheet,
                                             origin_cells=cells))

    validation = ValidationSummary(
        total_rows_read=total_rows_read,
        source_rows_emitted=len(kept),
        source_rows_context=0,
        source_rows_discarded=len(discarded),
        dataset_rows_emitted=len(dataset),
    )

    return C0Dataset(
        source_file=path,
        ingestion_strategy=IngestionStrategy(
            primary="structured_model", fallback="grid_scraping",
            used=used, reason=reason),
        detected_structure=structure,
        dataset=dataset,
        source_map=source_map,
        discarded_rows=discarded,
        validation_summary=validation,
    )

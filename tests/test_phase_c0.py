"""Testes da Fase C0 — Ingestão + Un-pivot."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c0",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import (
    IngestionStrategy, DetectedStructure, SourceMapEntry,
    DiscardedRow, ValidationSummary, C0Dataset,
)


def test_ingestion_strategy_model():
    s = IngestionStrategy(primary="structured_model", fallback="grid_scraping",
                          used="grid_scraping", reason="pivot detected")
    assert s.used == "grid_scraping"


def test_validation_summary_closure_fields():
    v = ValidationSummary(total_rows_read=200, source_rows_emitted=120,
                          source_rows_context=25, source_rows_discarded=55,
                          dataset_rows_emitted=580)
    assert v.source_rows_emitted + v.source_rows_context + v.source_rows_discarded == v.total_rows_read
    assert v.warnings == []


def test_c0_dataset_roundtrip():
    ds = C0Dataset(
        source_file="Propostas.xlsx",
        ingestion_strategy=IngestionStrategy(primary="structured_model",
            fallback="grid_scraping", used="structured_model", reason="clean table"),
        detected_structure=DetectedStructure(table_kind="flat"),
        dataset=[{"row_id": 1, "cnpj": "X", "status": "Aprovado", "quantidade": 10}],
        source_map=[SourceMapEntry(row_id=1, origin_sheet="Plan1",
            origin_cells={"cnpj": "A2", "quantidade": "B2"})],
        discarded_rows=[DiscardedRow(origin_row=9, reason="grand_total", raw=["Total", 99])],
        validation_summary=ValidationSummary(total_rows_read=10, source_rows_emitted=8,
            source_rows_context=1, source_rows_discarded=1, dataset_rows_emitted=8),
    )
    assert ds.schema_version == "c0_dataset.v1"
    data = ds.model_dump()
    assert C0Dataset.model_validate(data).schema_version == "c0_dataset.v1"


# --- Task 5: ingest ---
import csv as _csv
from ingest import read_table


def test_read_table_csv(tmp_path):
    p = tmp_path / "dados.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
    sheet, rows = read_table(str(p))
    assert sheet == "dados"
    assert rows[0] == ["cnpj", "status", "quantidade"]
    assert rows[1] == ["X1", "Aprovado", "10"]


def test_read_table_rejects_unknown_format(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("nada", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        read_table(str(p))


# --- Task 6: detecção + un-pivot wide ---
from unpivot import _is_number, classify_columns, detect_structure, unpivot_wide


def test_is_number_handles_locale():
    assert _is_number("1.234") is True
    assert _is_number("12,5") is True
    assert _is_number("Aprovado") is False
    assert _is_number(None) is False


def test_classify_columns_separates_dim_and_measure():
    header = ["cnpj", "Aprovado", "Reprovado"]
    data = [["X1", "10", "20"], ["X2", "5", "7"]]
    dim_idx, measure_idx = classify_columns(header, data)
    assert dim_idx == [0]
    assert measure_idx == [1, 2]


def test_detect_structure_wide():
    header = ["cnpj", "Aprovado", "Reprovado"]
    data = [["X1", "10", "20"]]
    s = detect_structure(header, data)
    assert s.table_kind == "wide"
    assert s.unpivot_source_columns == ["Aprovado", "Reprovado"]
    assert s.canonical_dimension_from_columns == "status"
    assert s.canonical_measure == "quantidade"


def test_detect_structure_flat():
    header = ["cnpj", "status", "quantidade"]
    data = [["X1", "Aprovado", "10"]]
    s = detect_structure(header, data)
    assert s.table_kind == "flat"


def test_unpivot_wide_emits_long_rows():
    header = ["cnpj", "Aprovado", "Reprovado"]
    data = [["X1", "10", "20"]]
    long_rows = unpivot_wide(header, data, [0], [1, 2])
    assert {"cnpj": "X1", "status": "Aprovado", "quantidade": 10.0} in long_rows
    assert {"cnpj": "X1", "status": "Reprovado", "quantidade": 20.0} in long_rows


def test_to_number_en_us_decimal():
    from unpivot import _to_number
    assert _to_number("12.5") == 12.5          # ponto decimal en-US
    assert _to_number("1,234.56") == 1234.56   # milhar en-US


def test_to_number_pt_br_decimal():
    from unpivot import _to_number
    assert _to_number("12,5") == 12.5          # vírgula decimal pt-BR
    assert _to_number("1.234,56") == 1234.56   # milhar pt-BR


def test_unpivot_wide_skips_empty_and_ragged():
    from unpivot import unpivot_wide
    header = ["cnpj", "Aprovado", "Reprovado"]
    data = [["X1", "10", ""], ["X2"]]  # célula vazia + linha ragged
    long_rows = unpivot_wide(header, data, [0], [1, 2])
    # X1: só Aprovado (Reprovado vazio); X2: nada (ragged, sem measures)
    assert len(long_rows) == 1
    assert long_rows[0] == {"cnpj": "X1", "status": "Aprovado", "quantidade": 10.0}


# --- Task 7: build_c0_dataset ---
from unpivot import build_c0_dataset


def test_build_c0_dataset_flat_csv(tmp_path):
    p = tmp_path / "flat.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
        w.writerow(["X2", "Reprovado", "20"])
    ds = build_c0_dataset(str(p))
    assert ds.ingestion_strategy.used == "structured_model"
    assert ds.detected_structure.table_kind == "flat"
    assert len(ds.dataset) == 2
    vs = ds.validation_summary
    assert vs.source_rows_emitted + vs.source_rows_context + vs.source_rows_discarded == vs.total_rows_read


def test_build_c0_dataset_wide_unpivot(tmp_path):
    p = tmp_path / "wide.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "Aprovado", "Reprovado"])
        w.writerow(["X1", "10", "20"])
    ds = build_c0_dataset(str(p))
    assert ds.ingestion_strategy.used == "grid_scraping"
    assert ds.detected_structure.table_kind == "wide"
    assert len(ds.dataset) == 2  # 1 linha larga -> 2 longas
    assert ds.validation_summary.dataset_rows_emitted == 2


def test_build_c0_dataset_discards_grand_total(tmp_path):
    p = tmp_path / "gt.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
        w.writerow(["Total Geral", "", "10"])
    ds = build_c0_dataset(str(p))
    assert len(ds.dataset) == 1
    assert any(d.reason == "grand_total" for d in ds.discarded_rows)


def test_build_c0_dataset_source_map_covers_dataset(tmp_path):
    p = tmp_path / "sm.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
    ds = build_c0_dataset(str(p))
    mapped_ids = {e.row_id for e in ds.source_map}
    dataset_ids = {r["row_id"] for r in ds.dataset}
    assert dataset_ids.issubset(mapped_ids)

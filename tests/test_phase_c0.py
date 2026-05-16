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

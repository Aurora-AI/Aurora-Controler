"""Testes da Fase C1 — Modelo Semântico."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c1",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import SemanticField, SemanticModel


def test_semantic_field_model():
    f = SemanticField(name="cnpj", type="string", semantic_role="entity_id",
                      business_role="merchant_document", cardinality=47)
    assert f.semantic_role == "entity_id"
    assert f.business_role == "merchant_document"


def test_semantic_field_optional_business_role():
    f = SemanticField(name="perfil", type="category", semantic_role="breakdown_dimension")
    assert f.business_role is None


def test_semantic_model_roundtrip():
    m = SemanticModel(
        primary_dimension="cnpj", secondary_dimension="perfil",
        fields=[SemanticField(name="quantidade", type="integer", semantic_role="measure")],
    )
    assert m.schema_version == "c1_semantic.v1"
    assert SemanticModel.model_validate(m.model_dump()).primary_dimension == "cnpj"


# --- Task 9: semantic ---
from dashboard_contracts import C0Dataset, IngestionStrategy, DetectedStructure, ValidationSummary
from semantic import infer_type, infer_semantic_role, build_semantic_model


def _c0_fixture() -> C0Dataset:
    return C0Dataset(
        source_file="t.csv",
        ingestion_strategy=IngestionStrategy(primary="structured_model",
            fallback="grid_scraping", used="structured_model", reason="flat"),
        detected_structure=DetectedStructure(table_kind="flat"),
        dataset=[
            {"row_id": 1, "cnpj": "00.1/0001-01", "status": "Aprovado", "quantidade": 10.0},
            {"row_id": 2, "cnpj": "00.2/0001-02", "status": "Reprovado", "quantidade": 20.0},
        ],
        source_map=[], discarded_rows=[],
        validation_summary=ValidationSummary(total_rows_read=2, source_rows_emitted=2,
            source_rows_context=0, source_rows_discarded=0, dataset_rows_emitted=2),
    )


def test_infer_type_integer_and_category():
    assert infer_type([10.0, 20.0, 30.0]) == "integer"
    assert infer_type(["Aprovado", "Reprovado", "Aprovado"]) == "category"


def test_infer_semantic_role_measure_and_entity():
    assert infer_semantic_role("quantidade", "integer", None) == "measure"
    assert infer_semantic_role("cnpj", "string", 47) == "entity_id"
    # ID puramente numérico deve ser entity_id, não measure
    assert infer_semantic_role("id", "integer", 47) == "entity_id"
    # 'quantidade' contém a substring 'id' mas NÃO deve casar (matching por token)
    assert infer_semantic_role("quantidade", "integer", None) == "measure"


def test_build_semantic_model_assigns_roles():
    model = build_semantic_model(_c0_fixture())
    assert model.schema_version == "c1_semantic.v1"
    roles = {f.name: f.semantic_role for f in model.fields}
    assert roles["cnpj"] == "entity_id"
    assert roles["status"] == "breakdown_dimension"
    assert roles["quantidade"] == "measure"
    assert any(f.semantic_role == "measure" for f in model.fields)


def test_build_semantic_model_picks_primary_dimension():
    model = build_semantic_model(_c0_fixture())
    # cnpj e status têm cardinalidade 2; empate resolvido por ordem estável -> cnpj
    assert model.primary_dimension == "cnpj"
    assert model.secondary_dimension == "status"


# --- Task 10: __main__ ---
import json as _json
import subprocess as _sub
import os as _os


def test_phase_c1_cli_writes_artifact(tmp_path):
    c0 = tmp_path / "T_c0_dataset.json"
    c0.write_text(_c0_fixture().model_dump_json(indent=2), encoding="utf-8")
    result = _sub.run(
        [sys.executable, "-m", "phase_c1", str(tmp_path / "T")],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**_os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    out = tmp_path / "T_c1_semantic.json"
    assert out.exists()
    assert _json.loads(out.read_text(encoding="utf-8"))["schema_version"] == "c1_semantic.v1"

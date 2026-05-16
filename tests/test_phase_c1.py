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

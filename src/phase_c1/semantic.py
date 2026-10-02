"""Fase C1 — Inferência determinística de papéis semânticos."""
from __future__ import annotations

import re
from typing import Any, Optional

from libs.trustware.dashboard_contracts import C0Dataset, SemanticField, SemanticModel

_ENTITY_HINTS = ("cnpj", "cpf", "id", "codigo", "documento")
_TEMPORAL_HINTS = ("data", "date", "mes", "ano", "periodo")
_BUSINESS_ROLE_MAP = {
    "cnpj": "merchant_document",
    "cpf": "person_document",
    "status": "proposal_status",
    "quantidade": "record_count",
}


def _is_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        s = value.strip().replace(".", "").replace(",", ".")
        try:
            float(s)
            return True
        except ValueError:
            return False
    return False


def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).strip().replace(".", "").replace(",", "."))


def infer_type(values: list[Any]) -> str:
    """Infere o tipo de uma coluna: integer | float | category | string."""
    non_empty = [v for v in values if v not in (None, "")]
    if not non_empty:
        return "string"
    if all(_is_number(v) for v in non_empty):
        nums = [_as_float(v) for v in non_empty]
        return "integer" if all(n.is_integer() for n in nums) else "float"
    distinct = len({str(v) for v in non_empty})
    if distinct <= 20:
        return "category"
    return "string"


def _name_tokens(name: str) -> set[str]:
    """Quebra o nome do campo em tokens minúsculos (separadores: espaço _ . / -)."""
    return {t for t in re.split(r"[\s_./\-]+", name.lower().strip()) if t}


def infer_semantic_role(name: str, col_type: str, cardinality: Optional[int]) -> str:
    """Atribui semantic_role de forma determinística.

    Ordem: entity_id (por token de nome) vence measure — um ID numérico não
    deve ser somado como métrica. O matching é por token (não substring), para
    que nomes como 'quantidade' não casem com o hint 'id'.
    `cardinality` é reservado para uso futuro.
    """
    tokens = _name_tokens(name)
    if tokens & set(_ENTITY_HINTS):
        return "entity_id"
    if col_type in ("integer", "float"):
        return "measure"
    if tokens & set(_TEMPORAL_HINTS):
        return "temporal"
    if col_type == "category":
        return "breakdown_dimension"
    return "label"


def _business_role(name: str) -> Optional[str]:
    lname = name.lower()
    for key, role in _BUSINESS_ROLE_MAP.items():
        if key in lname:
            return role
    return None


def build_semantic_model(c0: C0Dataset) -> SemanticModel:
    """Constrói o SemanticModel a partir do C0Dataset."""
    dataset = c0.dataset
    field_names = [k for k in dataset[0].keys() if k != "row_id"] if dataset else []

    fields: list[SemanticField] = []
    for name in field_names:
        values = [r.get(name) for r in dataset]
        col_type = infer_type(values)
        non_empty = [v for v in values if v not in (None, "")]
        cardinality = len({str(v) for v in non_empty})
        role = infer_semantic_role(name, col_type, cardinality)
        fields.append(SemanticField(
            name=name, type=col_type, semantic_role=role,
            business_role=_business_role(name),
            cardinality=None if role == "measure" else cardinality,
        ))

    dims = [f for f in fields if f.semantic_role in ("entity_id", "breakdown_dimension")]
    dims_sorted = sorted(dims, key=lambda f: f.cardinality or 0, reverse=True)
    primary = dims_sorted[0].name if dims_sorted else None
    secondary = dims_sorted[1].name if len(dims_sorted) > 1 else None

    return SemanticModel(
        primary_dimension=primary, secondary_dimension=secondary, fields=fields,
    )

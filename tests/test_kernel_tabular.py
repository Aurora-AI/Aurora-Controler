"""
Testes de src/kernel/tabular.py — vista tabular genérica (mapeamento de coluna +
coerção de tipo + guarda de dataset vazio), domínio-agnóstica.

Deliberadamente usa vocabulário e schema que NÃO são de varejo (widget/tag/qty em vez
de produto/cliente/loja) — o ponto do kernel é servir qualquer domínio tabular, e
testar só com vocabulário de vendas não provaria isso. A cobertura de comportamento
específico de Vendas (defaults, papéis pt-BR) mora em tests/test_column_mapper.py,
que testa o wrapper de domínio do Produto B.
"""
import pandas as pd
import pytest

from kernel.tabular import (
    ColumnMappingError, DateAmbiguityError, coerce_currency_series, coerce_date_series,
    infer_column_roles, records_to_frame, typed_empty_frame,
)

_ROLE_KEYWORDS = {"id": ["widget_id", "codigo"], "tag": ["etiqueta", "tag"]}
_REQUIRED_ROLES = ("id", "tag")


# ── infer_column_roles — mecanismo genérico, sem vocabulário embutido ──────────────

def test_infer_column_roles_requires_vocabulary_explicitly():
    """Sem role_keywords/required_roles, o kernel não tem vocabulário próprio pra
    inferir nada — precisa falhar alto (TypeError), não devolver {} em silêncio."""
    df = pd.DataFrame(columns=["x"])
    with pytest.raises(TypeError):
        infer_column_roles(df)


def test_infer_column_roles_matches_via_provided_vocabulary():
    df = pd.DataFrame(columns=["Widget_ID", "Etiqueta Principal"])
    roles = infer_column_roles(df, role_keywords=_ROLE_KEYWORDS, required_roles=_REQUIRED_ROLES)
    assert roles == {"id": "Widget_ID", "tag": "Etiqueta Principal"}


def test_infer_column_roles_override_takes_priority_over_heuristic():
    df = pd.DataFrame(columns=["Widget_ID", "Etiqueta Principal", "Outra Coluna"])
    roles = infer_column_roles(
        df, role_keywords=_ROLE_KEYWORDS, required_roles=_REQUIRED_ROLES,
        override={"tag": "Outra Coluna"},
    )
    assert roles["tag"] == "Outra Coluna"
    assert roles["id"] == "Widget_ID"


def test_infer_column_roles_fails_loud_when_required_role_missing():
    df = pd.DataFrame(columns=["Widget_ID"])  # falta "tag"
    with pytest.raises(ColumnMappingError):
        infer_column_roles(df, role_keywords=_ROLE_KEYWORDS, required_roles=_REQUIRED_ROLES)


def test_infer_column_roles_two_vocabularies_never_collide():
    """Dois domínios diferentes usando o mesmo mecanismo, no mesmo DataFrame, com
    vocabulários próprios — nenhum vaza pro outro."""
    df = pd.DataFrame(columns=["codigo_produto", "categoria_produto"])
    other_roles = {"category": ["categoria"]}
    roles = infer_column_roles(
        df, role_keywords=other_roles, required_roles=("category",),
    )
    assert roles == {"category": "categoria_produto"}


# ── coerção de moeda/data — já cobertas em profundidade via o wrapper de domínio em
# tests/test_column_mapper.py; aqui só confirma que o kernel exporta o mesmo
# comportamento diretamente, sem depender do wrapper ────────────────────────────────

def test_coerce_currency_series_still_works_called_directly_on_kernel():
    coerced = coerce_currency_series(pd.Series(["R$ 1.500,00", "480.0"]))
    assert coerced.tolist() == pytest.approx([1500.00, 480.0])


def test_coerce_date_series_raises_ambiguity_error_called_directly_on_kernel():
    series = pd.Series(["31/01/2024", "01/13/2024"])  # dia>12 nas duas posições, colunas diferentes
    with pytest.raises(DateAmbiguityError):
        coerce_date_series(series)


# ── guarda de dataset vazio — mecanismo genérico parametrizado por schema ──────────

def test_typed_empty_frame_has_zero_rows_with_correct_dtypes():
    schema = {"count": "int64", "label": "object", "amount": "float64"}
    df = typed_empty_frame(schema)
    assert len(df) == 0
    assert list(df.columns) == ["count", "label", "amount"]
    assert df["count"].dtype == "int64"
    assert df["amount"].dtype == "float64"


def test_records_to_frame_empty_list_returns_typed_empty_frame_not_columnless():
    """Sem isso, pd.DataFrame([]) não teria NENHUMA coluna, e qualquer código a
    jusante que acesse df['campo'] quebraria com KeyError antes de qualquer guarda
    de 'sem dado' ter chance de agir."""
    schema = {"count": "int64", "label": "object"}
    df = records_to_frame([], schema)
    assert len(df) == 0
    assert list(df.columns) == ["count", "label"]


def test_records_to_frame_non_empty_builds_from_dicts():
    schema = {"count": "int64", "label": "object"}
    df = records_to_frame([{"count": 1, "label": "a"}, {"count": 2, "label": "b"}], schema)
    assert len(df) == 2
    assert df["count"].tolist() == [1, 2]
    assert df["label"].tolist() == ["a", "b"]

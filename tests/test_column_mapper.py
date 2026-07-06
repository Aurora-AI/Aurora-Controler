"""
Testes de src/oracle/column_mapper.py — inferência de colunas + coerção de localização.

FASE RED (TDD): estes testes devem FALHAR agora (ModuleNotFoundError). Cobrem
especificamente as 2 regras endurecidas exigidas pelo CSO: coerção agressiva de moeda/data
pt-BR, e falha-alto em ambiguidade genuína de formato de data (nunca mistura em silêncio).
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from oracle.column_mapper import (
    ColumnMappingError, DateAmbiguityError, coerce_currency_series,
    coerce_date_series, infer_column_roles,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures"


# ── Inferência de papéis (vocabulário pt-BR) ────────────────────────────────────────

def test_infer_column_roles_finds_all_four_minimum_roles():
    df = pd.DataFrame(columns=["Data Emissão", "Produto/Serviço", "Cliente", "Valor Líquido", "Qtd"])
    roles = infer_column_roles(df)
    assert roles["date"] == "Data Emissão"
    assert roles["product"] == "Produto/Serviço"
    assert roles["customer"] == "Cliente"
    assert roles["value"] == "Valor Líquido"
    assert roles["quantity"] == "Qtd"


def test_infer_column_roles_fails_loud_when_customer_role_missing():
    """Sem os 4 papéis mínimos, deve levantar erro claro — nunca adivinhar em silêncio."""
    df = pd.DataFrame(columns=["Data", "Item", "Preço"])  # sem coluna de cliente
    with pytest.raises(ColumnMappingError):
        infer_column_roles(df)


def test_infer_column_roles_accepts_manual_override():
    df = pd.DataFrame(columns=["col1", "col2", "col3", "col4"])
    override = {"date": "col1", "product": "col2", "customer": "col3", "value": "col4"}
    roles = infer_column_roles(df, override=override)
    assert roles == {**roles, **override}


# ── Coerção de moeda (regra endurecida: nunca deixar string sobreviver ao Pydantic) ─

def test_coerce_currency_handles_dirty_brl_format():
    series = pd.Series(["R$ 1.500,00", "R$ 900,50", "R$ 10.000,00"])
    coerced = coerce_currency_series(series)
    assert coerced.tolist() == pytest.approx([1500.00, 900.50, 10000.00])
    assert pd.api.types.is_numeric_dtype(coerced)


def test_coerce_currency_handles_plain_numeric_input():
    series = pd.Series([1500.0, 900.5])
    coerced = coerce_currency_series(series)
    assert coerced.tolist() == pytest.approx([1500.0, 900.5])


def test_coerce_currency_unparseable_value_becomes_nan_not_silent_zero():
    """Um valor que sobrevive à coerção mas não parseia deve virar NaN (para ser
    descartado e contado no CleaningSummary) — nunca 0.0 silencioso."""
    series = pd.Series(["R$ 1.500,00", "texto qualquer sem número"])
    coerced = coerce_currency_series(series)
    assert coerced.iloc[0] == pytest.approx(1500.00)
    assert pd.isna(coerced.iloc[1])


# ── Coerção de data + detecção de mistura genuína de formato (regra endurecida) ─────

def test_coerce_date_series_defaults_to_dayfirst_ptbr():
    series = pd.Series(["15/01/2023", "28/03/2024"])
    coerced = coerce_date_series(series)
    assert coerced.iloc[0] == pd.Timestamp(2023, 1, 15)
    assert coerced.iloc[1] == pd.Timestamp(2024, 3, 28)


def test_coerce_date_series_raises_on_genuinely_mixed_formats():
    """mixed_dates_test.csv tem linhas só-válidas-DD/MM (dia>12 na 1a posição) e
    linhas só-válidas-MM/DD (dia>12 na 2a posição) na MESMA coluna — sinal estrutural
    inequívoco de mistura, não apenas ambiguidade. Deve falhar alto, nunca misturar."""
    df = pd.read_csv(FIXTURES / "mixed_dates_test.csv", dtype=str)
    with pytest.raises(DateAmbiguityError):
        coerce_date_series(df["Data"])


def test_coerce_date_series_with_explicit_format_override_bypasses_detection():
    df = pd.read_csv(FIXTURES / "mixed_dates_test.csv", dtype=str)
    # Com override explícito, o usuário assume a responsabilidade pela interpretação.
    coerced = coerce_date_series(df["Data"], date_format="DMY")
    assert len(coerced) == len(df)

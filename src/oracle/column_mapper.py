"""
EXRS Data Oracle — Mapeamento de colunas + coerção agressiva de localização.

Regras endurecidas (CSO): (1) nenhuma string de moeda pode sobreviver até o Pydantic —
coerção agressiva de "R$ 1.500,00" para 1500.0 acontece aqui; (2) mistura GENUÍNA de
formato de data (DD/MM e MM/DD coexistindo na mesma coluna, não apenas ambiguidade
teórica) falha alto — nunca mistura em silêncio.
"""
import re
import unicodedata

import pandas as pd


class ColumnMappingError(Exception):
    """Papéis obrigatórios de coluna não puderam ser identificados."""


class DateAmbiguityError(Exception):
    """Coluna de data contém formatos DD/MM e MM/DD genuinamente misturados."""


_ROLE_KEYWORDS: dict[str, list[str]] = {
    "date": ["data", "emissao", "dt"],
    "product": ["produto", "item", "sku", "descricao", "servico"],
    "customer": ["cliente", "razao", "cnpj"],
    "value": ["valor", "vlr", "total", "liquido", "preco"],
    "quantity": ["qtd", "quant", "quantidade"],
}

_REQUIRED_ROLES = ("date", "product", "customer", "value")


def _normalize(text: str) -> str:
    """Remove acentos e caixa — 'Líquido' -> 'liquido'."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def infer_column_roles(
    df: pd.DataFrame, override: dict[str, str] | None = None,
) -> dict[str, str]:
    """Infere qual coluna corresponde a cada papel (date/product/customer/value/
    quantity) via vocabulário pt-BR de vendas. `override` tem prioridade absoluta sobre
    a heurística. Levanta ColumnMappingError se um dos 4 papéis obrigatórios não for
    identificado."""
    roles: dict[str, str] = {}
    assigned_columns: set[str] = set()

    if override:
        for role, column in override.items():
            roles[role] = column
            assigned_columns.add(column)

    for role, keywords in _ROLE_KEYWORDS.items():
        if role in roles:
            continue
        for column in df.columns:
            if column in assigned_columns:
                continue
            normalized = _normalize(str(column))
            if any(keyword in normalized for keyword in keywords):
                roles[role] = column
                assigned_columns.add(column)
                break

    missing = [r for r in _REQUIRED_ROLES if r not in roles]
    if missing:
        raise ColumnMappingError(
            f"Não foi possível identificar as colunas para os papéis obrigatórios "
            f"{missing}. Colunas encontradas: {list(df.columns)}. Use --mapping para "
            f"especificar manualmente, ex: {{\"date\": \"NomeDaColuna\", ...}}."
        )
    return roles


def _clean_currency_value(value: object) -> float:
    if isinstance(value, bool):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return float("nan")
    text = str(value).strip()
    text = re.sub(r"[R\$€\s]", "", text)
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def coerce_currency_series(series: pd.Series) -> pd.Series:
    """Coerção agressiva de moeda suja pt-BR ('R$ 1.500,00' -> 1500.0). Valor que
    sobrevive à coerção mas não parseia vira NaN — nunca um 0.0 silencioso."""
    coerced = series.apply(_clean_currency_value)
    return pd.Series(coerced, dtype="float64", index=series.index)


_DATE_TOKEN_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def _detect_mixed_date_format(series: pd.Series) -> bool:
    """Detecta mistura ESTRUTURAL de formato: linhas só-válidas-DD/MM (dia>12 na 1a
    posição) e linhas só-válidas-MM/DD (dia>12 na 2a posição) coexistindo na mesma
    coluna — sinal inequívoco de mistura, não mera ambiguidade teórica."""
    forces_dayfirst = False
    forces_monthfirst = False
    for value in series.dropna():
        match = _DATE_TOKEN_RE.match(str(value).strip())
        if not match:
            continue
        first, second = int(match.group(1)), int(match.group(2))
        if first > 12 and second <= 12:
            forces_dayfirst = True
        elif second > 12 and first <= 12:
            forces_monthfirst = True
        if forces_dayfirst and forces_monthfirst:
            return True
    return False


def coerce_date_series(series: pd.Series, date_format: str | None = None) -> pd.Series:
    """Coage uma coluna de data para datetime. Padrão pt-BR (dayfirst=True). Se
    `date_format` não for informado e a coluna contiver mistura genuína de formato,
    levanta DateAmbiguityError — nunca mistura DD/MM e MM/DD em silêncio. Com
    `date_format` explícito ("DMY"|"MDY"), o usuário assume a interpretação e a
    detecção é ignorada."""
    if date_format is None:
        if _detect_mixed_date_format(series):
            raise DateAmbiguityError(
                "Coluna de data contém formatos DD/MM e MM/DD genuinamente "
                "misturados (dia > 12 aparece tanto na 1ª quanto na 2ª posição em "
                "linhas diferentes). Desambigue via --mapping com "
                "{\"date_format\": \"DMY\"|\"MDY\"}."
            )
        dayfirst = True
    else:
        dayfirst = date_format.upper() == "DMY"
    return pd.to_datetime(series, dayfirst=dayfirst, errors="coerce")

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
    "cost": ["custo"],
    "category": ["categoria", "familia", "linha"],
    "store": ["loja", "filial", "unidade"],
    "salesperson": ["vendedor"],
}

_REQUIRED_ROLES = ("date", "product", "customer", "value")

# Vocabulário de mapeamento para as abas da série B (Fix 3) — dict separado do de
# Vendas: mesmas palavras (ex. "sku") significam coisas diferentes em cada aba, e um
# vocabulário compartilhado colidiria (ex. "descricao" é produto em Vendas, mas
# identificação de item em Estoque).
_ESTOQUE_ROLE_KEYWORDS: dict[str, list[str]] = {
    "sku": ["sku", "produto", "item", "codigo"],
    "cost": ["custo"],
    "qty_on_hand": ["qtd_atual", "estoque", "saldo", "quantidade"],
    "last_movement": ["ultimo_mov", "movimentacao"],
    "category": ["categoria", "familia", "linha"],
}
_ESTOQUE_REQUIRED_ROLES = ("sku", "cost", "qty_on_hand", "last_movement")

_CLIENTES_ROLE_KEYWORDS: dict[str, list[str]] = {
    "customer_id": ["cliente_id", "codigo", "id"],
    "phone": ["telefone", "fone", "celular"],
    "document": ["cpf", "cnpj", "documento"],
}
_CLIENTES_REQUIRED_ROLES = ("customer_id",)

# SVC5 — vocabulário da aba Financeiro (receita declarada por loja/mês) — dict
# separado, mesma razão dos anteriores (vocabulário compartilhado colidiria).
_FINANCEIRO_ROLE_KEYWORDS: dict[str, list[str]] = {
    "period": ["mes", "periodo", "competencia"],
    "store": ["loja", "filial", "unidade"],
    "service_revenue": ["receita_servico", "servicos"],
}
_FINANCEIRO_REQUIRED_ROLES = ("period", "store", "service_revenue")


def _normalize(text: str) -> str:
    """Remove acentos e caixa — 'Líquido' -> 'liquido'."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def infer_column_roles(
    df: pd.DataFrame, override: dict[str, str] | None = None,
    role_keywords: dict[str, list[str]] | None = None,
    required_roles: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Infere qual coluna corresponde a cada papel via vocabulário pt-BR. `override`
    tem prioridade absoluta sobre a heurística. Levanta ColumnMappingError se um dos
    papéis obrigatórios não for identificado. `role_keywords`/`required_roles`
    permitem reaproveitar o mesmo mecanismo para esquemas diferentes de Vendas (ex.
    Estoque, Clientes) — default mantém o comportamento original de Vendas."""
    role_keywords = role_keywords if role_keywords is not None else _ROLE_KEYWORDS
    required_roles = required_roles if required_roles is not None else _REQUIRED_ROLES

    roles: dict[str, str] = {}
    assigned_columns: set[str] = set()

    if override:
        for role, column in override.items():
            roles[role] = column
            assigned_columns.add(column)

    for role, keywords in role_keywords.items():
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

    missing = [r for r in required_roles if r not in roles]
    if missing:
        raise ColumnMappingError(
            f"Não foi possível identificar as colunas para os papéis obrigatórios "
            f"{missing}. Colunas encontradas: {list(df.columns)}. Use --mapping para "
            f"especificar manualmente, ex: {{\"date\": \"NomeDaColuna\", ...}}."
        )
    return roles


def _clean_currency_value(value: object) -> float:
    """Coage um valor monetário para float, DETECTANDO o formato em vez de assumir pt-BR.

    Bug histórico (exposto pela fixture de ótica): a versão antiga fazia
    `text.replace(".", "")` sempre, tratando '480.0' (número cru do Excel, formato US/ISO)
    como milhar → 4800, inflando ~10× todo valor decimal. Planilha real mistura número cru
    (ponto decimal) e texto pt-BR ('1.500,00'). A desambiguação abaixo trata os dois."""
    if isinstance(value, bool):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return float("nan")
    text = re.sub(r"[R\$€\s]", "", str(value).strip())

    has_comma = "," in text
    has_dot = "." in text
    if has_comma and has_dot:
        # O ÚLTIMO separador é o decimal: pt-BR '1.500,00' (vírgula por último) vs
        # US '1,500.00' (ponto por último).
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")   # pt-BR
        else:
            text = text.replace(",", "")                     # US
    elif has_comma:
        text = text.replace(",", ".")                        # só vírgula → decimal pt-BR
    elif has_dot:
        # Só ponto → ambíguo. Múltiplos pontos, OU 1 ponto com exatamente 3 dígitos após,
        # = milhar pt-BR ('1.500' → 1500; '1.500.000' → 1500000). Caso contrário (1-2
        # dígitos após, ex: '480.0', '1500.00') = ponto decimal US/ISO, mantém.
        if text.count(".") > 1 or len(text.rsplit(".", 1)[-1]) == 3:
            text = text.replace(".", "")
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
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}")


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
    detecção é ignorada.

    Bug real (exposto por planilha de cliente): células de data do Excel chegam como
    string ISO ("2023-10-06 00:00:00") após a leitura com dtype=str. ISO é inequívoco —
    ano sempre na 1a posição — mas `pd.to_datetime(dayfirst=True)` sem `format="mixed"`
    infere um único formato a partir da 1a linha; se essa linha for ambígua (dia e mês
    ambos <=12), ele troca dia/mês em silêncio e aplica a troca à coluna inteira,
    gerando datas erradas nas linhas que "batem" e NaT em massa nas que não batem. ISO
    é tratado à parte, sem depender de dayfirst.

    2º bug real (exposto por dado mais sujo da mesma planilha): exigir que TODAS as
    linhas batam o padrão ISO para acionar esse caminho é frágil — uma única linha
    genuinamente malformada (ex. "31/02/2026", texto solto no meio de uma coluna ISO)
    derrubava a detecção pra coluna INTEIRA e reativava o bug acima. Maioria (não
    unanimidade) já basta: linha malformada isolada vira NaT (descarte correto,
    rastreado), sem contaminar as milhares de linhas ISO válidas ao redor dela."""
    non_null = series.dropna().astype(str).str.strip()
    if len(non_null) and non_null.str.match(_ISO_DATE_RE).mean() > 0.5:
        return pd.to_datetime(series, format="mixed", dayfirst=False, errors="coerce")
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

"""
EXRS Data Oracle — Vocabulário de domínio (Vendas/Estoque/Clientes/Financeiro) sobre
o mecanismo genérico de mapeamento de coluna + coerção do kernel
(`kernel.tabular`) — o "sobre o quê" por cima do "como" genérico.

Regras endurecidas (CSO), aplicadas pelo kernel: (1) nenhuma string de moeda pode
sobreviver até o Pydantic — coerção agressiva de "R$ 1.500,00" para 1500.0; (2)
mistura GENUÍNA de formato de data (DD/MM e MM/DD coexistindo na mesma coluna, não
apenas ambiguidade teórica) falha alto — nunca mistura em silêncio.
"""
import pandas as pd

from kernel.tabular import (  # noqa: F401 — re-exportado para quem já importa daqui
    ColumnMappingError, DateAmbiguityError, coerce_currency_series, coerce_date_series,
)
from kernel.tabular import infer_column_roles as _infer_column_roles_generic

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
    "payment": ["forma_pagto", "pagamento", "pagto"],
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
    # Algoritmo 3 (corrosão de desconto) — preço de TABELA do produto, para comparar
    # contra o preço efetivamente praticado na venda. Papel opcional: não entra em
    # _ESTOQUE_REQUIRED_ROLES, então planilha sem esta coluna não quebra nenhum
    # detector de Estoque existente — só desativa o detector que depende dela.
    "list_price": ["preco_venda", "preco_tabela", "preco"],
    # Fase D2 — nome legível do produto, pro Anexo Vivo nunca mostrar só o código
    # cru do SKU. Papel opcional (fora de _ESTOQUE_REQUIRED_ROLES): sem a coluna, o
    # anexo cai pro fallback honesto (só o código) — nunca inventa nome.
    "description": ["descricao", "nome"],
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

# Fase C — vocabulário da aba Compras (a "NF de entrada"): custo REAL de aquisição do
# SKU, por data de compra — usado pra checar se o `entry_cost` registrado na venda
# (aba Vendas) bate com o que a empresa de fato pagou pelo produto. Dict separado dos
# demais pela mesma razão de sempre ("custo"/"sku" mudam de sentido por aba).
_COMPRAS_ROLE_KEYWORDS: dict[str, list[str]] = {
    "purchase_id": ["compra_id", "id"],
    "date": ["data", "emissao"],
    "sku": ["sku", "produto", "item", "codigo"],
    "qty": ["qtd", "quantidade"],
    "cost": ["custo"],
}
_COMPRAS_REQUIRED_ROLES = ("date", "sku", "cost")


def infer_column_roles(
    df: pd.DataFrame, override: dict[str, str] | None = None,
    role_keywords: dict[str, list[str]] | None = None,
    required_roles: tuple[str, ...] | None = None,
) -> dict[str, str]:
    """Wrapper de domínio sobre `kernel.tabular.infer_column_roles`: quando
    `role_keywords`/`required_roles` não são fornecidos, usa o vocabulário de Vendas
    (`_ROLE_KEYWORDS`/`_REQUIRED_ROLES`) — mesmo comportamento de default de antes
    da convergência com o kernel. Chamadas para outras abas (Estoque/Clientes/
    Financeiro) já passam o próprio vocabulário explicitamente e não são afetadas
    por este default."""
    role_keywords = role_keywords if role_keywords is not None else _ROLE_KEYWORDS
    required_roles = required_roles if required_roles is not None else _REQUIRED_ROLES
    return _infer_column_roles_generic(
        df, override=override, role_keywords=role_keywords, required_roles=required_roles,
    )

"""
EXRS Data Oracle — Contratos Forenses (Pydantic V2)

Estes contratos definem a "lei" do módulo `exrs audit`: nenhum detector em
commercial_auditor.py carrega números mágicos — todo limiar vem de
`AuditThresholdsConfig`, injetado explicitamente e registrado no `ExecutiveAuditReport`
final (reprodutibilidade: sabe-se exatamente com quais limiares a auditoria rodou).
"""
from pydantic import BaseModel, Field


class AuditThresholdsConfig(BaseModel):
    """Todos os limiares de sensibilidade dos 4 detectores. Nenhum número mágico deve
    existir fora deste contrato."""
    revenue_drop_sigma: float = 2.0
    churn_cadence_multiplier: float = 2.0
    churn_min_purchases: int = 3
    trend_decoupling_pct: float = 0.0
    seasonality_min_months: int = 12
    materiality_revenue_pct: float = 1.0
    rfm_bins: int = 5
    variable_cost_pct: float = 15.0
    latent_revenue_anchor_category: str = "lente"
    latent_revenue_target_category: str = "solar"
    latent_revenue_conversion_pct: float = 20.0
    dead_stock_months: int = 8
    contingency_completeness_pct: float = 30.0
    outlier_median_ratio: float = 20.0  # valor > N× a mediana do próprio produto = erro de digitação
    # D3 — cold-start: loja cuja PRÓPRIA janela de histórico (primeira à última venda
    # NELA, não da rede) é menor que isto não tem base estatística para que suas
    # métricas sejam tratadas como fato derivado com a mesma confiança de uma loja
    # madura — ver `detect_store_performance`/`StorePerformance.has_sufficient_history`.
    cold_start_min_months: float = 4.0


class SalesRecord(BaseModel):
    """Registro de venda higienizado — a unidade atômica pós-limpeza."""
    date: object  # datetime — aceita datetime.datetime ou pandas.Timestamp
    product: str
    customer: str
    value: float
    quantity: float | None = None
    entry_cost: float | None = None
    category: str | None = None
    store: str | None = None
    source_file: str
    source_row: int


class WinsorizedValue(BaseModel):
    """Procedência de uma linha cujo valor foi podado por ser outlier estatístico
    (cerca de Tukey) — nunca some em silêncio, sempre rastreável até a linha de
    origem."""
    source_file: str
    source_row: int
    product: str
    original_value: float
    capped_value: float


class CleaningSummary(BaseModel):
    """Contabilidade da higienização — nada é descartado em silêncio."""
    rows_read: int
    rows_accepted: int
    rows_discarded_by_reason: dict[str, int] = Field(default_factory=dict)
    files_skipped: list[dict] = Field(default_factory=list)
    values_winsorized: list[WinsorizedValue] = Field(default_factory=list)


class RevenueLeakAnomaly(BaseModel):
    """Queda de receita além do limiar de desvio-padrão histórico."""
    scope: str  # "total" | "product" | "customer"
    entity_id: str
    period: str  # "YYYY-MM"
    expected_value: float
    actual_value: float
    drop_sigma: float
    severity: str  # "low" | "medium" | "high"
    low_confidence: bool = False


class ChurnFinding(BaseModel):
    """Cliente recorrente que parou de comprar sem cancelamento formal."""
    customer_id: str
    purchase_count: int
    avg_cadence_days: float
    last_purchase: str  # "YYYY-MM-DD"
    months_silent: int
    historical_annual_value: float


class ProductTrendEntry(BaseModel):
    """Produto cuja curva de crescimento descolou da empresa."""
    product: str
    company_growth_pct: float
    product_growth_pct: float
    decoupled: bool
    last_sale_month: str | None  # "YYYY-MM"


class RFMChampion(BaseModel):
    """Cliente no quintil máximo (recência + frequência + valor) — a base a proteger a
    qualquer custo. Metodologia RFM clássica: cada dimensão é ranqueada em `rfm_bins`
    quantis; campeão = topo nas 3 ao mesmo tempo."""
    customer_id: str
    recency_days: float
    frequency: int
    monetary: float
    recency_score: int
    frequency_score: int
    monetary_score: int


class ContributionMarginAlert(BaseModel):
    """Produto cuja margem de contribuição média (preço − custo de entrada − variáveis)
    é negativa — cada venda dá prejuízo antes mesmo de despesa fixa."""
    product: str
    avg_price: float
    avg_entry_cost: float
    variable_cost_pct: float
    contribution_margin: float
    sample_size: int


class LatentRevenueFinding(BaseModel):
    """Receita Latente / Attach: separa o FATO medido do CENÁRIO assumido. `attach_rate_pct`
    e `avg_ticket_target_category` são derivados do próprio histórico (régua do cliente).
    `assumed_conversion_pct` é uma premissa de negócio explícita — a loja nunca trabalhou
    esses não-compradores, então não há histórico do que aconteceria; não deriva, assume e
    rotula. `estimated_latent_revenue` é cenário, não fato."""
    anchor_category: str
    target_category: str
    eligible_customers: int  # base elegível: compraram a âncora
    non_buyers_count: int  # compraram âncora, nunca compraram o complemento
    attach_rate_pct: float  # FATO: % da base elegível que já compra o complemento
    avg_ticket_target_category: float  # FATO: ticket médio real do complemento
    assumed_conversion_pct: float  # CENÁRIO: taxa de conversão assumida, ajustável
    estimated_latent_revenue: float  # CENÁRIO: non_buyers × conversão × ticket real
    non_buyer_customers: list[str] = Field(default_factory=list)


class SeasonalityCurve(BaseModel):
    """Índice de sazonalidade mensal — nunca inventa curva sem histórico suficiente."""
    scope: str
    entity: str
    monthly_index: dict[int, float] | None = None
    insufficient_data: bool = False
    months_available: int | None = None


class DeadStockFinding(BaseModel):
    """B4 — SKUs sem movimento há mais que `dead_stock_months` (contagem de meses-
    calendário desde o último movimento até o mais recente movimento conhecido no
    estoque — nunca usa a data do sistema, só o que o arquivo atesta)."""
    dead_stock_months: int
    sku_count: int
    capital_frozen: float  # Σ(qtd_atual × custo) dos SKUs parados
    total_inventory_value: float  # Σ(qtd_atual × custo) de todo o estoque válido
    dead_stock_pct: float  # capital_frozen / total_inventory_value × 100
    skus: list[str] = Field(default_factory=list)


class GmroiEntry(BaseModel):
    """B2 — GMROI por categoria: margem bruta realizada (Vendas: receita − custo de
    entrada) ÷ valor de estoque médio a custo. MEDE E REPORTA o que o dado diz — não
    há alvo esperado, os números da categoria são o que são. `avg_inventory_value` usa
    o snapshot ATUAL do estoque como proxy de médio (o arquivo não tem série temporal
    de níveis de estoque para uma média histórica de verdade) — aproximação rotulada,
    não fingida como exata."""
    category: str
    gross_margin: float
    avg_inventory_value: float
    gmroi: float | None  # None se não há estoque nessa categoria (divisão por zero)
    sample_size: int  # nº de vendas que compuseram a margem bruta


class StorePerformance(BaseModel):
    """D1 — P&L por loja: agrega a MESMA lógica de margem de contribuição de
    `detect_contribution_margin` (preço médio − custo de entrada médio −
    `variable_cost_pct`% do preço), por LOJA em vez de por produto. `gross_revenue`
    soma TODO o valor de venda da loja (inclui estornos negativos — mesmo critério de
    receita usado em `detect_revenue_leaks`); nunca confundido com a margem de
    contribuição real, que só considera vendas com custo de entrada conhecido e
    valor > 0 (estorno não tem "preço", ver A1). `contribution_margin_total` é a
    margem de contribuição REAL da loja em R$ (média por venda × nº de vendas com
    custo conhecido) — é esse número, não `gross_revenue`, que decide se a loja dá
    lucro ou prejuízo.

    D3 — cold-start: `months_of_history` é a janela PRÓPRIA da loja (última venda −
    primeira venda NELA, não da rede) em meses corridos (aproximação, dias / 30.44).
    Loja com `months_of_history < cold_start_min_months` tem `has_sufficient_history
    = False` — suas métricas (faturamento, margem, ranking) não têm base estatística
    para serem apresentadas como fato derivado com a mesma confiança de uma loja
    madura; o consumidor do relatório deve rotulá-las "cenário assumido" / dado
    insuficiente, nunca escondê-las nem tratá-las como equivalentes ao resto da rede.
    Mesmo princípio de `SeasonalityCurve.insufficient_data` (curva de sazonalidade) e
    de `LatentRevenueFinding` (fato medido vs. cenário assumido) — nunca inventa
    confiança que o histórico não sustenta."""
    store: str
    gross_revenue: float
    revenue_sample_size: int  # nº de vendas (linhas) que compuseram gross_revenue
    avg_price: float  # preço médio das vendas com custo de entrada conhecido (valor > 0)
    avg_entry_cost: float
    variable_cost_pct: float
    contribution_margin_avg: float  # margem de contribuição média por venda (R$)
    contribution_margin_total: float  # contribution_margin_avg × margin_sample_size (R$)
    margin_sample_size: int  # nº de vendas com custo de entrada conhecido que compuseram a margem
    months_of_history: float  # (última venda − primeira venda) da PRÓPRIA loja, em meses
    has_sufficient_history: bool  # months_of_history >= thresholds.cold_start_min_months


class StoreMacroSummary(BaseModel):
    """D1 — Resumo macro do P&L por loja: ranking por faturamento bruto vs. ranking
    por margem de contribuição real (mesmo conjunto de lojas, ordens possivelmente
    diferentes — loja de alto volume pode ter margem negativa). `masked_amount` é o
    quanto o agregado saudável da rede MASCARA: soma, em módulo, da
    `contribution_margin_total` de cada loja com margem negativa — a rede "pensa" que
    ganha `network_contribution_margin_total`, mas isso já é o líquido depois do
    prejuízo dessas lojas ter sido absorvido pelo resto; `masked_amount` é quanto
    maior o resultado seria sem elas.

    D3 — cold-start: `revenue_rank`/`margin_rank` incluem TODAS as lojas, cold-start
    inclusive (não há motivo para escondê-las do ranking, só para rotular a
    confiança). `network_contribution_margin_total` também soma TODAS as lojas —
    dinheiro que já entrou/saiu de caixa é fato, não deixa de ser real por a loja ser
    nova. Já `stores_with_negative_margin`/`masked_amount` são uma alegação
    interpretativa ("estas lojas estruturalmente mascaram o resultado saudável da
    rede") — atribuir esse rótulo a uma loja cold-start com poucas semanas/meses de
    dado confundiria ruído estatístico de amostra pequena com prejuízo estrutural;
    por isso essas duas métricas somam apenas lojas com `has_sufficient_history =
    True`. Loja cold-start com margem negativa continua aparecendo em
    `StorePerformance.contribution_margin_total` normalmente (fato bruto), só não
    entra na narrativa de "mascaramento estrutural"."""
    stores_with_negative_margin: list[str] = Field(default_factory=list)
    masked_amount: float
    network_contribution_margin_total: float
    revenue_rank: list[str] = Field(default_factory=list)  # lojas por faturamento bruto, desc
    margin_rank: list[str] = Field(default_factory=list)  # lojas por margem de contribuição real, desc
    rank_differs: bool  # True se a ordem dos dois rankings acima não é idêntica


class DataCompletenessFinding(BaseModel):
    """A1 — Completude de cadastro (telefone + CPF), aba Clientes. Métrica de
    completude POR CAMPO (não por cliente): telefone e CPF podem faltar
    independentemente por cliente (dado real messy) — média de preenchimento dos 2
    campos é mais honesta que exigir os 2 juntos (que penaliza um cliente com só 1
    dado faltando tanto quanto um sem nenhum). Abaixo de `contingency_completeness_pct`,
    o relatório deve liderar pela série B em vez de churn/RFM/latente (dado de
    contato pouco confiável)."""
    total_customers: int
    phone_filled_pct: float
    document_filled_pct: float
    completeness_pct: float  # média dos dois campos acima
    contingency_triggered: bool


class ExecutiveAuditReport(BaseModel):
    """Artefato final: encapsula toda a auditoria. Campos de cliente já vêm
    pseudo-anonimizados (Client_A, Client_B...) — nomes reais nunca aparecem aqui."""
    period_start: str  # "YYYY-MM"
    period_end: str  # "YYYY-MM"
    cleaning: CleaningSummary
    thresholds: AuditThresholdsConfig
    revenue_leaks: list[RevenueLeakAnomaly] = Field(default_factory=list)
    churn_findings: list[ChurnFinding] = Field(default_factory=list)
    product_trends: list[ProductTrendEntry] = Field(default_factory=list)
    seasonality: list[SeasonalityCurve] = Field(default_factory=list)
    rfm_champions: list[RFMChampion] = Field(default_factory=list)
    contribution_margin_alerts: list[ContributionMarginAlert] = Field(default_factory=list)
    latent_revenue: list[LatentRevenueFinding] = Field(default_factory=list)
    dead_stock: list[DeadStockFinding] = Field(default_factory=list)
    gmroi: list[GmroiEntry] = Field(default_factory=list)
    data_completeness: list[DataCompletenessFinding] = Field(default_factory=list)
    store_performance: list[StorePerformance] = Field(default_factory=list)
    store_macro_summary: StoreMacroSummary | None = None
    generated_at: str

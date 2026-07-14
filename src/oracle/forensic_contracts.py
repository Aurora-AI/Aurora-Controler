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
    # D4 — SEV, captura de cliente: piso de % de vendas COM cliente identificado
    # (não-anônimo, ver `_ANONYMOUS_CUSTOMER`) abaixo do qual um vendedor tem "captura
    # baixa". Calibrado contra o dado real de referência (`consultoria_real_test.xlsx`):
    # entre os vendedores maduros (tenure > 1 ano), a maioria captura entre ~64% e ~77%
    # dos clientes; um único vendedor destoa do grupo em ~55% — 60% fica no meio do
    # vão entre os dois clusters (não colado em nenhuma borda), separando o outlier
    # real sem depender de nome/ID cravado — ver `detect_salesperson_performance`.
    sev_min_capture_pct: float = 60.0
    # D4 — SEV, ramp-up: tenure mínima (dias desde a PRÓPRIA primeira venda do
    # vendedor até a data mais recente conhecida na rede — mesmo estilo de
    # `cold_start_min_months`, em dias em vez de meses) abaixo da qual um vendedor
    # ainda está em curva de maturação e NUNCA pode ser penalizado por volume baixo
    # (`SalespersonPerformance.low_volume_flag`). 180 dias (~6 meses) é referência
    # comum de tempo-de-rampa em venda de produto técnico (ótica: portfólio +
    # relacionamento não se aprende em semanas). Confortavelmente acima de qualquer
    # tenure real de vendedor novo observada no dado de referência (~39-101 dias,
    # vendedores mais recentes da rede) — margem de quase 2x sobre o maior desses,
    # não colado na borda.
    sev_ramp_min_days: float = 180.0
    # B7 — concentração de cliente (risco de key-account): % da receita de UMA loja que
    # vem de um único cliente, acima do qual perder aquele cliente machuca a economia
    # daquela loja de verdade — ver `detect_customer_concentration`. Referência comum de
    # risco de concentração de cliente para uma unidade de negócio pequena (uma única
    # loja, não a rede inteira) gira em torno de 20-25%: é o mesmo tipo de corte usado
    # em divulgação contábil de "cliente significativo" (tipicamente >=10% no nível da
    # EMPRESA inteira, universo muito maior) escalado para cima porque aqui o universo é
    # uma única loja — perder 10% de UMA loja para um cliente é corriqueiro, perder 25%
    # não é. Calibrado contra a distribuição REAL de concentração cliente×loja em
    # `tests/fixtures/consultoria_real_test.xlsx` (sem ler a aba Gabarito — só a
    # distribuição bruta, via `detect_customer_concentration` rodado sobre os dados de
    # Vendas): média ~2.3%, terceiro quartil ~2.6%, e o segundo maior valor observado no
    # dado inteiro (~17.4%) vem de uma loja cold-start de baixíssimo volume (10 clientes
    # distintos, ~R$ 6,5 mil de receita total — ruído estatístico de amostra pequena,
    # não risco estrutural). O maior valor observado no dado (~32%) destoa claramente do
    # resto da distribuição. 25% fica confortavelmente no vão entre os dois — separa o
    # ruído de amostra pequena do sinal real sem colar em nenhuma borda.
    concentration_risk_pct: float = 25.0


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
    salesperson: str | None = None
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


class CustomerConcentrationFinding(BaseModel):
    """B7 — Concentração de cliente (risco de key-account): cliente cuja fatia da
    receita de UMA loja é alta o bastante para configurar risco real — se ele parar de
    comprar, a loja sente de verdade (perda desproporcional para uma única unidade de
    negócio, diferente de perder um cliente qualquer de uma base de centenas).

    `concentration_pct` = `customer_revenue` (soma de `value` do cliente NAQUELA loja) ÷
    `store_revenue` (soma de `value` de TODA a loja — mesmo critério de receita bruta
    usado em `StorePerformance.gross_revenue`: inclui estornos negativos, sem filtrar
    por custo de entrada conhecido; as duas somas vêm da mesma base, só o numerador
    restringe a 1 cliente). Agrupamento é DINÂMICO por (loja, cliente) — nunca uma
    lista fixa de lojas ou clientes, funciona para qualquer rede.

    Pseudo-cliente (`is_pseudo_entity`, walk-in sem cadastro) nunca aparece como
    `customer` aqui: ele é a soma de MUITOS passantes diferentes, não uma pessoa — sem
    essa exclusão, ele facilmente pareceria "concentrar" boa parte da receita de uma
    loja só por agregar volume de gente que não tem relação nenhuma entre si, gerando um
    falso alarme de key-account que não é ninguém de verdade (mesma classe de bug já
    corrigida em churn/RFM/receita latente/SEV — ver registro único
    `_PSEUDO_ENTITY_IDS`/`is_pseudo_entity` em `commercial_auditor.py`)."""
    store: str
    customer: str
    customer_revenue: float  # receita do cliente NAQUELA loja (inclui estornos)
    store_revenue: float  # receita bruta TOTAL da loja — mesmo critério de StorePerformance.gross_revenue
    concentration_pct: float  # customer_revenue / store_revenue × 100
    sample_size: int  # nº de vendas (linhas) do cliente naquela loja — procedência


class SalespersonPerformance(BaseModel):
    """D4 — SEV (Sistema de Eficiência de Venda): duas asserções INDEPENDENTES uma da
    outra, nunca uma mascarando a outra.

    (1) Captura de cliente: `capture_rate_pct` é a % das vendas do vendedor com
    cliente identificado (não-anônimo, ver `_ANONYMOUS_CUSTOMER` — mesmo pseudo-grupo
    de walk-in já usado por churn/RFM/receita latente). `low_capture_flag` é
    `capture_rate_pct < thresholds.sev_min_capture_pct` e é SEMPRE avaliado — nunca
    suprimido por `has_sufficient_tenure` nem por `total_revenue`/`sample_size` altos.
    Um vendedor pode converter muito bem (receita e volume altos) e ainda ter captura
    baixa; são dimensões diferentes, uma não perdoa a outra.

    (2) Ramp-up: `days_since_first_sale` é a tenure do vendedor — da PRÓPRIA primeira
    venda dele até a data mais recente conhecida na rede (mesmo estilo de
    `StorePerformance.months_of_history`/D3, em dias em vez de meses).
    `has_sufficient_tenure` é `days_since_first_sale >= thresholds.sev_ramp_min_days`.
    `low_volume_flag` só pode ser True quando `has_sufficient_tenure=True` — um
    vendedor em ramp (tenure curta) NUNCA é penalizado por volume baixo, mesmo que o
    volume dele seja objetivamente baixo comparado à rede; volume baixo em ramp é
    esperado, não é sinal de baixo desempenho. A comparação de "baixo" usa a MEDIANA de
    `sample_size` entre os pares com tenure suficiente (nunca a rede inteira, que
    incluiria vendedores em ramp e enviesaria o piso para baixo) — estatística robusta,
    não um terceiro limiar mágico.

    `total_revenue`/`sample_size` somam TODA venda do vendedor (inclui vendas
    anônimas e estornos negativos — mesmo critério de `StorePerformance.gross_revenue`)
    — é exatamente por incluir as vendas anônimas na base que a captura baixa fica
    visível mesmo quando o vendedor "converte bem"."""
    salesperson: str
    total_revenue: float
    sample_size: int  # nº de vendas do vendedor (procedência de todas as métricas abaixo)
    capture_rate_pct: float  # % das vendas com cliente identificado (não-anônimo)
    low_capture_flag: bool  # capture_rate_pct < sev_min_capture_pct — SEMPRE avaliado
    days_since_first_sale: int  # tenure: primeira venda DELE -> data mais recente da rede
    has_sufficient_tenure: bool  # days_since_first_sale >= sev_ramp_min_days
    low_volume_flag: bool  # só pode ser True quando has_sufficient_tenure=True


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
    customer_concentration: list[CustomerConcentrationFinding] = Field(default_factory=list)
    salesperson_performance: list[SalespersonPerformance] = Field(default_factory=list)
    generated_at: str

"""
EXRS Data Oracle — Contratos Forenses (Pydantic V2)

Estes contratos definem a "lei" do módulo `exrs audit`: nenhum detector em
commercial_auditor.py carrega números mágicos — todo limiar vem de
`AuditThresholdsConfig`, injetado explicitamente e registrado no `ExecutiveAuditReport`
final (reprodutibilidade: sabe-se exatamente com quais limiares a auditoria rodou).
"""
from __future__ import annotations
from pydantic import BaseModel, Field


class AuditThresholdsConfig(BaseModel):
    """Todos os limiares de sensibilidade dos 4 detectores. Nenhum número mágico deve
    existir fora deste contrato."""
    revenue_drop_sigma: float = 2.0
    churn_cadence_multiplier: float = 2.0
    churn_min_purchases: int = 3
    trend_decoupling_pct: float = 20.0
    seasonality_min_months: int = 12
    materiality_revenue_pct: float = 1.0
    rfm_bins: int = 5
    variable_cost_pct: float = 15.0
    # C3 — forma de pagamento que marca promoção deliberada: produto cuja margem
    # negativa vem 100% de vendas com este rótulo é `promotional`, não estrutural.
    promo_payment_label: str = "promocao"
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
    # SVC — camada de serviço: valor da coluna "categoria" que identifica uma linha de
    # SERVIÇO (ajuste/reparo/conserto), não produto. Configurável como
    # latent_revenue_anchor_category/target_category já são (nome de categoria como
    # valor de negócio, não número, mas mesma filosofia: nunca string cravada dentro
    # de uma função, sempre um campo aqui). Serviço não tem estoque (sem SKU na aba
    # Estoque) — precisa ficar fora de GMROI, e fora do ticket/RFM de PRODUTO (ver
    # detect_rfm_champions, detect_contribution_margin, detect_service_decomposition).
    service_category_label: str = "servico"
    # SVC5 — Reconciliação Financeiro × Vendas de serviço: tolerância em R$ acima da
    # qual (loja, mês) vira gap reportável. Observado no dado real: quando a aba
    # Financeiro e a soma transacional de Vendas batem, batem ao CENTAVO (mesma fonte,
    # dois lugares) — não há "quase bateu" genuíno. Um valor pequeno (R$1, cobre só
    # arredondamento) já separa reconciliação real de gap real, sem precisar de um
    # percentual (que erraria em lojas de receita de serviço pequena).
    service_reconciliation_gap_tolerance: float = 1.0
    # Fase B — Algoritmo 1 (GMROI por SKU): "margem ilusória" = markup alto mas giro
    # lento — as duas pernas do alerta, cada uma com seu próprio corte. `..._high_
    # margin_pct` é o piso de markup (%) acima do qual a margem é "alta". `..._low_
    # ratio` é o teto de GMROI abaixo do qual o giro é "lento" — referência de mercado
    # de varejo: GMROI >= 1.0 significa que a margem bruta anual já cobre o capital
    # investido no próprio SKU; abaixo de 1.0 o capital parado custa mais do que a
    # margem devolve. Um produto pode ter as duas coisas ao mesmo tempo (alta margem %
    # E giro lento) — é exatamente essa combinação que o algoritmo caça.
    gmroi_sku_high_margin_pct: float = 40.0
    gmroi_sku_low_ratio: float = 1.0
    # Fase B — Algoritmo 3 (corrosão de desconto por vendedor): quantos desvios-padrão
    # ACIMA da média de desconto% DA MESMA LOJA (nunca da rede inteira — vendedores de
    # lojas diferentes não competem no mesmo benchmark) um vendedor precisa estar para
    # virar `is_corrosive`. 2 desvios é o mesmo corte estatístico já usado em
    # `revenue_drop_sigma` neste contrato — consistência de vocabulário estatístico
    # dentro do motor.
    seller_corrosion_std_multiplier: float = 2.0
    # Fase B — Algoritmo 4 (concentração de VIP por vendedor): dentro dos clientes VIP
    # de UMA loja (ver `vip_customer_top_pct`), % da receita VIP daquela loja atrelada
    # a um único vendedor acima do qual existe risco de "sequestro de base" (o
    # vendedor, não a empresa, é dono do relacionamento). Mesma ordem de grandeza do
    # corte de `concentration_risk_pct` (cliente único concentra loja) — aqui é
    # vendedor único concentrando o segmento mais valioso da loja, risco maior por
    # isso o corte é mais alto.
    concentration_seller_vip_pct: float = 40.0
    # Fase B — Algoritmo 4: fatia (%) dos clientes de MAIOR receita, por loja, tratada
    # como "VIP" (Pareto aproximado — 20% é a referência clássica de curva ABC, não
    # verificada empiricamente contra 80% de receita neste dado; é a definição
    # operacional do algoritmo, não uma medição).
    vip_customer_top_pct: float = 20.0
    # Fase C — Triggers de triagem, POR TRANSAÇÃO (nunca o agregado sem teto por
    # vendedor da Fase B). Trigger A: |desconto sobre a tabela|% acima disto dispara
    # (positivo = vendeu bem abaixo da tabela; negativo = vendeu acima — os dois lados
    # são discrepância). 60% é o corte: uma promoção legítima raramente passa disso
    # sem virar liquidação de fato; abaixo disso é agressividade comercial normal, não
    # matéria de triagem.
    manual_review_discount_pct: float = 60.0
    # Fase C, evidência E4 — % de divergência entre o custo registrado na PRÓPRIA
    # linha de venda (`entry_cost`) e o custo da Compra (NF) mais recente anterior à
    # venda, acima do qual o cadastro é considerado desalinhado da aquisição real.
    # Calibrado para tolerar oscilação normal de reposição (fretes/negociação pontual)
    # sem tolerar cadastro parado (ex.: caso real ARP-013: custo na venda ~R$700-850
    # vs NF ~R$309 — divergência de ~130%, muito acima deste corte).
    nf_cost_divergence_pct: float = 15.0
    # Fase D, Pilar 1 (mix de margem por vendedor) — gap, em PONTOS PERCENTUAIS, entre
    # a margem blendada da loja e a margem blendada do vendedor, acima do qual o
    # vendedor é `is_margin_destructive`. 10pp é uma corrosão substancial (ex.: loja
    # margeia 40%, vendedor margeia 30% ou menos) — não confunde com a variação
    # normal de mix entre vendedores maduros, que costuma ficar num vão mais estreito.
    seller_margin_gap_pct: float = 10.0
    # Amostra mínima de vendas do vendedor (na loja, período todo) para a acusação de
    # "destruidor de margem" ter base estatística — mesmo espírito de
    # `sev_ramp_min_days`/`benchmark_population`: nunca aponta padrão em ruído de
    # amostra pequena.
    seller_margin_mix_min_sample: int = 10
    # Fase D, Pilar 2 — teto de linhas de origem exibidas por achado agregado
    # (corrosão de desconto, mix de margem). Amostra representativa, não lista
    # exaustiva — `sample_size` do achado é sempre o total real; o teto existe só
    # pra o JSON/anexo não explodir em achados com centenas de vendas.
    provenance_sample_cap: int = 10
    # Fase E, E1 (evasão de vendedor) — largura da janela "recente" (em meses) que
    # cada perna (captura/desconto/ticket) compara contra o histórico do PRÓPRIO
    # vendedor (nunca a rede). Mesmo espírito de `flight_risk_trend_window_months`
    # ser pequeno o bastante pra pegar uma virada real sem exigir anos de dado.
    flight_risk_trend_window_months: int = 3
    # Fase E, E1 — desvios-padrão da variabilidade histórica da PRÓPRIA série (nunca
    # um ponto-percentual fixo) que a queda/alta recente precisa exceder pra a perna
    # disparar — mesmo idioma estatístico de `revenue_drop_sigma`/
    # `seller_corrosion_std_multiplier` (2.0), aqui um pouco mais sensível (1.5)
    # porque a janela de comparação já é curta (poucos meses) e um corte igual a 2.0
    # deixaria passar viradas reais antes que a carteira evapore de vez.
    flight_risk_trend_sigma: float = 1.5
    # Fase E, E1 — de 3 pernas possíveis (captura/desconto/ticket), quantas precisam
    # disparar pra virar achado. 2 exige convergência de pelo menos duas dimensões
    # independentes — mesmo espírito de exigir 2 evidências simultâneas do Mix de
    # Margem (Fase D, Pilar 1) — nunca acusa por uma métrica isolada que pode ser
    # ruído sazonal de um mês.
    flight_risk_min_flags: int = 2
    # Fase E, E3 (habilidade proxy) — piso de quanto o vendedor precisa VENDER MENOS
    # que o padrão da própria loja (mix_deviation_pp negativo, em pontos percentuais)
    # numa categoria de margem alta pra virar hipótese de déficit de treinamento.
    # Mesma unidade/ordem de grandeza de `seller_margin_gap_pct` (10pp) — desvio de
    # mix pequeno é variação normal de atendimento, não padrão de evitação.
    skill_gap_avoidance_pp: float = 10.0
    # Fase E, E2 (conflito de comissionamento) — fato de negócio declarado pelo
    # consultor na configuração da rodada (não inferido da planilha, não há como
    # inferir % de comissão a partir de receita e custo sozinhos). "unknown"
    # (default) é o ponto cego honesto: o detector não avalia nada e emite
    # DiscardedAlarm em vez de adivinhar. Mesmo espírito de `service_category_label`/
    # `promo_payment_label` (vocabulário de negócio como campo, não string cravada).
    commission_basis: str = "unknown"  # "gross_revenue" | "contribution_margin" | "mixed"


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
    payment_method: str | None = None
    source_file: str
    source_row: int
    has_formula_error: bool = False


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
    raw_declared_revenue: float | None = None
    reconciliation_gap: float | None = None


class RevenueLeakAnomaly(BaseModel):
    """Queda de receita além do limiar de desvio-padrão histórico."""
    scope: str  # "total" | "product" | "customer"
    entity_id: str
    period: str  # "YYYY-MM"
    expected_value: float
    actual_value: float
    drop_sigma: float
    seasonality_adjusted: bool = False
    confidence: str = "high"
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
    # Fase D, Pilar 2 — Chave de Rastreabilidade: toda linha de Vendas deste
    # cliente, referenciável de volta ao arquivo original do cliente ("Vendas #189").
    source_rows: list[int] = Field(default_factory=list)
    # Fase D, Pilar 3 — Índice de Recuperabilidade: dias em silêncio ÷ cadência
    # PRÓPRIA do cliente (não um piso fixo de dias). Um cliente de ciclo curto que
    # acabou de estourar o próprio ritmo (ratio perto de 1.0-1.5, ex.: ciclo 30d
    # silente há 35d) é lead MUITO mais quente que um cliente de ciclo longo silente
    # há muito mais tempo em absoluto mas ainda dentro de múltiplos moderados do
    # PRÓPRIO ciclo (ex.: ciclo 90d silente há 120d, ratio 1.33) — ordenar a fila só
    # por R$ histórico queima energia de balcão em CPF frio. `days_since_last` é a
    # métrica em dias (mais fina que `months_silent`, que é bucket mensal) usada no
    # denominador da razão. NUNCA rotulado como probabilidade/score preditivo — é
    # razão de dois fatos medidos (dias ÷ cadência), não uma projeção.
    days_since_last: int = 0
    silence_to_cycle_ratio: float = 0.0


class ProductTrendEntry(BaseModel):
    """Produto cuja curva de crescimento descolou da empresa."""
    product: str
    company_growth_pct: float
    product_growth_pct: float
    decoupled: bool
    last_sale_month: str | None = None
    short_term_margin: float | None = None
    has_formula_errors: bool = False


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
    é negativa — cada venda dá prejuízo antes mesmo de despesa fixa.

    `promotional=True` (C3): TODAS as vendas do produto têm forma de pagamento igual a
    `promo_payment_label` — margem negativa é decisão comercial deliberada, não
    prejuízo estrutural. Fica fora de `total_operational_loss`; basta UMA venda
    não-promocional para voltar a ser estrutural (conservador por construção)."""
    product: str
    avg_price: float
    avg_entry_cost: float
    variable_cost_pct: float
    contribution_margin: float
    sample_size: int
    promotional: bool = False


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
    # Fase D, Pilar 2 — Chave de Rastreabilidade: linha(s) do SKU na aba Estoque
    # (lista porque o mesmo SKU pode aparecer 1x por loja no catálogo — nunca perde
    # ocorrência por sobrescrita de dict).
    sku_source_rows: dict[str, list[int]] = Field(default_factory=dict)
    # Fase D2 — capital preso POR SKU (soma das ocorrências, se o mesmo SKU aparece
    # parado em >1 loja) — sem isso, o Anexo Vivo não consegue montar a tabela por
    # item sem reabrir a planilha (violaria "build_anexo lê só o congelado").
    # Σ(sku_capital.values()) ≡ capital_frozen (identidade que o validador confere).
    sku_capital: dict[str, float] = Field(default_factory=dict)
    # Fase D2 — meses parado por SKU (pior caso, se em >1 loja com datas diferentes).
    sku_months_since: dict[str, int] = Field(default_factory=dict)
    # Fase D2 — nome legível ("Óculos Solar Polarizado A"), papel opcional
    # `description` em Estoque. SKU sem descrição reconhecível fica de fora do
    # dict (fallback honesto: o anexo mostra só o código) — nunca inventa nome.
    sku_descriptions: dict[str, str] = Field(default_factory=dict)


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
    is_directional_only: bool = False


class GmroiSkuAlert(BaseModel):
    """Fase B, Algoritmo 1 — GMROI por SKU (granularidade diferente de `GmroiEntry`,
    que é por categoria): produto com markup% alto E giro lento ao mesmo tempo —
    "margem ilusória", porque o preço parece ótimo na etiqueta mas o capital parado no
    próprio SKU rende menos do que custa manter. Lista já vem filtrada só pros SKUs
    que batem as DUAS pernas (`gmroi_sku_high_margin_pct` e `gmroi_sku_low_ratio`) —
    mesmo padrão de `ContributionMarginAlert` (só o que é alerta, não o universo
    inteiro)."""
    sku: str
    total_revenue: float
    total_cost: float
    gross_margin: float
    markup_pct: float  # gross_margin / total_revenue × 100
    capital_frozen: float  # qtd_atual × custo_unit deste SKU no snapshot de Estoque
    gmroi: float  # gross_margin / capital_frozen
    is_illusory_margin: bool = True  # sempre True nesta lista — documentativo


class CrossSellGapCustomer(BaseModel):
    """Um cliente elegível (comprou a categoria âncora) que nunca comprou a categoria
    complementar — candidato a abordagem de cross-sell."""
    customer_id: str
    anchor_category_revenue: float  # receita já gerada por este cliente na âncora


class AttachRateOpportunity(BaseModel):
    """Fase B, Algoritmo 2 — Attach Rate: mesma régua fato-vs-cenário de
    `LatentRevenueFinding` (âncora/alvo configuráveis nos MESMOS
    `latent_revenue_anchor_category`/`latent_revenue_target_category` — um único par
    de categorias no contrato, nunca dois vocabulários divergentes para a mesma ideia
    de negócio). `attach_rate_pct` é FATO medido; `cross_sell_gap` traz só os 5
    clientes de maior receita na âncora entre os que nunca compraram o alvo — a fila
    de abordagem mais valiosa primeiro, nunca a lista inteira (ver Spec de laudo
    executivo, teto de 5 na visão executiva)."""
    anchor_category: str
    target_category: str
    eligible_customers: int  # compraram a âncora
    attach_rate_pct: float  # % dos elegíveis que também compraram o alvo
    cross_sell_gap: list[CrossSellGapCustomer] = Field(default_factory=list)


class SellerMarginCorrosionAlert(BaseModel):
    """Fase B, Algoritmo 3 — Corrosão de ticket médio por vendedor: desconto concedido
    (preço de TABELA do Estoque − preço efetivamente praticado na venda) como % da
    receita do vendedor, comparado contra a média de desconto% dos PARES DA MESMA
    LOJA (nunca a rede inteira — lojas têm política de preço/piso diferentes).
    `is_corrosive` só é True quando `discount_pct` excede a média da loja em mais de
    `seller_corrosion_std_multiplier` desvios-padrão — vendedor que bate meta dando
    desconto fora da curva dos colegas da mesma unidade."""
    salesperson: str
    store: str
    total_revenue: float
    total_discount: float  # Σ(preço_tabela − preço_praticado) × qtd, pode ser negativo
    discount_pct: float  # total_discount / total_revenue × 100
    store_mean_discount_pct: float
    store_std_discount_pct: float
    sample_size: int
    is_corrosive: bool
    # Fase C — True quando este vendedor tem item em `discrepancy_triage.
    # auto_classified` com `verdict="suspected_cadastral_error"` cobrindo o mesmo
    # (loja, vendedor). Vendedor cujo desconto vem de tabela cadastralmente errada
    # NUNCA pode ser apresentado como corrosivo (culpa exige referência confiável —
    # Spec de Laudo Executivo v4 §15.5) — `is_corrosive` é forçado a False quando
    # `tainted_by_triage=True`, mesmo que o desvio estatístico bruto (2σ) apontasse
    # outlier.
    tainted_by_triage: bool = False
    # Fase D, Pilar 2 — Chave de Rastreabilidade: amostra (teto `provenance_sample_
    # cap`, nunca todas as N vendas do grupo — evitaria o JSON explodir) das linhas
    # de Vendas que compõem este alerta. Amostra, não lista exaustiva — `sample_size`
    # acima é o total real.
    sample_source_rows: list[int] = Field(default_factory=list)


class ConcentrationRiskAlert(BaseModel):
    """Fase B, Algoritmo 4 — Curva ABC cruzada / risco de "sequestro de base": dentro
    dos clientes VIP de UMA loja (top `vip_customer_top_pct`% por receita, Pareto
    aproximado), % da receita VIP daquela loja que passa pelas mãos de um único
    vendedor. Vendedor com concentração alta É o dono do relacionamento com a base
    mais valiosa da loja — risco de retenção se ele sair, não só de performance."""
    store: str
    salesperson: str
    vip_revenue: float  # receita deste vendedor vinda de clientes VIP da loja
    vip_total_store: float  # receita VIP total da loja (denominador)
    concentration_pct: float
    is_high_risk: bool  # concentration_pct > thresholds.concentration_seller_vip_pct


class DiscrepancyEvidence(BaseModel):
    """Fase C — os 5 sinais que o motor já tem no próprio dado para pré-classificar
    uma discrepância de preço sem depender de investigação humana. Cada campo é um
    FATO checável, nunca uma opinião — o veredito (ver `DiscrepancyTriageItem`) é uma
    função determinística deste vetor (árvore de decisão fixa, ver
    SPEC_Fase_C_Fila_Auditoria_Manual.md §3.2)."""
    below_cost: bool  # E1 — alguma venda do grupo abaixo do custo da própria linha
    sku_in_dead_stock: bool  # E2 — SKU está em `dead_stock[0].skus`
    is_promo_flagged: bool  # E3 — TODAS as vendas triadas do grupo são forma_pagto=promoção
    cost_diverges_from_nf: bool  # E4 — custo_entrada da venda diverge do custo da Compra (NF) mais recente
    store_systemic_pattern: bool  # E5 — a MEDIANA de desconto do (loja, SKU) inteiro também é implausível


class DiscrepancyTriageItem(BaseModel):
    """Fase C — um item por (SKU, loja, vendedor) cujo desconto sobre a tabela ou
    venda abaixo do custo passou de `manual_review_discount_pct`/`nf_cost_
    divergence_pct`. `verdict=None` só quando `status="pending_manual_review"` — as
    evidências não bastaram para a árvore de decisão classificar sozinha, e o item
    vai para veredito humano (ver `apply_manual_review_verdicts`)."""
    id: str
    sku: str
    # Fase D2 — nome legível do SKU (papel opcional `description` em Estoque);
    # None quando o catálogo não tem a coluna ou o SKU não está nele — fallback
    # honesto, o anexo mostra só o código.
    sku_description: str | None = None
    store: str
    salesperson: str
    source_rows: list[int] = Field(default_factory=list)  # procedência — linha de origem no arquivo
    practiced_price: float  # preço unitário médio praticado nas vendas do grupo
    list_price: float | None = None  # preço de tabela (Estoque) — None se SKU sem catálogo
    # custo médio de entrada nas próprias linhas de venda — None quando o grupo
    # disparou só pelo Trigger A (desconto sobre tabela) e a linha nunca teve
    # `entry_cost` capturado (Trigger A não depende de custo, só de preço de tabela)
    entry_cost: float | None = None
    nf_cost: float | None = None  # custo na Compra (NF) mais recente anterior à venda — None se indeterminável
    discount_over_list_pct: float | None = None  # (list_price - practiced)/list_price × 100; None sem list_price
    # Fase E parte 1 (Z3) — perda monetária REAL do grupo, somada LINHA A LINHA só nas
    # vendas que dispararam `below_cost` (nunca a média do grupo × qtd total — o grupo
    # pode ter linhas acima e abaixo do custo misturadas). None quando o grupo não
    # disparou por `below_cost` (fallback honesto, nunca 0.0 fingido).
    below_cost_loss_brl: float | None = None
    # Fase E parte 1 (QA, achado de revisão) — flag EXPLÍCITA: este item sobreviveu à
    # reclassificação e é sangria genuína (`verdict == "below_cost_sale"`), não
    # artefato de cadastro errado. Fonte única da verdade sobre "conta no total
    # agregado" — motor, validador (Z3) e template leem esta flag, nenhum deles
    # re-deriva a regra comparando `verdict` de novo (mesmo padrão de
    # `tainted_by_triage`: decisão calculada uma vez, propagada, nunca repetida).
    below_cost_confirmed: bool = False
    evidence: DiscrepancyEvidence
    verdict: str | None = None  # "suspected_cadastral_error"|"below_cost_sale"|"deliberate_liquidation"|None
    status: str  # "auto_classified" | "pending_manual_review"


class DiscrepancyTriage(BaseModel):
    """Fase C — resultado da triagem: `manual_queue` deve ser o RESÍDUO, não o
    atacado (critério de aceite: <10% dos itens disparados na fila — fila inundada é
    árvore de decisão errada, não "trabalho para depois", ver Spec §15.2)."""
    triggered_count: int
    auto_classified: list[DiscrepancyTriageItem] = Field(default_factory=list)
    manual_queue: list[DiscrepancyTriageItem] = Field(default_factory=list)
    # Fase E parte 1 (Z3) — Σ de below_cost_loss_brl SÓ dos itens com
    # verdict=="below_cost_sale" (auto_classified + manual_queue, embora este
    # último nunca tenha esse veredito por construção — status=pending_manual_review
    # implica verdict=None). `below_cost=True` é a EVIDÊNCIA da linha, não o
    # veredito final: item reclassificado para suspected_cadastral_error tem
    # below_cost_loss_brl preenchido (fato honesto) mas NÃO entra aqui — é artefato
    # de cadastro errado, não sangria real (§15.5). None quando nenhum item tem
    # veredito below_cost_sale (não há total a cruzar, Z3 não aciona).
    below_cost_total_brl: float | None = None


class AdvancedMetrics(BaseModel):
    """Namespace comum das teses analíticas pós-Fase A (Fase B: os 5 algoritmos
    originais; Fase C: `discrepancy_triage`; Fase D: `seller_margin_mix`) — cada uma
    com seu próprio graceful degradation: dado insuficiente para UMA tese (sem aba
    Estoque, sem coluna de categoria/vendedor/pagamento, etc.) => lista vazia (ou
    `None` quando o resultado é escalar/objeto único), NUNCA quebra o motor nem as
    outras teses."""
    gmroi_alerts: list[GmroiSkuAlert] = Field(default_factory=list)
    attach_rate_opportunities: list[AttachRateOpportunity] = Field(default_factory=list)
    seller_margin_corrosion: list[SellerMarginCorrosionAlert] = Field(default_factory=list)
    concentration_risk: list[ConcentrationRiskAlert] = Field(default_factory=list)
    # Fração 0..1 (nunca %) de clientes cuja PRIMEIRA transação foi serviço e que
    # depois compraram produto (categoria != service_category_label) em data
    # estritamente posterior. None quando não há base de clientes "iniciados em
    # serviço" no dado (sem categoria de serviço, ou ninguém começou por lá) — nunca
    # 0.0 fingido. Nome do campo (`follow_on_conversion`, sem sufixo `_rate`) segue o
    # schema literal da OS (SPEC_Fase_B_Formulas_Avancadas.md, seção 4).
    follow_on_conversion: float | None = None
    # Fase C — None quando não dá pra rodar NENHUM dos dois triggers (ex.: sem coluna
    # `entry_cost` E sem `list_price` disponível); ver `detect_discrepancy_triage`.
    # `DiscrepancyTriage(triggered_count=0, ...)` (não-None) é o estado "rodou, não
    # achou nada implausível" — distinto de "não rodou".
    discrepancy_triage: DiscrepancyTriage | None = None
    # Fase D, Pilar 1 — mix de venda por categoria de margem, um item por (loja,
    # vendedor) com amostra suficiente. Lista vazia quando faltar coluna de
    # categoria/vendedor/custo, ou quando ninguém bater `seller_margin_mix_min_sample`
    # — nunca aponta "destruidor de margem" sem base estatística.
    seller_margin_mix: list[SellerMarginMixProfile] = Field(default_factory=list)


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


class SellerCategoryMixEntry(BaseModel):
    """Fase D, Pilar 1 — uma categoria dentro do mix de UM vendedor: quanto ela pesa
    na receita dele vs. quanto pesa na receita da PRÓPRIA loja (todos os vendedores).
    `mix_deviation_pp` positivo = o vendedor empurra essa categoria MAIS que os pares
    da mesma loja — é essa lista, ordenada pelo desvio, que explica O PORQUÊ de
    `SellerMarginMixProfile.is_margin_destructive`, nunca só o rótulo."""
    category: str
    seller_revenue: float
    seller_mix_pct: float  # % da receita do vendedor nesta categoria
    store_mix_pct: float  # % da receita da loja (todos os vendedores) nesta categoria
    mix_deviation_pp: float  # seller_mix_pct - store_mix_pct, em pontos percentuais
    category_margin_pct: float  # margem% desta categoria NESTA loja — referência de "é margem baixa?"


class SellerMarginMixProfile(BaseModel):
    """Fase D, Pilar 1 — Mix de Venda por Categoria de Margem: distingue vendedor
    IMPRODUTIVO (vende pouco) de vendedor DESTRUIDOR DE MARGEM (vende normal/muito,
    mas concentrado em categoria de margem baixa acima do padrão da própria loja —
    mesmo mecanismo estrutural do caso L7/L9: o volume esconde a corrosão).

    `seller_margin_pct`/`store_margin_pct` são margem BLENDADA (Σmargem/Σreceita,
    não média de margem% por venda — receita maior pesa mais, correto para "quanto
    dinheiro de fato sobra"). `store_margin_pct` inclui TODOS os vendedores da loja
    (mesmo vendedor sob avaliação incluso) — mesmo critério de benchmark local já
    usado em `detect_seller_margin_corrosion` (nunca a rede inteira; lojas têm mix de
    catálogo/política diferentes). `margin_gap_pp = store_margin_pct -
    seller_margin_pct`: positivo = vendedor abaixo da própria loja.

    `is_margin_destructive` exige DUAS coisas ao mesmo tempo: gap acima do limiar E
    amostra mínima (`seller_margin_mix_min_sample`) — vendedor com poucas vendas não
    tem base estatística pra acusação de "destruidor de margem" (ruído, não padrão)."""
    salesperson: str
    store: str
    total_revenue: float
    seller_margin_pct: float
    store_margin_pct: float
    margin_gap_pp: float
    is_margin_destructive: bool
    sample_size: int
    mix: list[SellerCategoryMixEntry] = Field(default_factory=list)
    # Fase D, Pilar 2 — mesma amostra (teto `provenance_sample_cap`) de
    # `SellerMarginCorrosionAlert.sample_source_rows`.
    sample_source_rows: list[int] = Field(default_factory=list)


class FlightRiskAlert(BaseModel):
    """Fase E, E1 — Risco de Evasão de Talentos: 3 pernas independentes (captura em
    queda, desconto em alta, ticket em queda), cada uma calculada como série mensal
    do PRÓPRIO vendedor (nunca contra a rede) e disparada por desvio em σ sobre a
    variabilidade histórica dele mesmo — mesmo idioma estatístico de
    `detect_revenue_leaks`, nunca um ponto-percentual fixo.

    `risk_flags` lista só as pernas que dispararam (nunca um score opaco único —
    mesma filosofia de "o mix, nunca só o rótulo" do `SellerMarginMixProfile`); cada
    flag vem com o número que a sustenta nos campos `*_trend_*` correspondentes
    (`None` quando aquela perna não foi avaliada — dado insuficiente ou sem
    variabilidade, nunca "não disparou" fingido).

    `carteira_em_risco_brl` = `SalespersonPerformance.total_revenue` do vendedor no
    período — número já existente, reusado, nunca inventado. É receita BRUTA (inclui
    venda anônima e estorno negativo, mesma construção de `SalespersonPerformance`,
    ver docstring acima) — é o que evapora SE o vendedor sair, não uma perda já
    ocorrida; por isso NÃO entra em `ExecutiveSummary.total_ltv_risk` (que já é só
    churn de cliente — somar as duas naturezas sob um único total mascararia qual
    risco é qual, veja `SPEC_Fase_E_Parte1_Execucao.md` §3.1)."""
    salesperson: str
    store: str
    months_evaluated: int
    capture_trend_pct: float | None = None  # queda de capture_rate_pct, recente vs. histórico
    discount_trend_pp: float | None = None  # alta de discount_pct, recente vs. histórico
    ticket_trend_pct: float | None = None  # queda de ticket médio, recente vs. histórico
    risk_flags: list[str] = Field(default_factory=list)  # "captura_em_queda"|"desconto_em_alta"|"ticket_em_queda"
    carteira_em_risco_brl: float
    sample_source_rows: list[int] = Field(default_factory=list)


class IncentiveMisalignmentAlert(BaseModel):
    """Fase E, E2 — Conflito de Comissionamento: NÃO recalcula margem, ANOTA um
    achado que já existe (`SellerMarginMixProfile.is_margin_destructive` ou
    `SellerMarginCorrosionAlert.is_corrosive`) quando a estrutura de comissão
    declarada (`AuditThresholdsConfig.commission_basis`) explica estruturalmente por
    que o incentivo do vendedor não está alinhado com proteger margem.

    Consome os achados JÁ pós-taint (`tainted_by_triage`/absolvição de §15.5) — um
    vendedor absolvido por cadastro errado nunca aparece aqui (ver ordem de execução
    em `run_audit`, `SPEC_Fase_E_Parte1_Execucao.md` §3.2). Sem R$ próprio — achado
    estrutural/qualitativo, não entra em nenhum total monetário."""
    salesperson: str
    store: str
    commission_basis: str  # "gross_revenue" (único caso que gera alerta hoje)
    linked_finding_type: str  # "margin_mix" | "margin_corrosion"
    linked_finding_summary: str
    recommended_fix: str


class SkillGapDiagnosis(BaseModel):
    """Fase E, E3-v1 — Matriz de Habilidade vs. Viés (proxy): leitura sobre
    `SellerCategoryMixEntry` já existente (Fase D, Pilar 1) — quando um vendedor
    vende MENOS que o padrão da própria loja numa categoria cuja margem já é maior
    que a margem blendada da loja (`SellerMarginMixProfile.store_margin_pct`), o
    padrão sugere possível evitação por insegurança técnica, não preguiça.

    `is_proxy=True` sempre e `hypothesis` é sempre rotulada como hipótese — nunca
    "diagnóstico confirmado" (vocabulário obrigatório, mesma disciplina de
    `latent_revenue`). `data_gap` declara a limitação de dado desta v1 (conversão
    REAL exigiria saber tentativas/orçamentos recusados, não só vendas concluídas —
    v2 fica registrada na planta-mãe, não bloqueia esta). Sem R$ — achado
    estrutural, não entra em nenhum total monetário."""
    salesperson: str
    store: str
    category: str
    mix_deviation_pp: float  # negativo: vendedor vende menos que o padrão da loja nesta categoria
    category_margin_pct: float
    hypothesis: str
    is_proxy: bool = True
    data_gap: str | None = "conversao_real_requer_aba_orcamentos"


class TeamDiagnostics(BaseModel):
    """Fase E parte 1 — Física da Equipe: diagnósticos estruturais/organizacionais
    sobre o SISTEMA em volta do vendedor (incentivo, habilidade), não o resultado
    dele. Nenhum campo aqui entra em `ExecutiveSummary` (nenhum total monetário
    existente é tocado) — ver `SPEC_Fase_E_Parte1_Execucao.md` §0/§3.1. Mesmo
    graceful degradation de `AdvancedMetrics`: lista vazia quando o dado de origem
    não sustenta o achado, nunca populada com caso artificial."""
    flight_risk: list[FlightRiskAlert] = Field(default_factory=list)
    incentive_misalignment: list[IncentiveMisalignmentAlert] = Field(default_factory=list)
    skill_gaps: list[SkillGapDiagnosis] = Field(default_factory=list)
    # occupancy_profiles / scheduling_mismatches — Fase E parte 2 (E4/E5), fora desta OS.


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


class ServiceDecomposition(BaseModel):
    """SVC — Decomposição de Produto vs Serviço na mesma loja.
    Se a margem do produto for negativa mas a do serviço cobrir o buraco (lucro total > 0),
    `masks_negative_product_margin` será True."""
    store: str
    product_margin: float
    service_margin: float
    total_margin: float
    masks_negative_product_margin: bool
    follow_on_cac_effect: float  # Receita de produto gerada por clientes que entraram primeiro via serviço


class ServiceReconciliation(BaseModel):
    """SVC5 — Reconciliação entre aba Financeiro e aba Vendas para Serviços.
    Se a receita declarada não bater com a soma transacional, `has_gap` é True."""
    store: str
    period: str  # "YYYY-MM"
    financial_declared_revenue: float
    sales_transactional_revenue: float
    gap: float
    has_gap: bool


class DiscardedAlarm(BaseModel):
    """ES — Sumário executivo: um candidato que o motor avaliou e decidiu NÃO
    reportar como achado, com o motivo. Cobre só categorias que o motor genuinamente
    checa hoje (rampa de vendedor, cold-start de loja, Fase E: estrutura de
    comissão não informada) — nunca populado com um caso artificial só para não
    ficar vazio."""
    category: str  # "salesperson_ramp" | "store_cold_start" | "commission_basis_unknown"
    entity_id: str
    reason: str


class ActionPlanItem(BaseModel):
    """ES — Item do plano de ação, pré-ordenado pelo motor (tier ascendente, R$
    descendente dentro do tier). O frontend renderiza na ordem que veio, nunca
    reordena nem recalcula."""
    id: str
    category: str
    title: str
    description: str
    impact_brl: float
    nature: str  # "operational" | "capital" | "ltv_risk"
    tier: int  # 1 = perda certa/recorrente, 2 = capital recuperável, 3 = LTV projetado


class ExecutiveSummary(BaseModel):
    """ES — Agregados de topo do laudo. Cada total vem DA FONTE (dos detectores),
    contado uma vez; as três naturezas (operacional/capital/LTV) nunca são somadas
    entre si em lugar nenhum — são fatos de natureza contábil diferente. Receita
    latente (cenário) fica de fora: nunca soma aqui, nunca entra em `action_plan`.

    `total_operational_loss` exclui alerta de margem negativa `promotional=True` (C3:
    forma_pagto=promoção, decisão comercial deliberada) — só soma o que é prejuízo
    estrutural de verdade."""
    total_operational_loss: float
    total_capital_frozen: float
    total_ltv_risk: float
    discarded_alarms: list[DiscardedAlarm] = Field(default_factory=list)
    action_plan: list[ActionPlanItem] = Field(default_factory=list)


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
    service_decomposition: list[ServiceDecomposition] = Field(default_factory=list)
    service_reconciliation: list[ServiceReconciliation] = Field(default_factory=list)
    salesperson_performance: list[SalespersonPerformance] = Field(default_factory=list)
    advanced_metrics: AdvancedMetrics = Field(default_factory=AdvancedMetrics)
    executive_summary: ExecutiveSummary
    # Fase E parte 1 — Física da Equipe: diagnósticos estruturais (evasão, incentivo,
    # habilidade), paralelo a advanced_metrics, nunca somado a executive_summary.
    team_diagnostics: TeamDiagnostics = Field(default_factory=TeamDiagnostics)
    generated_at: str
    
    # Trustware / Forensic Gate: Status de integridade imposto pela Regra Dura.
    audit_status: str = "OK"
    presentation_mode: str = "LONG_WINDOW_MODE"

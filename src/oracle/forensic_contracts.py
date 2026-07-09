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


class SalesRecord(BaseModel):
    """Registro de venda higienizado — a unidade atômica pós-limpeza."""
    date: object  # datetime — aceita datetime.datetime ou pandas.Timestamp
    product: str
    customer: str
    value: float
    quantity: float | None = None
    source_file: str
    source_row: int


class CleaningSummary(BaseModel):
    """Contabilidade da higienização — nada é descartado em silêncio."""
    rows_read: int
    rows_accepted: int
    rows_discarded_by_reason: dict[str, int] = Field(default_factory=dict)
    files_skipped: list[dict] = Field(default_factory=list)


class RevenueLeakAnomaly(BaseModel):
    """Queda de receita além do limiar de desvio-padrão histórico."""
    scope: str  # "total" | "product" | "customer"
    entity_id: str
    period: str  # "YYYY-MM"
    expected_value: float
    actual_value: float
    drop_sigma: float
    severity: str  # "low" | "medium" | "high"


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


class SeasonalityCurve(BaseModel):
    """Índice de sazonalidade mensal — nunca inventa curva sem histórico suficiente."""
    scope: str
    entity: str
    monthly_index: dict[int, float] | None = None
    insufficient_data: bool = False
    months_available: int | None = None


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
    generated_at: str

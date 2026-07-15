"""Contratos Pydantic da Fase C — Gerador de Dashboards.

Cada fronteira de fase (C0→C4) é governada por um contrato versionado.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ==========================================
# Fase C0 — Ingestão + Un-pivot
# ==========================================


class IngestionStrategy(BaseModel):
    """Registra qual estratégia de leitura a C0 usou."""
    primary: str = Field(..., description="Estratégia primária tentada")
    fallback: str = Field(..., description="Estratégia de fallback disponível")
    used: str = Field(..., description="Estratégia efetivamente usada")
    reason: str = Field(..., description="Por que essa estratégia foi escolhida")


class DetectedStructure(BaseModel):
    """Estrutura detectada na tabela de origem."""
    table_kind: str = Field(..., description="flat | wide | pivot_hierarchical")
    hierarchy: dict[str, str] = Field(default_factory=dict, description="parent/child")
    unpivot_source_columns: list[str] = Field(default_factory=list,
        description="Colunas largas que viraram valores de dimensão")
    canonical_dimension_from_columns: Optional[str] = Field(None,
        description="Nome da dimensão criada a partir das colunas largas")
    canonical_measure: Optional[str] = Field(None,
        description="Nome da measure canônica do modelo longo")
    subtotal_rows_detected: int = 0
    grand_total_row: Optional[int] = None


class SourceMapEntry(BaseModel):
    """Proveniência de uma linha do dataset: de qual célula veio cada campo."""
    row_id: int = Field(..., description="row_id correspondente em dataset")
    origin_sheet: str
    origin_cells: dict[str, str] = Field(...,
        description="campo -> referência de célula de origem")


class DiscardedRow(BaseModel):
    """Linha de origem descartada, com motivo auditável."""
    origin_row: int
    reason: str = Field(..., description="grand_total | subtotal | empty | malformed | no_measures")
    raw: list[Any] = Field(..., description="Conteúdo bruto da linha descartada")


class ValidationSummary(BaseModel):
    """Resumo de contabilização de linhas da C0."""
    total_rows_read: int
    source_rows_emitted: int = Field(..., description="Linhas de origem que viraram dataset")
    source_rows_context: int = Field(..., description="Linhas de contexto (pai/cabeçalho)")
    source_rows_discarded: int = Field(..., description="Linhas descartadas")
    dataset_rows_emitted: int = Field(..., description="Linhas no dataset longo (independente)")
    warnings: list[str] = Field(default_factory=list)


class C0Dataset(BaseModel):
    """Artefato da C0: tabela longa limpa + proveniência completa."""
    schema_version: Literal["c0_dataset.v1"] = "c0_dataset.v1"
    source_file: str
    ingestion_strategy: IngestionStrategy
    detected_structure: DetectedStructure
    dataset: list[dict[str, Any]] = Field(..., description="Tabela longa canônica")
    source_map: list[SourceMapEntry]
    discarded_rows: list[DiscardedRow] = Field(default_factory=list)
    validation_summary: ValidationSummary


# ==========================================
# Fase C1 — Modelo Semântico
# ==========================================


class SemanticField(BaseModel):
    """Papel semântico e de negócio de um campo da tabela longa."""
    name: str
    type: str = Field(..., description="string | integer | float | date | category")
    semantic_role: str = Field(...,
        description="entity_id | breakdown_dimension | measure | temporal | label")
    business_role: Optional[str] = Field(None,
        description="Papel de negócio inferido por heurística determinística")
    cardinality: Optional[int] = Field(None, description="Nº de valores distintos")


class SemanticModel(BaseModel):
    """Artefato da C1: papéis semânticos de todos os campos."""
    schema_version: Literal["c1_semantic.v1"] = "c1_semantic.v1"
    primary_dimension: Optional[str] = None
    secondary_dimension: Optional[str] = None
    fields: list[SemanticField]


# ==========================================
# Fase C2 — Motor de Métricas
# ==========================================


class KPI(BaseModel):
    """Indicador com evidência de cálculo completa."""
    metric: str
    label: str
    value: float
    formula: str = Field(..., description="Fórmula sobre o modelo longo")
    numerator: float
    denominator: float
    validation_status: str = Field(..., description="ok | mismatch | undefined")


class AggregationRow(BaseModel):
    """Uma linha de agregação: chave categórica + valor."""
    key: str
    value: float


class Aggregation(BaseModel):
    """Agregação group-by de uma measure por uma dimensão."""
    id: str
    by: str = Field(..., description="Dimensão agrupadora")
    measure: str = Field(..., description="Measure agregada")
    rows: list[AggregationRow]


class Anomaly(BaseModel):
    """Anomalia detectada, com evidência numérica obrigatória."""
    type: str = Field(..., description="concentration | outlier")
    severity: str = Field(..., description="low | medium | high")
    metric: str
    evidence: str = Field(..., description="Evidência numérica textual")


class MetricsReport(BaseModel):
    """Artefato da C2: KPIs + agregações + anomalias."""
    schema_version: Literal["c2_metrics.v1"] = "c2_metrics.v1"
    kpis: list[KPI]
    aggregations: list[Aggregation]
    anomalies: list[Anomaly] = Field(default_factory=list)


# ==========================================
# Fase C3 — Recomendador + DashboardSpec
# ==========================================


class Resolution(BaseModel):
    """Resolução de renderização do dashboard."""
    width: int = 3840
    height: int = 2160


class DataView(BaseModel):
    """Bloco de dados tipado, materializado dentro do DashboardSpec."""
    kind: str = Field(..., description="series | kpi_list")
    columns: list[str]
    rows: list[dict[str, Any]]
    source: dict[str, Any] = Field(default_factory=dict,
        description="Rastro: de qual aggregation/kpi do C2 veio")


class DashboardComponent(BaseModel):
    """Um componente visual do dashboard."""
    id: str
    type: str = Field(..., description="kpi_cards | horizontal_bar | bar_ranking | heatmap | line | stacked_bar")
    data_binding: str = Field(..., description="Chave local: data_views.<nome>")
    analytical_intent: str
    generated_by_rule: str = Field(..., description="id da ChartRule que gerou")


class Layout(BaseModel):
    """Disposição em grade dos componentes."""
    kind: str = Field(..., description="c_level_grid | c_level_grid_dense")
    rows: list[list[str]] = Field(..., description="Grade de component ids")


class NarrativeBlock(BaseModel):
    """Bloco de narrativa executiva (gerado por LLM, opcional)."""
    level: str = Field(..., description="c_level | management | operational")
    text: str


class DashboardSpec(BaseModel):
    """Artefato canônico da Fase C — autocontido. C4 só toca este arquivo."""
    schema_version: Literal["dashboard_spec.v1"] = "dashboard_spec.v1"
    dashboard_id: str
    title: str
    resolution: Resolution
    theme: str
    llm_used: bool = False
    layout: Layout
    data_views: dict[str, DataView] = Field(...,
        description="Dados materializados; C4 resolve binding por lookup local")
    components: list[DashboardComponent]
    narrative: list[NarrativeBlock] = Field(default_factory=list)


class ChartRule(BaseModel):
    """Regra do catálogo de gráficos — carrega IDs estáveis, nunca funções."""
    id: str
    priority: int = Field(..., description="Numérica descendente: maior vence")
    analytical_intent: str
    predicate_id: str = Field(..., description="Chave em PREDICATE_REGISTRY")
    component_type: str
    data_view_builder_id: str = Field(..., description="Chave em DATA_VIEW_BUILDER_REGISTRY")


class DashboardComponentSpec(BaseModel):
    """Par emitido por uma ChartRule: componente + data_view exigido."""
    component: DashboardComponent
    required_data_view: DataView

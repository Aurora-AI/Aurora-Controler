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
    reason: str = Field(..., description="grand_total | subtotal | empty | malformed")
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

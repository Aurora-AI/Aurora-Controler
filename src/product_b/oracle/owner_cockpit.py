"""
ART-COC-001 — Cockpit do Dono
Contrato: ElysianConsult/docs/CATALOGO/registro/artefatos.yaml (ART-COC-001)
Dicionário: ElysianConsult/docs/CATALOGO/render/DICIONARIO_DASHBOARD.md

Princípios e Travas:
- Trava T1: Consome SOMENTE o ExecutiveAuditReport congelado. Zero recálculo, zero acesso à planilha.
- Trava T2 (REG-NUM-001): Indicador sem base de sustentação no arquivo contábil aparece NULO
  com selo SEM_BASE. NUNCA 0.0 falso nem 100% fingido.
- Trava T3 (Pilar 2 / DEC-009): Procedência e fonte de cada KPI declaradas.
- Trava T4 (DEC-009): Superfície estrita com teto de 7 elementos (1 âncora + 6 secundários).
  Validado no nível Pydantic via @model_validator.
- Trava REG-SEV-004: ZERO nomes de vendedores na tela do dono (o score vive apenas no coaching privado).
  Sanitização defensiva de strings interpoladas.
- Indicador-Mãe: Ciclo Médio de Recompra (FOR-BAS-003) — o número que justifica abrir o painel.
"""
from __future__ import annotations

import math
import statistics
from typing import Any
from pydantic import BaseModel, Field, model_validator

from product_b.oracle.forensic_contracts import (
    ExecutiveAuditReport,
    AdvancedMetrics,
    GmroiEntry,
    AttachRateOpportunity,
)


def _sanitize_single_line(text: str) -> str:
    """Remove quebras de linha e caracteres de controle para preservar a integridade visual."""
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").replace("\t", " ").split())


def _sanitize_category_name(cat: str) -> str:
    """Higieniza o nome de categoria de produto evitando injeção acidental de identificadores nominais."""
    cleaned = _sanitize_single_line(cat)
    forbidden_tokens = ["Vendedor", "vendedor", "V-", "salesperson", "venda_", "seller"]
    for token in forbidden_tokens:
        if token in cleaned:
            return "categoria_restringida"
    return cleaned


class CockpitKPI(BaseModel):
    """Representação de um indicador executivo na superfície do Cockpit do Dono."""
    kpi_id: str  # ex: "FOR-BAS-003"
    name: str  # ex: "Ciclo Médio de Recompra"
    symbol: str  # ex: "ciclo"
    value: float | None = None
    unit: str  # "dias", "%", "R$", "índice"
    status_selo: str = "SEM_BASE"  # "CONFIRMADO" | "SEM_BASE"
    meta_direcao: str = "N/A"  # "QUEDA" | "ALTA" | "ESTABILIDADE" | "N/A"
    descricao_fato: str
    source_ref: str | None = None


class OwnerCockpitArtifact(BaseModel):
    """Artefato completo do Cockpit do Dono (ART-COC-001) com teto estrito de 7 elementos."""
    artifact_id: str = "ART-COC-001"
    version: str = "v1.0"
    superficie_teto: int = 7
    
    # 1 Indicador Âncora (Número-Mãe que justifica abrir o painel)
    kpi_ancora: CockpitKPI
    
    # 6 KPIs Secundários (exatamente 6 na superfície)
    kpis_secundarios: list[CockpitKPI] = Field(default_factory=list)
    
    # Métricas de Governança
    total_kpis_ativos: int = 0
    total_kpis_sem_base: int = 0

    @model_validator(mode="after")
    def validate_superficie_e_ancora(self) -> OwnerCockpitArtifact:
        """Validação estrita de integridade estrutural do Cockpit (Trava T4 e Contrato)."""
        if len(self.kpis_secundarios) != 6:
            raise ValueError(
                f"OwnerCockpitArtifact exige exatamente 6 KPIs secundários "
                f"(recebeu {len(self.kpis_secundarios)}), garantindo o teto de 7 elementos na superfície."
            )
        if self.kpi_ancora.kpi_id != "FOR-BAS-003":
            raise ValueError(
                f"O indicador-mãe (âncora) de ART-COC-001 deve ser FOR-BAS-003 (recebeu {self.kpi_ancora.kpi_id})."
            )
        total_kpis = 1 + len(self.kpis_secundarios)
        if (self.total_kpis_ativos + self.total_kpis_sem_base) != total_kpis:
            raise ValueError(
                f"A soma de KPIs ativos ({self.total_kpis_ativos}) e sem base ({self.total_kpis_sem_base}) "
                f"deve ser igual ao total de elementos ({total_kpis})."
            )
        return self


def build_owner_cockpit(report: ExecutiveAuditReport) -> OwnerCockpitArtifact:
    """Constrói o artefato ART-COC-001 a partir de um ExecutiveAuditReport congelado.
    
    Extrai deterministicamente os 7 KPIs canônicos:
    1. FOR-BAS-003 (Âncora): Ciclo médio de recompra (mediana de cadência dos churn findings).
    2. FOR-BAS-010: Taxa de identificação (SEM_BASE se sem campo no motor).
    3. FOR-BAS-009: Taxa de recompra (SEM_BASE se total de clientes únicos indisponível).
    4. FOR-BAS-007: Attach rate por categoria (extraído de attach_rate_opportunities).
    5. FOR-EST-003: GMROI da rede (extraído de report.gmroi ou gmroi_alerts).
    6. FOR-BAS-011: Conversão de pendentes (SEM_BASE - LAC-FOR-063).
    7. FOR-FIN-004: MRR do Clube (SEM_BASE - LAC-FOR-063).
    """
    # 1. FOR-BAS-003 (Âncora: Ciclo Médio de Recompra)
    cadences = [
        float(c.avg_cadence_days)
        for c in report.churn_findings
        if c.avg_cadence_days is not None and math.isfinite(c.avg_cadence_days) and c.avg_cadence_days > 0
    ]
    if cadences:
        ciclo_val = float(statistics.median(cadences))
        kpi_ancora = CockpitKPI(
            kpi_id="FOR-BAS-003",
            name="Ciclo Médio de Recompra da Base",
            symbol="ciclo",
            value=round(ciclo_val, 1),
            unit="dias",
            status_selo="CONFIRMADO",
            meta_direcao="QUEDA",
            descricao_fato=f"Mediana de cadência observada em {len(cadences)} clientes com compras recorrentes",
            source_ref="churn_findings.avg_cadence_days",
        )
    else:
        kpi_ancora = CockpitKPI(
            kpi_id="FOR-BAS-003",
            name="Ciclo Médio de Recompra da Base",
            symbol="ciclo",
            value=None,
            unit="dias",
            status_selo="SEM_BASE",
            meta_direcao="QUEDA",
            descricao_fato="Histórico de recompras insuficiente para cálculo robusto de cadência",
            source_ref="churn_findings",
        )

    # 2. FOR-BAS-010 (Taxa de Identificação de Balcão)
    kpi_ident = CockpitKPI(
        kpi_id="FOR-BAS-010",
        name="Taxa de Identificação de Clientes",
        symbol="tx_ident",
        value=None,
        unit="%",
        status_selo="SEM_BASE",
        meta_direcao="ALTA",
        descricao_fato="Campo não fornecido no relatório contábil sem recálculo fora do motor (LAC-FOR-063)",
        source_ref=None,
    )

    # 3. FOR-BAS-009 (Taxa de Recompra)
    kpi_recompra = CockpitKPI(
        kpi_id="FOR-BAS-009",
        name="Taxa de Recompra da Carteira",
        symbol="tx_recompra",
        value=None,
        unit="%",
        status_selo="SEM_BASE",
        meta_direcao="ALTA",
        descricao_fato="Total de clientes únicos não preservado no relatório congelado (LAC-FOR-063)",
        source_ref=None,
    )

    # 4. FOR-BAS-007 (Attach Rate / Venda Cruzada)
    am = report.advanced_metrics
    attach_opps = am.attach_rate_opportunities if am else []
    if attach_opps:
        att = attach_opps[0]
        att_val = float(att.attach_rate_pct) if math.isfinite(att.attach_rate_pct) else None
        if att_val is not None:
            anc_clean = _sanitize_category_name(att.anchor_category)
            tgt_clean = _sanitize_category_name(att.target_category)
            kpi_attach = CockpitKPI(
                kpi_id="FOR-BAS-007",
                name="Taxa de Venda Cruzada (Attach Rate)",
                symbol="attach_cat",
                value=round(att_val, 1),
                unit="%",
                status_selo="CONFIRMADO",
                meta_direcao="ALTA",
                descricao_fato=f"Conversão {anc_clean} -> {tgt_clean} ({att.eligible_customers} elegíveis)",
                source_ref="advanced_metrics.attach_rate_opportunities[0]",
            )
        else:
            kpi_attach = CockpitKPI(
                kpi_id="FOR-BAS-007",
                name="Taxa de Venda Cruzada (Attach Rate)",
                symbol="attach_cat",
                value=None,
                unit="%",
                status_selo="SEM_BASE",
                meta_direcao="ALTA",
                descricao_fato="Valor de attach rate não finito no relatório congelado",
                source_ref="advanced_metrics.attach_rate_opportunities",
            )
    else:
        kpi_attach = CockpitKPI(
            kpi_id="FOR-BAS-007",
            name="Taxa de Venda Cruzada (Attach Rate)",
            symbol="attach_cat",
            value=None,
            unit="%",
            status_selo="SEM_BASE",
            meta_direcao="ALTA",
            descricao_fato="Nenhuma regra de venda cruzada disparada no período",
            source_ref="advanced_metrics.attach_rate_opportunities",
        )

    # 5. FOR-EST-003 (GMROI — Retorno de Margem sobre Estoque)
    if report.gmroi and len(report.gmroi) > 0:
        tot_margin = sum(g.gross_margin for g in report.gmroi if math.isfinite(g.gross_margin))
        tot_inv = sum(g.avg_inventory_value for g in report.gmroi if math.isfinite(g.avg_inventory_value))
        if tot_inv > 0:
            gmroi_consolidado = tot_margin / tot_inv
            if gmroi_consolidado <= 0:
                fato_gmroi = f"GMROI negativo ou nulo ({gmroi_consolidado:.2f}): margem bruta insuficiente sobre estoque médio"
            else:
                fato_gmroi = f"GMROI consolidado da rede sobre {len(report.gmroi)} categorias de produto"
            kpi_gmroi = CockpitKPI(
                kpi_id="FOR-EST-003",
                name="GMROI (Retorno de Margem sobre Estoque)",
                symbol="GMROI_doc",
                value=round(gmroi_consolidado, 2),
                unit="índice",
                status_selo="CONFIRMADO",
                meta_direcao="ALTA",
                descricao_fato=fato_gmroi,
                source_ref="report.gmroi",
            )
        else:
            kpi_gmroi = CockpitKPI(
                kpi_id="FOR-EST-003",
                name="GMROI (Retorno de Margem sobre Estoque)",
                symbol="GMROI_doc",
                value=None,
                unit="índice",
                status_selo="SEM_BASE",
                meta_direcao="ALTA",
                descricao_fato="Valor de estoque médio zerado ou inválido para cálculo de GMROI",
                source_ref="report.gmroi",
            )
    elif am and am.gmroi_alerts and len(am.gmroi_alerts) > 0:
        valid_gmrois = [
            float(g.gmroi)
            for g in am.gmroi_alerts
            if g.gmroi is not None and math.isfinite(g.gmroi) and g.gmroi > 0
        ]
        if valid_gmrois:
            kpi_gmroi = CockpitKPI(
                kpi_id="FOR-EST-003",
                name="GMROI (Retorno de Margem sobre Estoque)",
                symbol="GMROI_doc",
                value=round(statistics.median(valid_gmrois), 2),
                unit="índice",
                status_selo="CONFIRMADO",
                meta_direcao="ALTA",
                descricao_fato=f"Mediana de GMROI calculada sobre {len(valid_gmrois)} SKUs monitorados",
                source_ref="advanced_metrics.gmroi_alerts",
            )
        else:
            kpi_gmroi = CockpitKPI(
                kpi_id="FOR-EST-003",
                name="GMROI (Retorno de Margem sobre Estoque)",
                symbol="GMROI_doc",
                value=None,
                unit="índice",
                status_selo="SEM_BASE",
                meta_direcao="ALTA",
                descricao_fato="Valores de GMROI ausentes ou não finitos",
                source_ref="advanced_metrics.gmroi_alerts",
            )
    else:
        kpi_gmroi = CockpitKPI(
            kpi_id="FOR-EST-003",
            name="GMROI (Retorno de Margem sobre Estoque)",
            symbol="GMROI_doc",
            value=None,
            unit="índice",
            status_selo="SEM_BASE",
            meta_direcao="ALTA",
            descricao_fato="Sem dados de estoque/custo suficientes para medição de GMROI",
            source_ref="report.gmroi",
        )

    # 6. FOR-BAS-011 (Conversão de Pendentes / Orçamentos)
    kpi_pendentes = CockpitKPI(
        kpi_id="FOR-BAS-011",
        name="Conversão de Orçamentos Pendentes",
        symbol="conv_pendentes",
        value=None,
        unit="%",
        status_selo="SEM_BASE",
        meta_direcao="ALTA",
        descricao_fato="Tabela de orçamentos e pendências inexistente no arquivo (LAC-FOR-063)",
        source_ref=None,
    )

    # 7. FOR-FIN-004 (MRR do Clube de Assinatura)
    kpi_mrr = CockpitKPI(
        kpi_id="FOR-FIN-004",
        name="Receita Recorrente Mensal (MRR do Clube)",
        symbol="MRR",
        value=None,
        unit="R$",
        status_selo="SEM_BASE",
        meta_direcao="ALTA",
        descricao_fato="Tabela de planos e assinaturas recorrentes inexistente no arquivo (LAC-FOR-063)",
        source_ref=None,
    )

    secundarios = [kpi_ident, kpi_recompra, kpi_attach, kpi_gmroi, kpi_pendentes, kpi_mrr]
    
    total_ativos = (1 if kpi_ancora.status_selo == "CONFIRMADO" else 0) + sum(
        1 for k in secundarios if k.status_selo == "CONFIRMADO"
    )
    total_sem_base = (1 if kpi_ancora.status_selo == "SEM_BASE" else 0) + sum(
        1 for k in secundarios if k.status_selo == "SEM_BASE"
    )

    return OwnerCockpitArtifact(
        kpi_ancora=kpi_ancora,
        kpis_secundarios=secundarios,
        total_kpis_ativos=total_ativos,
        total_kpis_sem_base=total_sem_base,
    )


def render_owner_cockpit_text(artifact: OwnerCockpitArtifact) -> str:
    """Renderiza a visão textual do Cockpit do Dono (ART-COC-001).
    
    Superfície estrita de 7 elementos.
    REG-SEV-004: Zero nomes de vendedores exibidos.
    REG-NUM-001: Sem base exibe [SEM_BASE], nunca 0.0 nem 100%.
    """
    anc = artifact.kpi_ancora
    if anc.status_selo == "CONFIRMADO" and anc.value is not None:
        anc_str = f"{anc.value:,.1f} {anc.unit}"
    else:
        anc_str = "[SEM_BASE]"
        
    lines = [
        f"=========================================================================================================",
        f"                          {artifact.artifact_id} · COCKPIT DO DONO ({artifact.version})",
        f"=========================================================================================================",
        f"  INDICADOR-MÃE (ÂNCORA): {anc.name.upper()} ({anc.symbol})",
        f"  VALOR CONSOLIDADO:      {anc_str}  [Meta: {anc.meta_direcao}]  Selo: {anc.status_selo}",
        f"  DIAGNÓSTICO FATO:       {anc.descricao_fato}",
        f"---------------------------------------------------------------------------------------------------------",
        f"  GOVERNANÇA: {artifact.total_kpis_ativos} KPIs Confirmados | {artifact.total_kpis_sem_base} KPIs Quarentenados em SEM_BASE (Teto: {artifact.superficie_teto} elementos)",
        f"  REG-SEV-004: Painel consolidado da rede (zero identificação individual) | REG-NUM-001: Quarentena estrita",
        f"=========================================================================================================",
        f"{'#':<4} {'KPI ID':<12} {'SÍMBOLO':<15} {'VALOR CONSOLIDADO':<22} {'META':<10} {'STATUS / SELO':<15} {'DETALHE / FATO':<35}",
        f"---------------------------------------------------------------------------------------------------------",
    ]

    for idx, k in enumerate(artifact.kpis_secundarios, start=2):
        if k.status_selo == "CONFIRMADO" and k.value is not None:
            if k.unit == "R$":
                val_str = f"R$ {k.value:,.2f}"
            elif k.unit == "%":
                val_str = f"{k.value:,.1f}%"
            elif k.unit == "dias":
                val_str = f"{k.value:,.1f} dias"
            else:
                val_str = f"{k.value:,.2f} ({k.unit})"
        else:
            val_str = "[SEM_BASE]"

        clean_id = _sanitize_single_line(k.kpi_id)
        clean_sym = _sanitize_single_line(k.symbol)
        clean_meta = _sanitize_single_line(k.meta_direcao)
        clean_selo = _sanitize_single_line(k.status_selo)
        clean_fato = _sanitize_single_line(k.descricao_fato)

        lines.append(
            f"{idx:<4} {clean_id:<12} {clean_sym:<15} {val_str:<22} {clean_meta:<10} {clean_selo:<15} {clean_fato:<35}"
        )

    lines.append(f"=========================================================================================================")
    return "\n".join(lines)

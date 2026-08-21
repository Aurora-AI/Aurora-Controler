"""
ART-FIL-002 — Fila de Auditoria Manual
Contrato: ElysianConsult/docs/CATALOGO/registro/artefatos.yaml (ART-FIL-002)
Especificação: SPEC_Fase_C_Fila_Auditoria_Manual.md

Princípios e Travas:
- Trava T1: Consome exclusivamente o bloco `discrepancy_triage` de um `ExecutiveAuditReport` congelado.
  Zero recálculo, zero acesso a planilhas, zero chamada a LLM.
- Trava T2 (REG-NUM-001): Degeneração matemática ou campos ausentes produzem None/indicadores
  seguros sem crash e sem contaminação estatística.
- Trava T3 (Pilar 2 / DEC-009): 100% dos itens preservam `source_rows` mapeando de volta às linhas de venda.
- Trava T4 (DEC-009): Superfície mínima (teto_elementos: 1) — número âncora de pendentes + tabela de resolução rápida.
- Trava T6: Item pendente NUNCA vira fato contábil ou financeiro — perda só entra em totais se
  `below_cost_confirmed=True` (veredito humano ou auto já concluído).
- Princípio Dimensionador: Fila manual recebe apenas o RESÍDUO não classificável (<10% dos disparos).
"""
from __future__ import annotations

import math
from typing import Any
from pydantic import BaseModel, Field

from product_b.oracle.forensic_contracts import (
    ExecutiveAuditReport,
    DiscrepancyTriage,
    DiscrepancyTriageItem,
    DiscrepancyEvidence,
)

# Mapeamento oficial de evidências técnicas para linguagem humana (§3.2 SPEC Fase C)
_TRADUCAO_EVIDENCIA = (
    ("cost_diverges_from_nf", "custo da venda diverge da NF"),
    ("store_systemic_pattern", "padrão repetido por outros vendedores da loja"),
    ("below_cost", "preço praticado abaixo do custo"),
    ("sku_in_dead_stock", "SKU está no estoque parado"),
    ("is_promo_flagged", "venda registrada com forma de pagamento de promoção"),
)


def _sanitize_single_line(text: str) -> str:
    """Remove quebras de linha e caracteres de controle para preservar a integridade visual da tabela."""
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").replace("\t", " ").split())


class ManualAuditQueueItem(BaseModel):
    """Item da Fila de Auditoria Manual (ART-FIL-002).
    Representa uma transação/agrupamento com discrepância aguardando veredito ou pré-classificada."""
    id: str  # ex: "DTQ-0001"
    sku: str
    sku_description: str | None = None
    store: str
    salesperson: str
    
    # Preços e custos da linha / catálogo / NF
    practiced_price: float
    list_price: float | None = None
    entry_cost: float | None = None
    nf_cost: float | None = None
    discount_over_list_pct: float | None = None
    
    # Perda monetária calculada pelo motor na linha
    below_cost_loss_brl: float | None = None
    
    # Trava T6: Flag de confirmação (sempre False para pendentes)
    below_cost_confirmed: bool = False
    
    # Evidências traduzidas para tomada de decisão rápida (~30s)
    evidencias: list[str] = Field(default_factory=list)
    
    # Estado da triagem
    status: str  # "pending_manual_review" | "auto_classified"
    verdict: str | None = None  # None se pendente
    
    # Trava T3 / Pilar 2: Chaves de rastreabilidade até as linhas de Vendas
    source_rows: list[int] = Field(default_factory=list)


class ManualAuditQueueArtifact(BaseModel):
    """Artefato completo da Fila de Auditoria Manual (ART-FIL-002)."""
    artifact_id: str = "ART-FIL-002"
    version: str = "v1.0"
    superficie_teto: int = 1
    
    # Número Âncora de Superfície
    total_disparos: int = 0
    total_auto_classificados: int = 0
    total_pendentes: int = 0
    
    # Princípio Dimensionador (<10% de resíduo)
    taxa_residuo_pct: float = 0.0
    alerta_dimensionamento: bool = False
    teto_residuo_max_pct: float = 10.0
    
    # Listas particionadas
    itens_pendentes: list[ManualAuditQueueItem] = Field(default_factory=list)
    itens_auto_classificados: list[ManualAuditQueueItem] = Field(default_factory=list)


def _traduzir_evidencias_vetor(ev: DiscrepancyEvidence | dict[str, Any] | None) -> list[str]:
    """Traduz o vetor de flags booleanas de evidência em frases descritivas curtas."""
    if ev is None:
        return []
    if isinstance(ev, BaseModel):
        ev_dict = ev.model_dump()
    elif isinstance(ev, dict):
        ev_dict = ev
    else:
        return []
    return [frase for chave, frase in _TRADUCAO_EVIDENCIA if ev_dict.get(chave)]


def build_manual_audit_queue(report: ExecutiveAuditReport) -> ManualAuditQueueArtifact:
    """Constrói o artefato ART-FIL-002 a partir de um ExecutiveAuditReport congelado.
    
    Aplica:
    1. Consumo puro do bloco `report.advanced_metrics.discrepancy_triage`.
    2. Dimensionamento da taxa de resíduo (`total_pendentes / total_disparos`).
       Gate de divisão por zero: se `total_disparos <= 0`, taxa é 0.0%.
    3. Trava T6: itens pendentes têm `below_cost_confirmed=False` e `verdict=None`.
    4. Trava T3: Preservação de `source_rows` em 100% dos itens.
    """
    am = report.advanced_metrics
    dt: DiscrepancyTriage | None = am.discrepancy_triage if am else None
    
    if dt is None:
        return ManualAuditQueueArtifact(
            total_disparos=0,
            total_auto_classificados=0,
            total_pendentes=0,
            taxa_residuo_pct=0.0,
            alerta_dimensionamento=False,
            itens_pendentes=[],
            itens_auto_classificados=[],
        )
    
    def _converter_item(i: DiscrepancyTriageItem) -> ManualAuditQueueItem:
        return ManualAuditQueueItem(
            id=i.id,
            sku=i.sku,
            sku_description=i.sku_description,
            store=i.store,
            salesperson=i.salesperson,
            practiced_price=float(i.practiced_price),
            list_price=float(i.list_price) if i.list_price is not None and math.isfinite(i.list_price) else None,
            entry_cost=float(i.entry_cost) if i.entry_cost is not None and math.isfinite(i.entry_cost) else None,
            nf_cost=float(i.nf_cost) if i.nf_cost is not None and math.isfinite(i.nf_cost) else None,
            discount_over_list_pct=float(i.discount_over_list_pct) if i.discount_over_list_pct is not None and math.isfinite(i.discount_over_list_pct) else None,
            below_cost_loss_brl=float(i.below_cost_loss_brl) if i.below_cost_loss_brl is not None and math.isfinite(i.below_cost_loss_brl) else None,
            # Trava T6: Se status for pendente, confirmação é estritamente False
            below_cost_confirmed=bool(i.below_cost_confirmed and i.status != "pending_manual_review"),
            evidencias=_traduzir_evidencias_vetor(i.evidence),
            status=i.status,
            verdict=i.verdict if i.status != "pending_manual_review" else None,
            source_rows=list(i.source_rows),
        )
    
    pendentes = [_converter_item(it) for it in dt.manual_queue]
    auto = [_converter_item(it) for it in dt.auto_classified]
    
    total_disp = dt.triggered_count
    total_pend = len(pendentes)
    total_auto = len(auto)
    
    # Gate de divisão por zero:
    if total_disp > 0:
        taxa_res = (total_pend / total_disp) * 100.0
    else:
        taxa_res = 0.0
        
    alerta_dim = taxa_res > 10.0
    
    return ManualAuditQueueArtifact(
        total_disparos=total_disp,
        total_auto_classificados=total_auto,
        total_pendentes=total_pend,
        taxa_residuo_pct=taxa_res,
        alerta_dimensionamento=alerta_dim,
        itens_pendentes=pendentes,
        itens_auto_classificados=auto,
    )


def render_manual_audit_queue_text(artifact: ManualAuditQueueArtifact) -> str:
    """Renderiza a superfície mínima (T4: 1 elemento) da Fila de Auditoria Manual.
    
    Número Âncora: 'X itens aguardam veredito'
    Tabela com evidências cruzadas para resolução em ~30s por item.
    """
    alerta_str = " [ALERTA: RESÍDUO > 10%]" if artifact.alerta_dimensionamento else " [GOVERNANÇA OK]"
    lines = [
        f"=== {artifact.artifact_id} · Fila de Auditoria Manual ({artifact.version}) ===",
        f"Número Âncora: {artifact.total_pendentes} itens aguardando veredito humano",
        f"Total Disparos: {artifact.total_disparos} | Auto-classificados: {artifact.total_auto_classificados} | Resíduo: {artifact.taxa_residuo_pct:.2f}%{alerta_str}",
        f"Princípio Dimensionador: Fila manual recebe o resíduo não classificável (teto: {artifact.teto_residuo_max_pct:.1f}%).",
        "-" * 105,
        f"{'#':<4} {'ID':<10} {'LOJA':<8} {'VEND.':<8} {'SKU':<12} {'PRAT.':<10} {'TABELA':<10} {'NF CUSTO':<10} {'EVIDÊNCIAS':<35}",
        "-" * 105,
    ]
    
    if not artifact.itens_pendentes:
        lines.append("NENHUM ITEM PENDENTE DE AUDITORIA MANUAL (Fila limpa — 100% resolvido automaticamente)")
    else:
        for idx, item in enumerate(artifact.itens_pendentes, start=1):
            prat_str = f"R$ {item.practiced_price:,.2f}"
            tab_str = f"R$ {item.list_price:,.2f}" if item.list_price is not None else "[S/TAB]"
            nf_str = f"R$ {item.nf_cost:,.2f}" if item.nf_cost is not None else "[S/NF]"
            ev_str = "; ".join(item.evidencias) if item.evidencias else "Sem evidência conclusiva"
            
            clean_id = _sanitize_single_line(item.id)
            clean_store = _sanitize_single_line(item.store)
            clean_vend = _sanitize_single_line(item.salesperson)
            clean_sku = _sanitize_single_line(item.sku)
            clean_ev = _sanitize_single_line(ev_str)
            
            lines.append(
                f"{idx:<4} {clean_id:<10} {clean_store:<8} {clean_vend:<8} {clean_sku:<12} {prat_str:<10} {tab_str:<10} {nf_str:<10} {clean_ev:<35}"
            )
            
    return "\n".join(lines)

"""
ART-FIL-001 — Fila de Resgate Diária (v1 Reduzida)
Contrato: ElysianConsult/docs/CATALOGO/registro/artefatos.yaml (ART-FIL-001)

Trava T1: Este módulo é um formatador determinístico. Ele consome exclusivamente
o `ExecutiveAuditReport` congelado do motor EXRS (commercial_auditor.py). Zero
recálculo, zero acesso a planilhas, zero chamada a LLM.

Trava T2 (REG-NUM-001): Denominador nulo/inválido (ciclo <= 0 ou dias ausentes)
produz NULO com selo "SEM_BASE", ficando fora da ordenação da fila ativa (nunca 0
ou infinito no fim).

Trava T3: Todo item carrega `source_rows` até a linha original de venda.

Trava T4: Superfície mínima (teto_elementos: 1) — entrega a lista de resgate sem
dashboards acessórios.

Declaração de Desvio de Escopo (v1):
O elemento completo de ART-FIL-001 é "cliente · o que oferecer · por que agora".
A v1 reduzida entrega "cliente" e "por que agora" (silêncio ÷ ciclo /
recuperabilidade). A coluna "o que oferecer" (cross-sell) está deliberadamente fora
do escopo v1 por depender de FOR-BAS-007 (CONFLITANTE, LAC-FOR-060) e FOR-BAS-008
(LAC-FOR-061 — conversão esperada sem origem declarada).

Canonicidade de FOR-BAS-006:
Status: CANDIDATO | Confiança: MEDIA | Procedência: indireta (reconstruída pelo nome do campo)
"""
from __future__ import annotations

from typing import Any
import math
from pydantic import BaseModel, Field

from product_b.oracle.forensic_contracts import ExecutiveAuditReport, ChurnFinding


class RescueQueueItem(BaseModel):
    """Item da Fila de Resgate Diária (ART-FIL-001).
    Representa um cliente com churn detectado e sua recuperabilidade."""
    customer_id: str
    last_purchase_date: str  # "YYYY-MM-DD"
    days_since_last: int
    avg_cadence_days: float | None = None
    
    # FOR-BAS-006: status_canonico=CANDIDATO, confianca=MEDIA
    # silence_to_cycle_ratio = dias_desde_ultima_compra / cadencia_media
    silence_to_cycle_ratio: float | None = None
    
    # REG-NUM-001: Selo de estado para casos degenerados (ciclo <= 0 ou ausente)
    status_selo: str | None = None  # None para OK, "SEM_BASE" quando indefinido
    
    historical_value: float
    
    # FOR-BAS-002: Segmento RFM derivado
    rfm_segment: str = "Em Risco"
    
    # T3 / Pilar 2: Chaves de rastreabilidade (linhas de origem no arquivo)
    source_rows: list[int] = Field(default_factory=list)


class RescueQueueArtifact(BaseModel):
    """Artefato completo da Fila de Resgate Diária (ART-FIL-001 v1 reduzida)."""
    artifact_id: str = "ART-FIL-001"
    version: str = "v1-reduzida"
    superficie_teto: int = 1
    
    # Declaração formal de desvio de escopo v1 vs artefatos.yaml
    desvio_escopo_declarado: str = (
        "Superfície parcial: entrega 'cliente' e 'por que agora' (recuperabilidade). "
        "Coluna 'o que oferecer' (cross-sell) omitida por dependência de FOR-BAS-007 "
        "(CONFLITANTE, LAC-FOR-060) e FOR-BAS-008 (LAC-FOR-061)."
    )
    
    total_ativos: int = 0
    total_sem_base: int = 0
    
    # Fila ativa: ordenada por recuperabilidade (FOR-BAS-006) ASC, desempate por -historical_value
    itens_ativos: list[RescueQueueItem] = Field(default_factory=list)
    
    # Itens excluídos da fila ativa por REG-NUM-001 (ciclo <= 0 ou sem base)
    itens_sem_base: list[RescueQueueItem] = Field(default_factory=list)


def _is_valid_positive_finite(val: Any) -> bool:
    """True apenas se o valor for um número real finito e estritamente positivo.
    Rejeita: None, NaN, inf, -inf, 0, valores negativos e tipos não-numéricos."""
    if val is None or not isinstance(val, (int, float)):
        return False
    return math.isfinite(val) and val > 0


def build_rescue_queue(report: ExecutiveAuditReport) -> RescueQueueArtifact:
    """Constrói o artefato ART-FIL-001 a partir de um ExecutiveAuditReport congelado.
    
    Aplica:
    1. Filtro de pseudo-entidades (já garantido pelo motor).
    2. Identificação de segmento RFM a partir dos rfm_champions do relatório.
    3. Trava T1 (Zero Recálculo): O formatador lê estritamente `finding.silence_to_cycle_ratio`
       do relatório congelado. Proibido calcular `days_since_last / avg_cadence_days` aqui.
    4. Trava T2 (REG-NUM-001): Se `cadence` ou `silence_to_cycle_ratio` forem ausentes,
       não-finitos (NaN/inf) ou <= 0, o item recebe `status_selo="SEM_BASE"`,
       `silence_to_cycle_ratio=None` e é isolado em `itens_sem_base` fora do ranking ativo.
    5. Ordenação ativa por recuperabilidade (`silence_to_cycle_ratio` ASC, desempate por `-historical_value`).
    """
    champions_set = {champ.customer_id for champ in report.rfm_champions}
    
    ativos: list[RescueQueueItem] = []
    sem_base: list[RescueQueueItem] = []
    
    for finding in report.churn_findings:
        cadence = finding.avg_cadence_days
        days_silent = finding.days_since_last
        ratio = finding.silence_to_cycle_ratio
        
        # Mapeamento RFM básico disponível no report
        rfm_label = "Campeão (555)" if finding.customer_id in champions_set else "Em Risco / Churn"
        
        # Gate REG-NUM-001 + Trava T1 (Zero Recálculo):
        # Ambos cadence e ratio devem ter sido emitidos válidos pelo motor.
        # Se qualquer um for inválido/não-finito/<=0, quarentena imediata em SEM_BASE.
        if not _is_valid_positive_finite(cadence) or not _is_valid_positive_finite(ratio):
            item = RescueQueueItem(
                customer_id=finding.customer_id,
                last_purchase_date=finding.last_purchase,
                days_since_last=days_silent,
                avg_cadence_days=float(cadence) if _is_valid_positive_finite(cadence) else None,
                silence_to_cycle_ratio=None,
                status_selo="SEM_BASE",
                historical_value=finding.historical_annual_value,
                rfm_segment=rfm_label,
                source_rows=list(finding.source_rows),
            )
            sem_base.append(item)
        else:
            # Trava T1: Consumo fiel e exclusivo do valor congelado emitido pelo motor
            item = RescueQueueItem(
                customer_id=finding.customer_id,
                last_purchase_date=finding.last_purchase,
                days_since_last=days_silent,
                avg_cadence_days=float(cadence),
                silence_to_cycle_ratio=float(ratio),
                status_selo=None,
                historical_value=finding.historical_annual_value,
                rfm_segment=rfm_label,
                source_rows=list(finding.source_rows),
            )
            ativos.append(item)
    
    # Ordenação da fila ativa: mais quente primeiro (menor ratio), desempate por maior valor histórico
    ativos_ordenados = sorted(
        ativos,
        key=lambda item: (
            item.silence_to_cycle_ratio if item.silence_to_cycle_ratio is not None else float("inf"),
            -item.historical_value,
        ),
    )
    
    return RescueQueueArtifact(
        total_ativos=len(ativos_ordenados),
        total_sem_base=len(sem_base),
        itens_ativos=ativos_ordenados,
        itens_sem_base=sem_base,
    )


def _sanitize_single_line(text: str) -> str:
    """Remove quebras de linha e caracteres de controle para preservar a integridade visual da superfície."""
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").replace("\t", " ").split())


def render_rescue_queue_text(artifact: RescueQueueArtifact) -> str:
    """Renderiza a superfície mínima (T4: 1 elemento) da Fila de Resgate."""
    lines = [
        f"=== {artifact.artifact_id} · Fila de Resgate Diária ({artifact.version}) ===",
        f"Contatos Ativos: {artifact.total_ativos} | Excluídos (SEM_BASE): {artifact.total_sem_base}",
        f"Ordenação: Recuperabilidade (silêncio ÷ ciclo) [FOR-BAS-006, CANDIDATO]",
        f"Nota de Escopo: {artifact.desvio_escopo_declarado}",
        "-" * 80,
        f"{'#':<4} {'CLIENTE':<15} {'ÚLT. COMPRA':<12} {'SILÊNCIO/CICLO':<16} {'VALOR HIST.':<14} {'RFM':<15}",
        "-" * 80,
    ]
    
    for idx, item in enumerate(artifact.itens_ativos, start=1):
        ratio_str = f"{item.silence_to_cycle_ratio:.2f}x" if item.silence_to_cycle_ratio is not None else "[SEM_BASE]"
        val_str = f"R$ {item.historical_value:,.2f}"
        clean_cid = _sanitize_single_line(item.customer_id)
        lines.append(
            f"{idx:<4} {clean_cid:<15} {item.last_purchase_date:<12} {ratio_str:<16} {val_str:<14} {item.rfm_segment:<15}"
        )
    
    if artifact.itens_sem_base:
        lines.append("-" * 80)
        lines.append("ITENS EXCLUÍDOS DA FILA ATIVA (REG-NUM-001: Sem Base Estatística):")
        for item in artifact.itens_sem_base:
            clean_cid = _sanitize_single_line(item.customer_id)
            lines.append(
                f"[*] {clean_cid:<15} Última: {item.last_purchase_date} | Selo: {item.status_selo} | R$ {item.historical_value:,.2f}"
            )
            
    return "\n".join(lines)

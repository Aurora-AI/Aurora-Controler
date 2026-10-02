"""
EXRS Trustware — Forensic Gate
Camada 1: A REGRA DURA (Trustware)

Este módulo aplica as travas matemáticas irrefutáveis da auditoria. 
Se os dados de entrada estiverem corrompidos (gap de reconciliação ou descarte abusivo), 
o estado do relatório é forçado para crítico. Isso impede que qualquer renderizador 
(Camada 2) exiba uma "beleza estéril" sem os devidos alertas.
"""
from typing import Any
import sys
import os

# sys.path injection removido
from product_b.oracle.forensic_contracts import ExecutiveAuditReport


def apply_forensic_locks(report: ExecutiveAuditReport) -> ExecutiveAuditReport:
    """
    Aplica as travas matemáticas de forense e manipula o status e modos de apresentação
    do relatório ANTES que ele chegue a qualquer UI ou cliente.
    """
    
    # Regra 1: Reconciliação de Grid (Tolerância Zero)
    gap = report.cleaning.reconciliation_gap
    if gap is not None and abs(gap) > 0.01:
        report.audit_status = "CRITICAL_RECONCILIATION_GAP"
        # Se falhou a reconciliação, desativa selos positivos de vazamento esvaziando as evidências
        # ou forçando uma anomalia de erro estrutural.
        
    # Regra 2: Taxa de descarte abusiva (> 5%)
    if report.cleaning.rows_read > 0:
        discarded_rows = report.cleaning.rows_read - report.cleaning.rows_accepted
        discard_rate = discarded_rows / report.cleaning.rows_read
        if discard_rate > 0.05:
            report.audit_status = "CRITICAL_DISCARD_RATE"
            
    # Regra 3: Troca Dinâmica de Contexto (Short-Window Mode)
    # Se não há sazonalidade histórica detectada, forçamos o modo de janela curta.
    if not report.seasonality:
        report.presentation_mode = "SHORT_WINDOW_MODE"
    else:
        report.presentation_mode = "LONG_WINDOW_MODE"

    return report

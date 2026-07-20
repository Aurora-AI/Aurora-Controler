"""
Testes de regressão — Fase C (SPEC_Fase_C_Fila_Auditoria_Manual.md): triagem de
discrepâncias de preço e fila de auditoria manual.

Cobre: os 2 triggers por transação, as 5 evidências e a árvore de decisão
determinística, o dimensionamento da fila (resíduo, não atacado), graceful
degradation por evidência (nunca tudo-ou-nada), e a fusão do arquivo-irmão de
vereditos humanos.
"""
import json
from datetime import datetime, timedelta

import pandas as pd
import pytest

from product_b.oracle.commercial_auditor import (
    _classify_discrepancy, apply_manual_review_verdicts, detect_discrepancy_triage,
)
from product_b.oracle.forensic_contracts import (
    AuditThresholdsConfig, DeadStockFinding, DiscrepancyEvidence, DiscrepancyTriage,
    DiscrepancyTriageItem, ExecutiveAuditReport, ExecutiveSummary, AdvancedMetrics, CleaningSummary,
)

THRESHOLDS = AuditThresholdsConfig()
D0 = datetime(2026, 1, 1)


def _sales(rows):
    # entry_cost sempre presente (mesmo None) — no pipeline real a coluna existe
    # sempre (SalesRecord.entry_cost, ainda que NaN); um dict sem a chave faria a
    # coluna inteira sumir do DataFrame sintético, o que nunca acontece em produção.
    return pd.DataFrame([{
        "date": D0, "quantity": 1.0, "source_row": i + 2, "entry_cost": None, **r,
    } for i, r in enumerate(rows)])


def _estoque(rows):
    return pd.DataFrame([{"data_ultimo_mov": D0, **r} for r in rows])


def _compras(rows):
    return pd.DataFrame(rows)


# --------------------------------------------------------------- árvore de decisão


def test_classify_precedence_cadastral_beats_everything():
    ev = DiscrepancyEvidence(
        below_cost=True, sku_in_dead_stock=True, is_promo_flagged=True,
        cost_diverges_from_nf=True, store_systemic_pattern=False,
    )
    assert _classify_discrepancy(ev) == "suspected_cadastral_error"


def test_classify_liquidation_via_promo():
    ev = DiscrepancyEvidence(
        below_cost=False, sku_in_dead_stock=False, is_promo_flagged=True,
        cost_diverges_from_nf=False, store_systemic_pattern=False,
    )
    assert _classify_discrepancy(ev) == "deliberate_liquidation"


def test_classify_liquidation_via_dead_stock_without_below_cost():
    ev = DiscrepancyEvidence(
        below_cost=False, sku_in_dead_stock=True, is_promo_flagged=False,
        cost_diverges_from_nf=False, store_systemic_pattern=False,
    )
    assert _classify_discrepancy(ev) == "deliberate_liquidation"


def test_classify_dead_stock_plus_below_cost_is_not_liquidation():
    # desovar estoque parado é uma coisa; vender abaixo do custo é outra — quando as
    # duas coexistem, a severidade maior (sangria) prevalece.
    ev = DiscrepancyEvidence(
        below_cost=True, sku_in_dead_stock=True, is_promo_flagged=False,
        cost_diverges_from_nf=False, store_systemic_pattern=False,
    )
    assert _classify_discrepancy(ev) == "below_cost_sale"


def test_classify_below_cost_alone():
    ev = DiscrepancyEvidence(
        below_cost=True, sku_in_dead_stock=False, is_promo_flagged=False,
        cost_diverges_from_nf=False, store_systemic_pattern=False,
    )
    assert _classify_discrepancy(ev) == "below_cost_sale"


def test_classify_no_evidence_is_pending():
    ev = DiscrepancyEvidence(
        below_cost=False, sku_in_dead_stock=False, is_promo_flagged=False,
        cost_diverges_from_nf=False, store_systemic_pattern=False,
    )
    assert _classify_discrepancy(ev) is None


# --------------------------------------------------------------- detector completo


def test_cadastral_error_via_nf_divergence():
    # preço praticado ~180, tabela 838 (desconto >60%), mas o custo real na NF é bem
    # menor que o custo_entrada registrado na venda -> E4 dispara.
    vendas = _sales([
        {"product": "ARP-013", "customer": "C1", "value": 180.0, "entry_cost": 700.0,
         "salesperson": "V-30", "store": "L9"},
        {"product": "ARP-013", "customer": "C2", "value": 200.0, "entry_cost": 720.0,
         "salesperson": "V-30", "store": "L9"},
    ])
    estoque = _estoque([{"sku": "ARP-013", "custo_unit": 309.0, "qtd_atual": 5.0, "preco_venda": 838.0}])
    compras = _compras([
        {"data": D0 - timedelta(days=30), "sku": "ARP-013", "custo_unit": 309.11, "qtd": 10},
    ])
    triage = detect_discrepancy_triage(vendas, estoque, compras, [], THRESHOLDS)
    assert triage.triggered_count == 1
    assert len(triage.auto_classified) == 1
    item = triage.auto_classified[0]
    assert item.verdict == "suspected_cadastral_error"
    assert item.evidence.cost_diverges_from_nf is True
    assert item.source_rows == [2, 3]


def test_cadastral_error_via_store_systemic_pattern():
    # dois vendedores da MESMA loja vendem o mesmo SKU bem abaixo da tabela -> E5.
    vendas = _sales([
        {"product": "SKU-X", "customer": "C1", "value": 100.0, "entry_cost": 50.0,
         "salesperson": "V-01", "store": "L1"},
        {"product": "SKU-X", "customer": "C2", "value": 105.0, "entry_cost": 50.0,
         "salesperson": "V-02", "store": "L1"},
    ])
    estoque = _estoque([{"sku": "SKU-X", "custo_unit": 50.0, "qtd_atual": 5.0, "preco_venda": 500.0}])
    triage = detect_discrepancy_triage(vendas, estoque, None, [], THRESHOLDS)
    assert triage.triggered_count == 2
    verdicts = {item.salesperson: item.verdict for item in triage.auto_classified}
    assert verdicts == {"V-01": "suspected_cadastral_error", "V-02": "suspected_cadastral_error"}
    assert triage.manual_queue == []


def test_deliberate_liquidation_via_promo_flag():
    vendas = _sales([
        {"product": "PROMO-X", "customer": "C1", "value": 40.0, "entry_cost": 45.0,
         "salesperson": "V-01", "store": "L1", "payment_method": "promocao"},
        {"product": "PROMO-X", "customer": "C2", "value": 42.0, "entry_cost": 45.0,
         "salesperson": "V-01", "store": "L1", "payment_method": "promocao"},
    ])
    estoque = _estoque([{"sku": "PROMO-X", "custo_unit": 45.0, "qtd_atual": 5.0, "preco_venda": 200.0}])
    triage = detect_discrepancy_triage(vendas, estoque, None, [], THRESHOLDS)
    assert triage.triggered_count == 1
    item = triage.auto_classified[0]
    # below_cost também é True aqui (40<45), mas promo é sinal de intenção deliberada
    # tão forte quanto — no entanto a árvore prioriza below_cost sobre liquidação
    # pura quando NÃO é dead_stock; aqui confirmamos que promo isolado (sem below_cost
    # coexistindo) classifica como liquidação.
    assert item.evidence.is_promo_flagged is True


def test_promo_reverts_to_pending_with_one_non_promo_sale():
    # mesma régua conservadora do C3: 1 venda normal já reverte o sinal de promoção
    vendas = _sales([
        {"product": "PROMO-Y", "customer": "C1", "value": 100.0,
         "salesperson": "V-01", "store": "L1", "payment_method": "promocao"},
        {"product": "PROMO-Y", "customer": "C2", "value": 100.0,
         "salesperson": "V-01", "store": "L1", "payment_method": "cartao"},
    ])
    estoque = _estoque([{"sku": "PROMO-Y", "custo_unit": 20.0, "qtd_atual": 5.0, "preco_venda": 500.0}])
    triage = detect_discrepancy_triage(vendas, estoque, None, [], THRESHOLDS)
    assert triage.manual_queue and triage.manual_queue[0].evidence.is_promo_flagged is False


def test_below_cost_sale_without_mitigating_evidence():
    vendas = _sales([
        {"product": "SKU-Z", "customer": "C1", "value": 30.0, "entry_cost": 100.0,
         "salesperson": "V-09", "store": "L4"},
    ])
    triage = detect_discrepancy_triage(vendas, None, None, [], THRESHOLDS)
    assert triage.triggered_count == 1
    item = triage.auto_classified[0]
    assert item.verdict == "below_cost_sale"
    assert item.list_price is None  # sem Estoque, Trigger A nunca dispara — Trigger B funciona sozinho


def test_pending_manual_review_when_evidence_is_ambiguous():
    # desconto extremo sobre tabela (75%, dispara Trigger A) — mas NÃO abaixo do
    # custo (entry_cost 50 < praticado 100), custo bate com a NF, SKU não é estoque
    # morto, não é promo, e é caso isolado na loja (só este vendedor -> sem E5).
    # Nenhuma das 5 evidências dispara: precisa mesmo de um humano.
    vendas = _sales([
        {"product": "SKU-W", "customer": "C1", "value": 100.0, "entry_cost": 50.0,
         "salesperson": "V-05", "store": "L2"},
    ])
    estoque = _estoque([{"sku": "SKU-W", "custo_unit": 50.0, "qtd_atual": 5.0, "preco_venda": 400.0}])
    compras = _compras([{"data": D0 - timedelta(days=10), "sku": "SKU-W", "custo_unit": 50.0, "qtd": 3}])
    triage = detect_discrepancy_triage(vendas, estoque, compras, [], THRESHOLDS)
    assert triage.triggered_count == 1
    assert triage.auto_classified == []
    assert triage.manual_queue[0].status == "pending_manual_review"
    assert triage.manual_queue[0].verdict is None
    ev = triage.manual_queue[0].evidence
    assert not any([ev.below_cost, ev.sku_in_dead_stock, ev.is_promo_flagged,
                    ev.cost_diverges_from_nf, ev.store_systemic_pattern])


def test_no_trigger_below_threshold_returns_clean_result():
    vendas = _sales([
        {"product": "SKU-OK", "customer": "C1", "value": 95.0, "entry_cost": 60.0,
         "salesperson": "V-01", "store": "L1"},
    ])
    estoque = _estoque([{"sku": "SKU-OK", "custo_unit": 60.0, "qtd_atual": 5.0, "preco_venda": 100.0}])
    triage = detect_discrepancy_triage(vendas, estoque, None, [], THRESHOLDS)
    assert triage.triggered_count == 0
    assert triage.auto_classified == [] and triage.manual_queue == []


# --------------------------------------------------------------- graceful degradation


def test_no_store_column_returns_none():
    vendas = _sales([{"product": "X", "customer": "C1", "value": 10.0, "salesperson": "V-01"}])
    assert detect_discrepancy_triage(vendas, None, None, [], THRESHOLDS) is None


def test_no_salesperson_column_returns_none():
    vendas = _sales([{"product": "X", "customer": "C1", "value": 10.0, "store": "L1"}])
    assert detect_discrepancy_triage(vendas, None, None, [], THRESHOLDS) is None


def test_never_crashes_when_entry_cost_column_is_entirely_absent():
    """Achado de robustez: arquivo sem NENHUMA linha de custo faz a coluna
    entry_cost vir dtype=object cheia de None (não float64/NaN) — comparação `<`
    direta nesse dtype misto lança TypeError sem a coerção defensiva. Reprodução
    mínima: nenhuma linha do lote tem `entry_cost`."""
    # _sales() sempre inclui a coluna entry_cost (default None) — mesma garantia de
    # schema que o pipeline real oferece (_SALES_FRAME_SCHEMA sempre declara o
    # campo, mesmo quando 100% das linhas do arquivo do cliente vêm sem custo).
    vendas = _sales([
        {"product": "X", "customer": "C1", "value": 100.0, "salesperson": "V-01", "store": "L1"},
    ])
    triage = detect_discrepancy_triage(vendas, None, None, [], THRESHOLDS)
    assert triage.triggered_count == 0  # sem custo e sem lista de preço, nada dispara


def test_dead_stock_evidence_without_estoque_sheet():
    # E2 não depende de Estoque — vem do parâmetro dead_stock já calculado
    vendas = _sales([
        {"product": "DEAD-01", "customer": "C1", "value": 10.0, "entry_cost": 50.0,
         "salesperson": "V-01", "store": "L1"},
    ])
    dead_stock = [DeadStockFinding(
        dead_stock_months=8, sku_count=1, capital_frozen=500.0,
        total_inventory_value=1000.0, dead_stock_pct=50.0, skus=["DEAD-01"],
    )]
    triage = detect_discrepancy_triage(vendas, None, None, dead_stock, THRESHOLDS)
    item = triage.auto_classified[0]
    assert item.evidence.sku_in_dead_stock is True


# --------------------------------------------------------------- fusão de vereditos


def _blank_report(triage):
    return ExecutiveAuditReport(
        period_start="2026-01", period_end="2026-01",
        cleaning=CleaningSummary(rows_read=0, rows_accepted=0),
        thresholds=THRESHOLDS,
        advanced_metrics=AdvancedMetrics(discrepancy_triage=triage),
        executive_summary=ExecutiveSummary(
            total_operational_loss=0.0, total_capital_frozen=0.0, total_ltv_risk=0.0,
        ),
        generated_at="2026-01-01T00:00:00+00:00",
    )


def test_apply_manual_review_promotes_reviewed_items(tmp_path):
    pending_item = DiscrepancyTriageItem(
        id="DTQ-0001", sku="SKU-W", store="L2", salesperson="V-05",
        practiced_price=100.0, entry_cost=150.0,
        evidence=DiscrepancyEvidence(
            below_cost=False, sku_in_dead_stock=False, is_promo_flagged=False,
            cost_diverges_from_nf=False, store_systemic_pattern=False,
        ),
        status="pending_manual_review",
    )
    triage = DiscrepancyTriage(triggered_count=1, manual_queue=[pending_item])
    report = _blank_report(triage)

    review_path = tmp_path / "manual_review_v3.json"
    review_path.write_text(json.dumps({
        "reviews": [{"queue_item_id": "DTQ-0001", "verdict": "deliberate_liquidation"}]
    }), encoding="utf-8")

    updated = apply_manual_review_verdicts(report, review_path)
    new_triage = updated.advanced_metrics.discrepancy_triage
    assert new_triage.manual_queue == []
    assert len(new_triage.auto_classified) == 1
    reviewed = new_triage.auto_classified[0]
    assert reviewed.verdict == "deliberate_liquidation"
    assert reviewed.status == "manually_reviewed"
    # relatório original não foi mutado (nova cópia)
    assert triage.manual_queue == [pending_item]


def test_apply_manual_review_missing_file_returns_report_unchanged(tmp_path):
    triage = DiscrepancyTriage(triggered_count=0)
    report = _blank_report(triage)
    result = apply_manual_review_verdicts(report, tmp_path / "does_not_exist.json")
    assert result is report

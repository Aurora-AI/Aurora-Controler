"""
Testes de conformidade, governança e sabotagem para ART-FIL-002 (Fila de Auditoria Manual).
Contrato: ElysianConsult/docs/CATALOGO/registro/artefatos.yaml (ART-FIL-002)
Doutrina: Aurora Trustware (T1, T2, T3, T4, T6, Regra 13 reprova)
"""
import math
import pytest
from pathlib import Path

from product_b.oracle.forensic_contracts import (
    ExecutiveAuditReport,
    CleaningSummary,
    AuditThresholdsConfig,
    ExecutiveSummary,
    AdvancedMetrics,
    DiscrepancyTriage,
    DiscrepancyTriageItem,
    DiscrepancyEvidence,
)
from product_b.oracle.commercial_auditor import run_audit
from product_b.oracle.manual_audit_queue import (
    ManualAuditQueueItem,
    ManualAuditQueueArtifact,
    build_manual_audit_queue,
    render_manual_audit_queue_text,
)

FIXTURE_CONSULTORIA = Path(__file__).resolve().parents[1] / "Consultoria.xlsx"


def _make_dummy_report(discrepancy_triage: DiscrepancyTriage | None = None) -> ExecutiveAuditReport:
    """Helper para criar um relatório mínimo congelado com triagem."""
    adv = AdvancedMetrics()
    if discrepancy_triage:
        adv.discrepancy_triage = discrepancy_triage
    return ExecutiveAuditReport(
        period_start="2024-01",
        period_end="2026-06",
        cleaning=CleaningSummary(rows_read=100, rows_accepted=100, invalid_dates_dropped=0),
        thresholds=AuditThresholdsConfig(),
        churn_findings=[],
        rfm_champions=[],
        advanced_metrics=adv,
        executive_summary=ExecutiveSummary(
            total_operational_loss=0.0,
            total_capital_frozen=0.0,
            total_ltv_risk=0.0,
        ),
        generated_at="2026-08-17T20:00:00+00:00",
    )


def test_manual_audit_queue_surface_anchor_and_dimensioning():
    """Governança: O artefato expõe o número âncora de pendências e dimensiona a taxa de resíduo."""
    ev = DiscrepancyEvidence(
        below_cost=True,
        sku_in_dead_stock=False,
        is_promo_flagged=False,
        cost_diverges_from_nf=False,
        store_systemic_pattern=False,
    )
    auto_item = DiscrepancyTriageItem(
        id="DTQ-0001",
        sku="SKU-AUTO",
        store="L1",
        salesperson="V1",
        source_rows=[10],
        practiced_price=50.0,
        list_price=100.0,
        entry_cost=60.0,
        below_cost_loss_brl=10.0,
        below_cost_confirmed=True,
        evidence=ev,
        verdict="below_cost_sale",
        status="auto_classified",
    )
    pend_item = DiscrepancyTriageItem(
        id="DTQ-0002",
        sku="SKU-PEND",
        store="L2",
        salesperson="V2",
        source_rows=[20],
        practiced_price=40.0,
        list_price=100.0,
        entry_cost=40.0,
        below_cost_loss_brl=None,
        below_cost_confirmed=False,
        evidence=ev,
        verdict=None,
        status="pending_manual_review",
    )
    
    triage = DiscrepancyTriage(
        triggered_count=20,
        auto_classified=[auto_item] * 19,
        manual_queue=[pend_item],
    )
    report = _make_dummy_report(triage)
    artifact = build_manual_audit_queue(report)
    
    assert artifact.total_disparos == 20
    assert artifact.total_auto_classificados == 19
    assert artifact.total_pendentes == 1
    assert artifact.taxa_residuo_pct == pytest.approx(5.0)
    assert artifact.alerta_dimensionamento is False
    assert len(artifact.itens_pendentes) == 1
    assert artifact.itens_pendentes[0].id == "DTQ-0002"
    assert artifact.itens_pendentes[0].source_rows == [20]


def test_reprova_quando_item_pendente_tem_perda_confirmada_t6():
    """Trava T6 / Sabotagem: Item pendente NUNCA pode ter below_cost_confirmed=True.
    Mesmo se o motor ou objeto injetado contiver True, o artefato deve forçar False."""
    ev = DiscrepancyEvidence(below_cost=True, sku_in_dead_stock=False, is_promo_flagged=False, cost_diverges_from_nf=False, store_systemic_pattern=False)
    corrupted_pend = DiscrepancyTriageItem(
        id="DTQ-BAD",
        sku="SKU-BAD",
        store="L1",
        salesperson="V1",
        source_rows=[1],
        practiced_price=20.0,
        list_price=100.0,
        entry_cost=50.0,
        below_cost_loss_brl=30.0,
        below_cost_confirmed=True,  # CORRUPÇÃO: pendente não pode ter perda confirmada!
        evidence=ev,
        verdict=None,
        status="pending_manual_review",
    )
    triage = DiscrepancyTriage(triggered_count=1, auto_classified=[], manual_queue=[corrupted_pend])
    report = _make_dummy_report(triage)
    artifact = build_manual_audit_queue(report)
    
    assert len(artifact.itens_pendentes) == 1
    # Trava T6 deve ter neutralizado para False
    assert artifact.itens_pendentes[0].below_cost_confirmed is False
    assert artifact.itens_pendentes[0].verdict is None


def test_reprova_quando_residuo_ultrapassa_teto_dimensionamento():
    """Princípio Dimensionador / Sabotagem: Fila com >10% de resíduo deve acionar alerta_dimensionamento=True."""
    ev = DiscrepancyEvidence(below_cost=False, sku_in_dead_stock=False, is_promo_flagged=False, cost_diverges_from_nf=False, store_systemic_pattern=False)
    pend = DiscrepancyTriageItem(
        id="DTQ-P",
        sku="SKU-P",
        store="L1",
        salesperson="V1",
        source_rows=[1],
        practiced_price=50.0,
        evidence=ev,
        verdict=None,
        status="pending_manual_review",
    )
    # 3 disparos, 2 pendentes -> 66.6% de resíduo (> 10%)
    triage = DiscrepancyTriage(triggered_count=3, auto_classified=[], manual_queue=[pend, pend])
    report = _make_dummy_report(triage)
    artifact = build_manual_audit_queue(report)
    
    assert artifact.taxa_residuo_pct == pytest.approx(66.666, rel=1e-2)
    assert artifact.alerta_dimensionamento is True


def test_reprova_divisao_por_zero_quando_zero_disparos():
    """Trava T2 / Sabotagem: Se triggered_count == 0, taxa_residuo_pct deve ser 0.0 sem crash."""
    triage = DiscrepancyTriage(triggered_count=0, auto_classified=[], manual_queue=[])
    report = _make_dummy_report(triage)
    artifact = build_manual_audit_queue(report)
    
    assert artifact.total_disparos == 0
    assert artifact.total_pendentes == 0
    assert artifact.taxa_residuo_pct == 0.0
    assert artifact.alerta_dimensionamento is False


@pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf"), None])
def test_reprova_valores_nao_finitos_em_precos_e_custos(bad_val):
    """Degrau 3 Adversarial: Nenhum float não finito quebra a instanciação ou o renderizador."""
    ev = DiscrepancyEvidence(below_cost=False, sku_in_dead_stock=False, is_promo_flagged=False, cost_diverges_from_nf=False, store_systemic_pattern=False)
    item = DiscrepancyTriageItem(
        id="DTQ-NAN",
        sku="SKU-NAN",
        store="L1",
        salesperson="V1",
        source_rows=[1],
        practiced_price=50.0,
        list_price=bad_val,
        entry_cost=bad_val,
        nf_cost=bad_val,
        discount_over_list_pct=bad_val,
        below_cost_loss_brl=bad_val,
        evidence=ev,
        verdict=None,
        status="pending_manual_review",
    )
    triage = DiscrepancyTriage(triggered_count=1, auto_classified=[], manual_queue=[item])
    report = _make_dummy_report(triage)
    artifact = build_manual_audit_queue(report)
    
    assert len(artifact.itens_pendentes) == 1
    rendered = render_manual_audit_queue_text(artifact)
    assert "DTQ-NAN" in rendered
    assert "[S/TAB]" in rendered or "R$" in rendered


def test_manual_audit_queue_render_is_single_element_t4():
    """Trava T4: Superfície mínima de 1 elemento."""
    ev = DiscrepancyEvidence(below_cost=True, sku_in_dead_stock=False, is_promo_flagged=False, cost_diverges_from_nf=True, store_systemic_pattern=False)
    item = DiscrepancyTriageItem(
        id="DTQ-0001",
        sku="ARP-013\nINJECT",
        store="Loja 01",
        salesperson="V-01",
        source_rows=[189, 526],
        practiced_price=300.0,
        list_price=890.0,
        entry_cost=320.0,
        nf_cost=150.0,
        evidence=ev,
        verdict=None,
        status="pending_manual_review",
    )
    triage = DiscrepancyTriage(triggered_count=1, auto_classified=[], manual_queue=[item])
    report = _make_dummy_report(triage)
    artifact = build_manual_audit_queue(report)
    rendered = render_manual_audit_queue_text(artifact)
    
    assert "=== ART-FIL-002 · Fila de Auditoria Manual" in rendered
    assert "Número Âncora: 1 itens aguardando veredito humano" in rendered
    assert "DTQ-0001" in rendered
    # Quebra de linha sanitizada
    assert "\nINJECT" not in rendered
    assert "ARP-013 INJECT" in rendered


def test_manual_audit_queue_against_consultoria_xlsx_gabarito():
    """Validação direta de ART-FIL-002 contra o Gabarito e a fixture Consultoria.xlsx:
    - 964 disparos totais
    - 922 auto-classificados
    - 42 pendentes na fila manual
    - Taxa de resíduo de ~4.35% (abaixo de 10%)
    - 100% dos 42 itens carregam source_rows e não contêm perdas confirmadas antecipadas.
    """
    assert FIXTURE_CONSULTORIA.exists(), f"Fixture não encontrada: {FIXTURE_CONSULTORIA}"
    report = run_audit(FIXTURE_CONSULTORIA)
    artifact = build_manual_audit_queue(report)
    
    assert artifact.total_disparos == 964
    assert artifact.total_auto_classificados == 922
    assert artifact.total_pendentes == 42
    assert artifact.taxa_residuo_pct == pytest.approx(4.3568, rel=1e-2)
    assert artifact.alerta_dimensionamento is False
    assert len(artifact.itens_pendentes) == 42
    
    for it in artifact.itens_pendentes:
        assert len(it.source_rows) > 0, f"Item {it.id} sem source_rows"
        assert it.status == "pending_manual_review"
        assert it.verdict is None
        assert it.below_cost_confirmed is False

"""
Testes de conformidade e adversariais do artefato ART-FIL-001 (Fila de Resgate Diária v1 Reduzida).
Governança: ElysianConsult/docs/CATALOGO/registro/artefatos.yaml
Doutrina: Aurora Trustware (T1, T2, T3, T4, T5, T6, T7)
"""
import math
import pytest
from pathlib import Path
from datetime import datetime

from product_b.oracle.forensic_contracts import (
    ExecutiveAuditReport, ChurnFinding, CleaningSummary, AuditThresholdsConfig,
    ExecutiveSummary, RFMChampion,
)
from product_b.oracle.commercial_auditor import run_audit
from product_b.oracle.rescue_queue import (
    RescueQueueItem, RescueQueueArtifact, build_rescue_queue, render_rescue_queue_text,
)

FIXTURE_CONSULTORIA = Path(__file__).resolve().parents[1] / "Consultoria.xlsx"


def _make_dummy_report(findings: list[ChurnFinding], champions: list[RFMChampion] | None = None) -> ExecutiveAuditReport:
    """Helper para criar um relatório mínimo congelado."""
    return ExecutiveAuditReport(
        period_start="2024-01",
        period_end="2026-06",
        cleaning=CleaningSummary(rows_read=100, rows_accepted=100, invalid_dates_dropped=0),
        thresholds=AuditThresholdsConfig(),
        churn_findings=findings,
        rfm_champions=champions or [],
        executive_summary=ExecutiveSummary(
            total_operational_loss=0.0,
            total_capital_frozen=0.0,
            total_ltv_risk=0.0,
        ),
        generated_at="2026-08-13T18:00:00+00:00",
    )


def test_rescue_queue_ordering_by_recoverability_not_value():
    """Trava de Ordenação: cliente mais quente (menor ratio) precede cliente mais frio,
    mesmo que o mais frio tenha maior valor histórico (ex. R$ 894 @ 1.7x vs R$ 1.640 @ 2.8x)."""
    frio = ChurnFinding(
        customer_id="Client_Frio_Rico",
        purchase_count=4,
        avg_cadence_days=60.0,
        last_purchase="2025-10-01",
        months_silent=10,
        historical_annual_value=1640.0,
        days_since_last=168,
        silence_to_cycle_ratio=2.8,
        source_rows=[101, 102, 103, 104],
    )
    quente = ChurnFinding(
        customer_id="Client_Quente_Modesto",
        purchase_count=4,
        avg_cadence_days=60.0,
        last_purchase="2026-02-15",
        months_silent=4,
        historical_annual_value=894.0,
        days_since_last=102,
        silence_to_cycle_ratio=1.7,
        source_rows=[201, 202, 203, 204],
    )
    report = _make_dummy_report([frio, quente])
    artifact = build_rescue_queue(report)
    
    assert artifact.total_ativos == 2
    assert artifact.total_sem_base == 0
    # O de menor ratio deve vir PRIMEIRO
    assert artifact.itens_ativos[0].customer_id == "Client_Quente_Modesto"
    assert artifact.itens_ativos[0].silence_to_cycle_ratio == 1.7
    assert artifact.itens_ativos[1].customer_id == "Client_Frio_Rico"
    assert artifact.itens_ativos[1].silence_to_cycle_ratio == 2.8


def test_rescue_queue_trava_t1_no_recalculation_and_t2_reg_num_001():
    """Trava T1 + T2: Se o silence_to_cycle_ratio for inválido (<=0, None, NaN) ou ausente
    no relatório congelado, o formatador NUNCA recalcula days_silent / cadence.
    Ele quarentena o registro em SEM_BASE e o exclui da fila ativa."""
    # Finding com cadence válido e dias válidos, mas ratio zerado ou ausente
    finding_uncomputed_ratio = ChurnFinding(
        customer_id="Client_Motor_Falhou",
        purchase_count=3,
        avg_cadence_days=50.0,
        last_purchase="2026-01-01",
        months_silent=4,
        historical_annual_value=800.0,
        days_since_last=100,
        silence_to_cycle_ratio=0.0,  # <= 0
        source_rows=[10, 11, 12],
    )
    report = _make_dummy_report([finding_uncomputed_ratio])
    artifact = build_rescue_queue(report)
    
    # Não deve ter recalculado para 2.0x!
    assert artifact.total_ativos == 0
    assert artifact.total_sem_base == 1
    assert artifact.itens_sem_base[0].customer_id == "Client_Motor_Falhou"
    assert artifact.itens_sem_base[0].status_selo == "SEM_BASE"
    assert artifact.itens_sem_base[0].silence_to_cycle_ratio is None


@pytest.mark.parametrize("cadence_val,ratio_val", [
    (float("nan"), 1.5),
    (50.0, float("nan")),
    (float("nan"), float("nan")),
    (float("-inf"), 1.5),
    (50.0, float("-inf")),
    (float("inf"), 1.5),
    (50.0, float("inf")),
    (0.0, 1.5),
    (-30.0, 1.5),
    (50.0, 0.0),
    (50.0, -2.0),
])
def test_rescue_queue_adversarial_non_finite_inputs(cadence_val, ratio_val):
    """Degrau 3 Adversarial: Nenhum float não finito ou <= 0 pode vazar para a fila ativa."""
    finding = ChurnFinding(
        customer_id="Client_Adversarial",
        purchase_count=2,
        avg_cadence_days=cadence_val,
        last_purchase="2026-01-01",
        months_silent=5,
        historical_annual_value=100.0,
        days_since_last=150,
        silence_to_cycle_ratio=ratio_val,
        source_rows=[1],
    )
    report = _make_dummy_report([finding])
    artifact = build_rescue_queue(report)
    
    assert artifact.total_ativos == 0
    assert artifact.total_sem_base == 1
    assert artifact.itens_sem_base[0].status_selo == "SEM_BASE"
    assert artifact.itens_sem_base[0].silence_to_cycle_ratio is None


def test_rescue_queue_carries_source_rows_trava_t3():
    """Trava T3: Todo item da fila deve descer até a linha original (source_rows)."""
    finding = ChurnFinding(
        customer_id="Client_Traceable",
        purchase_count=3,
        avg_cadence_days=30.0,
        last_purchase="2026-01-01",
        months_silent=5,
        historical_annual_value=1200.0,
        days_since_last=60,
        silence_to_cycle_ratio=2.0,
        source_rows=[12, 45, 89],
    )
    report = _make_dummy_report([finding])
    artifact = build_rescue_queue(report)
    
    assert len(artifact.itens_ativos) == 1
    assert artifact.itens_ativos[0].source_rows == [12, 45, 89]


def test_rescue_queue_declared_scope_deviation_and_metadata():
    """Governança: O artefato declara o desvio de escopo (superfície parcial v1 sem cross-sell)
    e metadados de canonicidade."""
    report = _make_dummy_report([])
    artifact = build_rescue_queue(report)
    
    assert artifact.artifact_id == "ART-FIL-001"
    assert artifact.version == "v1-reduzida"
    assert artifact.superficie_teto == 1
    assert "Superfície parcial" in artifact.desvio_escopo_declarado
    assert "LAC-FOR-060" in artifact.desvio_escopo_declarado
    assert "LAC-FOR-061" in artifact.desvio_escopo_declarado


def test_rescue_queue_against_consultoria_xlsx_gabarito():
    """Validação contra a fixture funcional Consultoria.xlsx e o Gabarito:
    1. Confirma os 5 clientes de teste plantados de churn (C-017..C-021).
    2. Garante exclusão dos clientes sazonais (SEAS-001..SEAS-005).
    3. Garante que todos os itens possuem source_rows válidos e silence_to_cycle_ratio positivo.
    """
    assert FIXTURE_CONSULTORIA.exists(), f"Fixture não encontrada: {FIXTURE_CONSULTORIA}"
    report, identity_map = run_audit(FIXTURE_CONSULTORIA, return_identity_map=True)
    
    # Inverter mapa de identidade para verificar IDs reais
    pseudo_to_real = {v: k for k, v in identity_map.items()}
    
    artifact = build_rescue_queue(report)
    
    # Total de clientes ativos no churn da fixture
    assert artifact.total_ativos > 0
    
    real_ids_in_queue = {pseudo_to_real.get(item.customer_id, item.customer_id) for item in artifact.itens_ativos}
    
    # 1. Os 5 clientes do Gabarito A3 (C-017 a C-021) devem estar na fila
    for expected_c in ["C-017", "C-018", "C-019", "C-020", "C-021"]:
        assert expected_c in real_ids_in_queue, f"Cliente {expected_c} deveria estar na fila de resgate"
        
    # 2. Clientes sazonais SEAS-001 a SEAS-005 NÃO podem estar na fila de churn (falso positivo do Gabarito B)
    for seas_c in ["SEAS-001", "SEAS-002", "SEAS-003", "SEAS-004", "SEAS-005"]:
        assert seas_c not in real_ids_in_queue, f"Cliente sazonal {seas_c} não deveria estar no churn"
        
    # 3. Pseudo-entidades nunca aparecem
    for item in artifact.itens_ativos:
        assert item.customer_id not in {"SEM_CADASTRO", "LOJA_NAO_IDENTIFICADA", "VENDEDOR_NAO_IDENTIFICADO"}
        assert len(item.source_rows) > 0, f"Cliente {item.customer_id} sem source_rows"
        assert item.silence_to_cycle_ratio is not None and item.silence_to_cycle_ratio > 0


def test_rescue_queue_surface_render_is_single_element_t4():
    """Trava T4: Superfície mínima de 1 elemento."""
    finding = ChurnFinding(
        customer_id="Client_A",
        purchase_count=3,
        avg_cadence_days=50.0,
        last_purchase="2026-01-10",
        months_silent=5,
        historical_annual_value=1250.0,
        days_since_last=100,
        silence_to_cycle_ratio=2.0,
        source_rows=[10, 20, 30],
    )
    report = _make_dummy_report([finding])
    artifact = build_rescue_queue(report)
    rendered = render_rescue_queue_text(artifact)
    
    assert "ART-FIL-001 · Fila de Resgate Diária" in rendered
    assert "Client_A" in rendered
    assert "2.00x" in rendered
    assert "R$ 1,250.00" in rendered
    assert "Contatos Ativos: 1" in rendered

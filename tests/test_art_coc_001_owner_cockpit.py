"""
Testes de conformidade, governança e sabotagem para ART-COC-001 (Cockpit do Dono).
Contrato: ElysianConsult/docs/CATALOGO/registro/artefatos.yaml (ART-COC-001)
Doutrina: Aurora Trustware (T1, T2/REG-NUM-001, T3, T4, REG-SEV-004, Regra 13 reprova)
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
    ChurnFinding,
    AttachRateOpportunity,
    GmroiEntry,
)
from product_b.oracle.commercial_auditor import run_audit
from product_b.oracle.owner_cockpit import (
    CockpitKPI,
    OwnerCockpitArtifact,
    build_owner_cockpit,
    render_owner_cockpit_text,
)

FIXTURE_CONSULTORIA = Path(__file__).resolve().parents[1] / "Consultoria.xlsx"


def _make_minimal_report(
    churn: list[ChurnFinding] | None = None,
    attach: list[AttachRateOpportunity] | None = None,
    gmroi: list[GmroiEntry] | None = None,
) -> ExecutiveAuditReport:
    """Helper para criar um relatório mínimo congelado."""
    adv = AdvancedMetrics()
    if attach is not None:
        adv.attach_rate_opportunities = attach
    return ExecutiveAuditReport(
        period_start="2024-01",
        period_end="2026-06",
        cleaning=CleaningSummary(rows_read=100, rows_accepted=100, invalid_dates_dropped=0),
        thresholds=AuditThresholdsConfig(),
        churn_findings=churn or [],
        rfm_champions=[],
        gmroi=gmroi or [],
        advanced_metrics=adv,
        executive_summary=ExecutiveSummary(
            total_operational_loss=0.0,
            total_capital_frozen=0.0,
            total_ltv_risk=0.0,
        ),
        generated_at="2026-08-17T21:00:00+00:00",
    )


def test_cockpit_surface_exact_7_elements_t4():
    """Trava T4: Superfície estrita com exatamente 7 elementos (1 âncora + 6 secundários)."""
    report = _make_minimal_report()
    artifact = build_owner_cockpit(report)
    
    assert artifact.superficie_teto == 7
    assert artifact.kpi_ancora.kpi_id == "FOR-BAS-003"
    assert len(artifact.kpis_secundarios) == 6
    total_elements = 1 + len(artifact.kpis_secundarios)
    assert total_elements == 7
    assert artifact.total_kpis_ativos + artifact.total_kpis_sem_base == 7


def test_reprova_kpi_sem_base_exibindo_zero_ou_cem_falsos_reg_num_001():
    """REG-NUM-001 / Sabotagem: Indicador sem base NUNCA pode exibir 0.0 nem 100%.
    Deve ter value=None e status_selo='SEM_BASE'."""
    report = _make_minimal_report(churn=[], attach=[], gmroi=[])
    artifact = build_owner_cockpit(report)
    
    # Todos os 7 KPIs devem estar em SEM_BASE
    assert artifact.kpi_ancora.status_selo == "SEM_BASE"
    assert artifact.kpi_ancora.value is None
    
    for k in artifact.kpis_secundarios:
        assert k.status_selo == "SEM_BASE"
        assert k.value is None
        assert k.value != 0.0
        assert k.value != 100.0

    rendered = render_owner_cockpit_text(artifact)
    assert "0.00%" not in rendered
    assert "0.0 dias" not in rendered
    assert "[SEM_BASE]" in rendered


def test_reprova_vazamento_de_nomes_de_vendedores_reg_sev_004():
    """REG-SEV-004 / Sabotagem Adversarial: Injeção ativa de nomes de vendedores via campos
    de oportunidade de venda cruzada deve ser interceptada e neutralizada defensivamente."""
    # Injeta ativamente nomes de vendedores em campos externos
    injected_attach = [
        AttachRateOpportunity(
            anchor_category="Vendedor Maria Silva",
            target_category="V-01 João",
            attach_rate_pct=50.0,
            eligible_customers=100,
        )
    ]
    report = _make_minimal_report(attach=injected_attach)
    artifact = build_owner_cockpit(report)
    rendered = render_owner_cockpit_text(artifact)
    
    # Nenhum identificador nominal individual de vendedor pode aparecer no texto
    forbidden_terms = ["Vendedor", "Maria Silva", "V-01", "João", "Joao", "salesperson", "seller"]
    for term in forbidden_terms:
        assert term not in rendered, f"Vazamento de nome/termo proibido detectado: {term}"


def test_reprova_excesso_ou_falta_de_elementos_na_superficie_pydantic_validator():
    """Trava T4 / Sabotagem: Rejeitar artefatos com contagem de secundários diferente de 6 no Pydantic."""
    report = _make_minimal_report()
    artifact = build_owner_cockpit(report)
    
    # Tentativa de instanciar com 7 secundários (total 8) -> deve estourar ValueError
    too_many = list(artifact.kpis_secundarios) + [
        CockpitKPI(kpi_id="FOR-EXTRA", name="Extra", symbol="extra", unit="%", descricao_fato="Extra")
    ]
    with pytest.raises(ValueError, match="exige exatamente 6 KPIs secundários"):
        OwnerCockpitArtifact(
            kpi_ancora=artifact.kpi_ancora,
            kpis_secundarios=too_many,
            total_kpis_ativos=1,
            total_kpis_sem_base=7,
        )

    # Tentativa de instanciar com 5 secundários (total 6) -> deve estourar ValueError
    too_few = list(artifact.kpis_secundarios)[:5]
    with pytest.raises(ValueError, match="exige exatamente 6 KPIs secundários"):
        OwnerCockpitArtifact(
            kpi_ancora=artifact.kpi_ancora,
            kpis_secundarios=too_few,
            total_kpis_ativos=1,
            total_kpis_sem_base=5,
        )


def test_reprova_indicador_ancora_diferente_de_for_bas_003():
    """Trava T4 / Sabotagem: Rejeitar artefatos com indicador-mãe diferente de FOR-BAS-003."""
    report = _make_minimal_report()
    artifact = build_owner_cockpit(report)
    
    fake_ancora = CockpitKPI(
        kpi_id="FOR-EST-003",
        name="GMROI como Âncora Falsa",
        symbol="fake",
        unit="índice",
        descricao_fato="Incorreto",
    )
    with pytest.raises(ValueError, match="deve ser FOR-BAS-003"):
        OwnerCockpitArtifact(
            kpi_ancora=fake_ancora,
            kpis_secundarios=artifact.kpis_secundarios,
            total_kpis_ativos=1,
            total_kpis_sem_base=6,
        )


def test_reprova_gmroi_com_margem_negativa_ou_estoque_zerado():
    """Degrau 3 Adversarial: GMROI com margem negativa ou estoque zerado/negativo."""
    # 1. Estoque negativo ou zerado -> SEM_BASE
    report_neg_inv = _make_minimal_report(
        gmroi=[
            GmroiEntry(
                category="solar",
                gross_margin=-100.0,
                avg_inventory_value=-50.0,
                gmroi=-2.0,
                sample_size=10,
                is_directional_only=False,
            )
        ]
    )
    artifact_neg_inv = build_owner_cockpit(report_neg_inv)
    kpi_gmroi_neg = [k for k in artifact_neg_inv.kpis_secundarios if k.kpi_id == "FOR-EST-003"][0]
    assert kpi_gmroi_neg.status_selo == "SEM_BASE"
    assert kpi_gmroi_neg.value is None

    # 2. Margem bruta negativa com estoque positivo -> CONFIRMADO com indicador claro de prejuízo
    report_loss = _make_minimal_report(
        gmroi=[
            GmroiEntry(
                category="solar",
                gross_margin=-500.0,
                avg_inventory_value=100.0,
                gmroi=-5.0,
                sample_size=10,
                is_directional_only=False,
            )
        ]
    )
    artifact_loss = build_owner_cockpit(report_loss)
    kpi_loss = [k for k in artifact_loss.kpis_secundarios if k.kpi_id == "FOR-EST-003"][0]
    assert kpi_loss.status_selo == "CONFIRMADO"
    assert kpi_loss.value == -5.0
    assert "negativo" in kpi_loss.descricao_fato


@pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf"), -50.0, 0.0])
def test_reprova_valores_nao_finitos_ou_degenerados_em_cadencia_ancora(bad_val):
    """Degrau 3 Adversarial: Cadências não finitas ou <=0 em churn findings não contaminam o indicador-mãe."""
    bad_churn = ChurnFinding(
        customer_id="C_BAD",
        purchase_count=2,
        avg_cadence_days=bad_val,
        last_purchase="2026-01-01",
        months_silent=5,
        historical_annual_value=100.0,
        days_since_last=150,
        silence_to_cycle_ratio=1.5,
        source_rows=[1],
    )
    report = _make_minimal_report(churn=[bad_churn])
    artifact = build_owner_cockpit(report)
    
    # Como a única cadência é inválida, o âncora deve ir honrosamente para SEM_BASE
    assert artifact.kpi_ancora.status_selo == "SEM_BASE"
    assert artifact.kpi_ancora.value is None


def test_cockpit_against_consultoria_xlsx_gabarito():
    """Validação direta de ART-COC-001 contra a fixture Consultoria.xlsx:
    - Indicador-mãe FOR-BAS-003 (Ciclo Médio): 67.9 dias (CONFIRMADO)
    - FOR-BAS-007 (Attach Rate): 61.5% (CONFIRMADO)
    - FOR-EST-003 (GMROI Consolidado): 0.63 (CONFIRMADO)
    - 4 KPIs quarentenados em SEM_BASE (FOR-BAS-010, FOR-BAS-009, FOR-BAS-011, FOR-FIN-004)
    - Total de confirmados: 3 | Total SEM_BASE: 4 | Total superfície: 7
    """
    assert FIXTURE_CONSULTORIA.exists(), f"Fixture ausente: {FIXTURE_CONSULTORIA}"
    report = run_audit(FIXTURE_CONSULTORIA)
    artifact = build_owner_cockpit(report)
    
    # 1. Âncora FOR-BAS-003
    assert artifact.kpi_ancora.kpi_id == "FOR-BAS-003"
    assert artifact.kpi_ancora.status_selo == "CONFIRMADO"
    assert artifact.kpi_ancora.value == pytest.approx(67.9, rel=1e-2)
    assert artifact.kpi_ancora.unit == "dias"
    assert artifact.kpi_ancora.meta_direcao == "QUEDA"
    
    # 2. Secundários
    sec_map = {k.kpi_id: k for k in artifact.kpis_secundarios}
    assert len(sec_map) == 6
    
    # FOR-BAS-010 (SEM_BASE)
    assert sec_map["FOR-BAS-010"].status_selo == "SEM_BASE"
    assert sec_map["FOR-BAS-010"].value is None
    
    # FOR-BAS-009 (SEM_BASE)
    assert sec_map["FOR-BAS-009"].status_selo == "SEM_BASE"
    assert sec_map["FOR-BAS-009"].value is None
    
    # FOR-BAS-007 (Attach Rate: 61.5%)
    assert sec_map["FOR-BAS-007"].status_selo == "CONFIRMADO"
    assert sec_map["FOR-BAS-007"].value == pytest.approx(61.5, rel=1e-2)
    assert sec_map["FOR-BAS-007"].unit == "%"
    
    # FOR-EST-003 (GMROI Consolidado: 0.63)
    assert sec_map["FOR-EST-003"].status_selo == "CONFIRMADO"
    assert sec_map["FOR-EST-003"].value == pytest.approx(0.63, rel=1e-2)
    assert sec_map["FOR-EST-003"].unit == "índice"
    
    # FOR-BAS-011 (SEM_BASE)
    assert sec_map["FOR-BAS-011"].status_selo == "SEM_BASE"
    assert sec_map["FOR-BAS-011"].value is None
    
    # FOR-FIN-004 (SEM_BASE)
    assert sec_map["FOR-FIN-004"].status_selo == "SEM_BASE"
    assert sec_map["FOR-FIN-004"].value is None
    
    # Contagens de Governança
    assert artifact.total_kpis_ativos == 3
    assert artifact.total_kpis_sem_base == 4
    
    # Renderização textual
    rendered = render_owner_cockpit_text(artifact)
    assert "ART-COC-001 · COCKPIT DO DONO" in rendered
    assert "67.9 dias" in rendered
    assert "61.5%" in rendered
    assert "0.63 (índice)" in rendered
    assert "[SEM_BASE]" in rendered

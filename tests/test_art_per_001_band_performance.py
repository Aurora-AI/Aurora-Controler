"""
Testes de conformidade, governança e sabotagem para ART-PER-001 (Painel de Performance por Bandas).
Contrato: ElysianConsult/docs/CATALOGO/registro/artefatos.yaml (ART-PER-001)
Dicionário: ElysianConsult/docs/CATALOGO/render/DICIONARIO_DASHBOARD.md (L358-L403)
Doutrina: Aurora Trustware (T1, T2/REG-NUM-001, T3, T4, REG-SEV-004, REG-NUM-002, Regra 13 reprova)
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
    SalespersonPerformance,
    SellerMarginCorrosionAlert,
    SellerMarginMixProfile,
)
from product_b.oracle.commercial_auditor import run_audit
from product_b.oracle.band_performance import (
    BandSummary,
    StoreBandSummary,
    BandPerformanceArtifact,
    build_band_performance,
    render_band_performance_text,
)

FIXTURE_CONSULTORIA = Path(__file__).resolve().parents[1] / "Consultoria.xlsx"


def _make_seller(
    salesperson: str,
    total_revenue: float,
    sample_size: int = 50,
    capture_rate_pct: float = 80.0,
    low_capture_flag: bool = False,
    days_since_first_sale: int = 500,
    has_sufficient_tenure: bool = True,
    low_volume_flag: bool = False,
) -> SalespersonPerformance:
    """Helper para instanciar SalespersonPerformance com todos os campos obrigatórios."""
    return SalespersonPerformance(
        salesperson=salesperson,
        total_revenue=total_revenue,
        sample_size=sample_size,
        capture_rate_pct=capture_rate_pct,
        low_capture_flag=low_capture_flag,
        days_since_first_sale=days_since_first_sale,
        has_sufficient_tenure=has_sufficient_tenure,
        low_volume_flag=low_volume_flag,
    )


def _make_minimal_report(
    sp: list[SalespersonPerformance] | None = None,
    corrosion: list[SellerMarginCorrosionAlert] | None = None,
) -> ExecutiveAuditReport:
    """Helper para criar um relatório mínimo congelado."""
    adv = AdvancedMetrics()
    if corrosion is not None:
        adv.seller_margin_corrosion = corrosion
    return ExecutiveAuditReport(
        period_start="2024-01",
        period_end="2026-06",
        cleaning=CleaningSummary(rows_read=100, rows_accepted=100, invalid_dates_dropped=0),
        thresholds=AuditThresholdsConfig(),
        churn_findings=[],
        rfm_champions=[],
        gmroi=[],
        salesperson_performance=sp or [],
        advanced_metrics=adv,
        executive_summary=ExecutiveSummary(
            total_operational_loss=0.0,
            total_capital_frozen=0.0,
            total_ltv_risk=0.0,
        ),
        generated_at="2026-08-18T07:00:00+00:00",
    )


def test_band_performance_surface_exact_4_elements_t4():
    """Trava T4: Superfície estrita com teto de exatamente 4 elementos estruturais."""
    # 4 vendedores para partição mínima
    sps = [
        _make_seller("V-01", 4000.0),
        _make_seller("V-02", 3000.0),
        _make_seller("V-03", 2000.0),
        _make_seller("V-04", 1000.0),
    ]
    report = _make_minimal_report(sp=sps)
    artifact = build_band_performance(report)

    assert artifact.superficie_teto == 4
    # Elemento 1 (Âncora): Gap em R$
    assert artifact.anchor_gap_topo_media_brl is not None
    assert artifact.anchor_gap_topo_media_brl == pytest.approx(1500.0, rel=1e-2)  # Topo (4000) - Média (2500) = 1500
    # Elemento 2: 4 Bandas
    assert len(artifact.bandas) == 4
    band_names = [b.band_name for b in artifact.bandas]
    assert band_names == ["Topo", "Forte", "Médio", "Base"]
    # Elemento 3: Assinaturas de comportamento
    assert len(artifact.assinaturas_comportamento) == 4
    # Elemento 4: Tendências intra-loja
    assert isinstance(artifact.lojas_tendencias, list)


def test_reprova_vazamento_de_nomes_de_vendedores_reg_sev_004():
    """REG-SEV-004 / Sabotagem Adversarial: O Painel de Bandas NUNCA pode expor
    nomes nominais, rankings punitivos ou IDs individuais de vendedores na tela do gestor."""
    # Injeta vendedores com nomes literais e IDs
    sps = [
        _make_seller("João Silva (V-01)", 10000.0),
        _make_seller("Maria Santos (V-02)", 8000.0),
        _make_seller("Pedro Costa (V-03)", 5000.0),
        _make_seller("Ana Lima (V-04)", 2000.0),
    ]
    report = _make_minimal_report(sp=sps)
    artifact = build_band_performance(report)
    rendered = render_band_performance_text(artifact)

    forbidden_terms = [
        "João", "Silva", "Maria", "Santos", "Pedro", "Costa", "Ana", "Lima",
        "V-01", "V-02", "V-03", "V-04", "salesperson", "ranking_cru",
    ]
    for term in forbidden_terms:
        assert term not in rendered, f"Vazamento de nome/termo individual detectado no render: {term}"


def test_reprova_excesso_ou_falta_de_bandas_pydantic_validator():
    """Trava T4 / Sabotagem: Rejeitar artefatos com número de bandas != 4 no validador Pydantic."""
    report = _make_minimal_report()
    artifact = build_band_performance(report)

    # Tentativa de instanciar com 5 bandas
    too_many = list(artifact.bandas) + [
        BandSummary(band_name="Ultra", behavior_signature="Extra")
    ]
    with pytest.raises(ValueError, match="exige exatamente 4 bandas"):
        BandPerformanceArtifact(
            anchor_gap_topo_media_brl=100.0,
            status_selo="CONFIRMADO",
            bandas=too_many,
            assinaturas_comportamento={},
            lojas_tendencias=[],
            total_vendedores_avaliados=5,
        )

    # Tentativa de instanciar com 3 bandas
    too_few = list(artifact.bandas)[:3]
    with pytest.raises(ValueError, match="exige exatamente 4 bandas"):
        BandPerformanceArtifact(
            anchor_gap_topo_media_brl=100.0,
            status_selo="CONFIRMADO",
            bandas=too_few,
            assinaturas_comportamento={},
            lojas_tendencias=[],
            total_vendedores_avaliados=3,
        )


def test_reprova_amostra_insuficiente_quarentenada_reg_num_002():
    """REG-NUM-002 / REG-NUM-001: Menos de 4 vendedores não permite formar 4 bandas.
    Deve ir para SEM_BASE com anchor_gap=None e selo SEM_BASE."""
    sps = [
        _make_seller("V-01", 5000.0),
        _make_seller("V-02", 3000.0),
    ]
    report = _make_minimal_report(sp=sps)
    artifact = build_band_performance(report)

    assert artifact.status_selo == "SEM_BASE"
    assert artifact.anchor_gap_topo_media_brl is None
    assert artifact.total_vendedores_avaliados == 2

    rendered = render_band_performance_text(artifact)
    assert "[SEM_BASE]" in rendered


@pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf"), -100.0])
def test_reprova_valores_nao_finitos_ou_degenerados_em_receitas(bad_val):
    """Degrau 3 Adversarial: Receitas corrompidas ou não finitas são descartadas sem poluir médias."""
    sps = [
        _make_seller("V-BAD", bad_val),
        _make_seller("V-01", 4000.0),
        _make_seller("V-02", 3000.0),
        _make_seller("V-03", 2000.0),
        _make_seller("V-04", 1000.0),
    ]
    report = _make_minimal_report(sp=sps)
    artifact = build_band_performance(report)

    # V-BAD deve ser excluído dos válidos (restando 4 vendedores válidos)
    assert artifact.total_vendedores_avaliados == 4
    assert artifact.status_selo == "CONFIRMADO"
    assert artifact.anchor_gap_topo_media_brl == pytest.approx(1500.0, rel=1e-2)


def test_band_performance_against_consultoria_xlsx_gabarito():
    """Validação direta de ART-PER-001 contra a fixture real Consultoria.xlsx:
    - 34 vendedores avaliados
    - 10 lojas cobertas
    - Indicador-mãe (Gap Topo vs Média): R$ 55.844,77 (CONFIRMADO)
    - 4 Bandas: Topo (N=8, Média R$ 96.093,92), Forte (N=9, Média R$ 43.383,43),
      Médio (N=9, Média R$ 18.238,42), Base (N=8, Média R$ 5.640,40)
    - Assinaturas de comportamento presentes para as 4 bandas
    - Tendências intra-loja computadas para as 10 lojas
    """
    assert FIXTURE_CONSULTORIA.exists(), f"Fixture ausente: {FIXTURE_CONSULTORIA}"
    report = run_audit(FIXTURE_CONSULTORIA)
    artifact = build_band_performance(report)

    # Governança
    assert artifact.artifact_id == "ART-PER-001"
    assert artifact.total_vendedores_avaliados == 34
    assert artifact.total_lojas_cobertas == 10
    assert artifact.status_selo == "CONFIRMADO"

    # Elemento 1 (Âncora)
    assert artifact.anchor_gap_topo_media_brl == pytest.approx(55844.77, rel=1e-2)

    # Elemento 2 (4 Bandas)
    assert len(artifact.bandas) == 4
    b_map = {b.band_name: b for b in artifact.bandas}

    # Topo
    assert b_map["Topo"].seller_count == 8
    assert b_map["Topo"].avg_revenue_brl == pytest.approx(96093.92, rel=1e-2)
    assert b_map["Topo"].min_revenue_brl == pytest.approx(82343.42, rel=1e-2)
    assert b_map["Topo"].max_revenue_brl == pytest.approx(127384.97, rel=1e-2)

    # Forte
    assert b_map["Forte"].seller_count == 9
    assert b_map["Forte"].avg_revenue_brl == pytest.approx(43383.43, rel=1e-2)

    # Médio
    assert b_map["Médio"].seller_count == 9
    assert b_map["Médio"].avg_revenue_brl == pytest.approx(18238.42, rel=1e-2)

    # Base
    assert b_map["Base"].seller_count == 8
    assert b_map["Base"].avg_revenue_brl == pytest.approx(5640.40, rel=1e-2)

    # Elemento 3 (Assinaturas)
    for b_name in ["Topo", "Forte", "Médio", "Base"]:
        assert b_name in artifact.assinaturas_comportamento
        assert len(artifact.assinaturas_comportamento[b_name]) > 10

    # Elemento 4 (Tendências Intra-Loja)
    assert len(artifact.lojas_tendencias) == 10
    st_names = [st.store for st in artifact.lojas_tendencias]
    assert "L1 - Centro" in st_names
    assert "L9 - Serra" in st_names

    # Renderização textual
    rendered = render_band_performance_text(artifact)
    assert "ART-PER-001 · PAINEL DE PERFORMANCE POR BANDAS" in rendered
    assert "R$ 55,844.77" in rendered
    assert "BANDA TOPO" in rendered
    assert "L1 - Centro" in rendered
    # Proibição de nomes de vendedores no render
    assert "V-01" not in rendered
    assert "V-30" not in rendered

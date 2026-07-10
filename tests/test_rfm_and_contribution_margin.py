"""
Testes de regressão — Fix 3 (1ª etapa, só aba Vendas): RFM Campeões (Gabarito #2) e
Margem de Contribuição / B5 (Gabarito #6).

RFM: recência crua não discrimina em negócio de compra recorrente regular (ver
docstring de detect_rfm_champions) — vira gate de "ainda ativo" pela cadência PRÓPRIA
do cliente, reaproveitando o limiar do churn (A3). Trava: recall 100% dos 10 campeões
plantados (C-001..C-010); os 5 churners plantados (C-017..C-021) NUNCA aparecem
(cadência silenciosa reprova o gate).

B5: a fixture sintética não planta margem negativa na aba Vendas (o cenário MCNEG vive
na aba Estoque, fora do escopo desta 1ª etapa) — a trava aqui é negativa: nenhum SKU
saudável (margem ~40-60%) deve disparar falso positivo.
"""
from pathlib import Path

from oracle.commercial_auditor import run_audit

FIXTURE = Path(__file__).parent / "fixtures" / "otica_test_bom.xlsx"

_CHAMPIONS = {f"C-{i:03d}" for i in range(1, 11)}
_CHURNERS = {f"C-{i:03d}" for i in range(17, 22)}


def test_rfm_recalls_all_planted_champions():
    report, identity_map = run_audit(FIXTURE, return_identity_map=True)
    reverse_map = {pseudo: real for real, pseudo in identity_map.items()}
    champion_ids = {
        reverse_map.get(c.customer_id, c.customer_id) for c in report.rfm_champions
    }
    assert _CHAMPIONS <= champion_ids


def test_rfm_never_flags_a_churner_as_champion():
    report, identity_map = run_audit(FIXTURE, return_identity_map=True)
    reverse_map = {pseudo: real for real, pseudo in identity_map.items()}
    champion_ids = {
        reverse_map.get(c.customer_id, c.customer_id) for c in report.rfm_champions
    }
    assert not (_CHURNERS & champion_ids)


def test_rfm_excludes_anonymous_pseudo_customer():
    report, identity_map = run_audit(FIXTURE, return_identity_map=True)
    reverse_map = {pseudo: real for real, pseudo in identity_map.items()}
    champion_ids = {
        reverse_map.get(c.customer_id, c.customer_id) for c in report.rfm_champions
    }
    assert "SEM_CADASTRO" not in champion_ids


def test_contribution_margin_no_false_positive_on_healthy_skus():
    report = run_audit(FIXTURE)
    assert report.contribution_margin_alerts == []


# ── Receita Latente / Attach (Gabarito #3) ──────────────────────────────────────────
# A fixture não sustenta o "100 clientes de grau" do Gabarito (todo cliente compra
# "lente" no gerador — não há sinal transacional que isole esse subgrupo; é um recorte
# de ID artificial). A trava aqui é sobre o que É real e estável: separação
# fato-vs-cenário, e os 70 solar_buyers plantados (C-050..C-119) nunca aparecem como
# não-compradores.
_SOLAR_BUYERS = {f"C-{i:03d}" for i in range(50, 120)}


def test_latent_revenue_separates_fact_from_scenario():
    report = run_audit(FIXTURE)
    assert len(report.latent_revenue) == 1
    finding = report.latent_revenue[0]
    # Fato: attach rate = compradores do complemento / base elegível.
    expected_attach_pct = 100.0 * (finding.eligible_customers - finding.non_buyers_count) / finding.eligible_customers
    assert finding.attach_rate_pct == expected_attach_pct
    # Cenário: a fórmula de R$ latente usa a conversão assumida, nunca o attach rate.
    expected_latent = (
        finding.non_buyers_count * finding.assumed_conversion_pct / 100.0
        * finding.avg_ticket_target_category
    )
    assert abs(finding.estimated_latent_revenue - expected_latent) < 0.01


def test_latent_revenue_excludes_known_solar_buyers():
    report, identity_map = run_audit(FIXTURE, return_identity_map=True)
    reverse_map = {pseudo: real for real, pseudo in identity_map.items()}
    finding = report.latent_revenue[0]
    non_buyer_real_ids = {
        reverse_map.get(c, c) for c in finding.non_buyer_customers
    }
    assert not (_SOLAR_BUYERS & non_buyer_real_ids)

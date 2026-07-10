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

# -*- coding: utf-8 -*-
"""
Testes de regressão — Fase E, E3-v1: Matriz de Habilidade vs. Viés (proxy).

Leitura sobre SellerMarginMixProfile.mix já existente (Fase D, Pilar 1) — objetos
construídos diretamente, sem passar pelo detector de origem.
"""
from product_b.oracle.commercial_auditor import detect_skill_gaps
from product_b.oracle.forensic_contracts import (
    AuditThresholdsConfig, SellerCategoryMixEntry, SellerMarginMixProfile,
)

THRESHOLDS = AuditThresholdsConfig()  # skill_gap_avoidance_pp = 10.0


def _entry(category, deviation, margin):
    return SellerCategoryMixEntry(
        category=category, seller_revenue=1000.0, seller_mix_pct=10.0 + deviation,
        store_mix_pct=10.0, mix_deviation_pp=deviation, category_margin_pct=margin,
    )


def _profile(mix, store_margin=30.0, salesperson="V-01", store="L1"):
    return SellerMarginMixProfile(
        salesperson=salesperson, store=store, total_revenue=10000.0, seller_margin_pct=25.0,
        store_margin_pct=store_margin, margin_gap_pp=5.0, is_margin_destructive=False,
        sample_size=50, mix=mix,
    )


def test_evita_categoria_de_margem_alta_vira_hipotese():
    # vende 15pp menos que o padrão da loja (> 10pp de piso) numa categoria que
    # margeia mais (50%) que a loja (30%) -> hipótese
    profile = _profile([_entry("multifocal", deviation=-15.0, margin=50.0)], store_margin=30.0)
    diagnoses = detect_skill_gaps([profile], THRESHOLDS)
    assert len(diagnoses) == 1
    d = diagnoses[0]
    assert d.salesperson == "V-01" and d.store == "L1" and d.category == "multifocal"
    assert d.mix_deviation_pp == -15.0
    assert d.is_proxy is True
    assert "hipótese" in d.hypothesis or "déficit" in d.hypothesis
    assert d.data_gap == "conversao_real_requer_aba_orcamentos"


def test_desvio_abaixo_do_piso_nao_vira_hipotese():
    # só 5pp abaixo do padrão (< piso de 10pp) -> não dispara, mesmo com margem alta
    profile = _profile([_entry("multifocal", deviation=-5.0, margin=50.0)], store_margin=30.0)
    assert detect_skill_gaps([profile], THRESHOLDS) == []


def test_categoria_de_margem_baixa_nao_vira_hipotese():
    # evita muito (-20pp) mas a categoria margeia MENOS que a loja -> não é
    # evitação de categoria valiosa, não dispara
    profile = _profile([_entry("entrada", deviation=-20.0, margin=10.0)], store_margin=30.0)
    assert detect_skill_gaps([profile], THRESHOLDS) == []


def test_vendedor_empurra_categoria_mais_nao_dispara():
    # mix_deviation_pp positivo (vende MAIS que o padrão) -> nunca é "evitação"
    profile = _profile([_entry("multifocal", deviation=20.0, margin=50.0)], store_margin=30.0)
    assert detect_skill_gaps([profile], THRESHOLDS) == []


def test_multiplas_categorias_cada_uma_avaliada_independente():
    profile = _profile([
        _entry("multifocal", deviation=-15.0, margin=50.0),  # dispara
        _entry("entrada", deviation=-15.0, margin=10.0),      # margem baixa, não dispara
        _entry("solar", deviation=-3.0, margin=45.0),         # abaixo do piso, não dispara
    ], store_margin=30.0)
    diagnoses = detect_skill_gaps([profile], THRESHOLDS)
    assert len(diagnoses) == 1
    assert diagnoses[0].category == "multifocal"


def test_sem_perfis_retorna_vazio():
    assert detect_skill_gaps([], THRESHOLDS) == []

"""
Testes de regressão — Fase D, Pilar 1 (Mix de Venda por Categoria de Margem):
distingue vendedor improdutivo (vende pouco) de vendedor destruidor de margem
(volume normal/alto, concentrado numa categoria de margem baixa acima do padrão da
própria loja).
"""
from datetime import datetime

import pandas as pd
import pytest

from product_b.oracle.commercial_auditor import detect_seller_margin_mix
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

THRESHOLDS = AuditThresholdsConfig()
D0 = datetime(2026, 1, 1)


def _sales(rows):
    # source_row sempre presente no pipeline real (schema fixo desde a Fase C) —
    # aqui, default sequencial pra quem não passar explicitamente.
    return pd.DataFrame([
        {"date": D0, "source_row": i + 2, **r} for i, r in enumerate(rows)
    ])


def _line(product, customer, value, entry_cost, salesperson, store, category):
    return {
        "product": product, "customer": customer, "value": value, "entry_cost": entry_cost,
        "salesperson": salesperson, "store": store, "category": category,
    }


def _make_seller_rows(salesperson, store, n_alto, n_baixo, value_alto=200.0, cost_alto=100.0,
                       value_baixo=200.0, cost_baixo=195.0):
    # categoria "premium": margem 50% · categoria "entrada": margem 2,5%
    rows = []
    for i in range(n_alto):
        rows.append(_line("P-PREMIUM", f"C{salesperson}{i}", value_alto, cost_alto, salesperson, store, "premium"))
    for i in range(n_baixo):
        rows.append(_line("P-ENTRADA", f"C{salesperson}b{i}", value_baixo, cost_baixo, salesperson, store, "entrada"))
    return rows


def test_flags_seller_concentrated_on_low_margin_category():
    # loja L1: V-01 vende metade/metade (referência da loja); V-02 empurra só a
    # categoria de margem baixa -> margem blendada bem abaixo da loja.
    rows = (
        _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)
        + _make_seller_rows("V-02", "L1", n_alto=0, n_baixo=20)
    )
    df = _sales(rows)
    profiles = detect_seller_margin_mix(df, THRESHOLDS)
    by_seller = {p.salesperson: p for p in profiles}

    assert by_seller["V-02"].is_margin_destructive is True
    assert by_seller["V-02"].margin_gap_pp > THRESHOLDS.seller_margin_gap_pct
    # a categoria "entrada" precisa aparecer no topo do mix (maior desvio) para V-02
    top = by_seller["V-02"].mix[0]
    assert top.category == "entrada"
    assert top.mix_deviation_pp > 0
    assert top.category_margin_pct < 50.0  # é de fato a categoria de margem mais baixa


def test_seller_matching_store_pattern_is_not_flagged():
    # V-01 vende exatamente no mesmo mix da loja (ele PRÓPRIO é metade da loja) ->
    # gap deve ficar em 0, nunca destrutivo.
    rows = _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)
    df = _sales(rows)
    profiles = detect_seller_margin_mix(df, THRESHOLDS)
    assert len(profiles) == 1
    assert profiles[0].is_margin_destructive is False
    assert profiles[0].margin_gap_pp == pytest.approx(0.0, abs=0.01)


def test_high_volume_seller_can_still_be_margin_destructive():
    """O ponto central do pilar: volume alto não perdoa margem baixa. V-03 tem MAIS
    receita que qualquer vendedor saudável isolado, mas quase toda ela na categoria
    de margem baixa — 3 vendedores saudáveis ancoram o benchmark da loja o
    suficiente pra a corrosão de V-03 aparecer no gap (com só 1-2 âncoras, o volume
    de V-03 arrasta a própria média da loja pra perto dele — efeito matemático
    esperado de um benchmark blendado por receita, não um bug)."""
    healthy = (
        _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)
        + _make_seller_rows("V-04", "L1", n_alto=10, n_baixo=10)
        + _make_seller_rows("V-05", "L1", n_alto=10, n_baixo=10)
        + _make_seller_rows("V-06", "L1", n_alto=10, n_baixo=10)
    )
    corrosive = _make_seller_rows("V-03", "L1", n_alto=0, n_baixo=25)
    df = _sales(healthy + corrosive)
    profiles = detect_seller_margin_mix(df, THRESHOLDS)
    by_seller = {p.salesperson: p for p in profiles}
    assert by_seller["V-03"].total_revenue > by_seller["V-01"].total_revenue
    assert by_seller["V-03"].is_margin_destructive is True


def test_below_minimum_sample_is_excluded():
    rows = _make_seller_rows("V-09", "L1", n_alto=1, n_baixo=2)  # 3 vendas, abaixo do piso (10)
    df = _sales(rows)
    profiles = detect_seller_margin_mix(df, THRESHOLDS)
    assert profiles == []


def test_excludes_returns_and_service_category():
    rows = _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)
    rows.append(_line("SVC-01", "C1", 500.0, 50.0, "V-01", "L1", "servico"))  # fora: serviço
    rows.append(_line("P-ENTRADA", "C2", -180.0, 180.0, "V-01", "L1", "entrada"))  # fora: devolução
    df = _sales(rows)
    profiles = detect_seller_margin_mix(df, THRESHOLDS)
    assert len(profiles) == 1
    categories = {m.category for m in profiles[0].mix}
    assert "servico" not in categories


def test_excludes_pseudo_salesperson():
    rows = _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)
    ghost_rows = _make_seller_rows("V-02", "L1", n_alto=10, n_baixo=10)
    for r in ghost_rows:
        r.pop("salesperson")  # vira pseudo-entidade (fillna interno do motor)
    df = pd.concat([_sales(rows), _sales(ghost_rows)], ignore_index=True)
    profiles = detect_seller_margin_mix(df, THRESHOLDS)
    assert {p.salesperson for p in profiles} == {"V-01"}


def test_excludes_literal_placeholder_string_as_pseudo_entity_too():
    """QA (achado, mesma classe de armadilha da Pegadinha 3/Beta): se a string
    LITERAL do placeholder interno aparecer como dado real (não via fillna), ainda
    precisa ser excluída da avaliação — o filtro roda depois do fillna, sobre valor,
    não sobre origem do dado."""
    rows = _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)
    literal_rows = _make_seller_rows("VENDEDOR_NAO_IDENTIFICADO", "L1", n_alto=10, n_baixo=10)
    df = pd.concat([_sales(rows), _sales(literal_rows)], ignore_index=True)
    profiles = detect_seller_margin_mix(df, THRESHOLDS)
    assert {p.salesperson for p in profiles} == {"V-01"}


def test_pseudo_salesperson_revenue_still_counts_in_store_benchmark():
    """QA (achado crítico): vendedor não identificado é excluído da AVALIAÇÃO
    individual, mas a receita dele é fato bruto da loja — precisa continuar contando
    no benchmark contra o qual os vendedores REAIS são comparados (mesmo critério de
    `detect_customer_concentration`: `store_revenue` = toda venda da loja). Excluir
    a receita walk-in do benchmark subestimaria a margem real da loja."""
    named = _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)
    # mix bem diferente de V-01 (quase só categoria de margem baixa) — se a receita
    # walk-in for descartada do benchmark por engano, a média da loja não muda nada
    # entre os dois cenários; se for preservada (correto), muda visivelmente.
    unidentified = _make_seller_rows("V-02", "L1", n_alto=0, n_baixo=20)
    for r in unidentified:
        r.pop("salesperson")
    df_with_ghost = pd.concat([_sales(named), _sales(unidentified)], ignore_index=True)
    df_without_ghost = _sales(named)

    profiles_with = detect_seller_margin_mix(df_with_ghost, THRESHOLDS)
    profiles_without = detect_seller_margin_mix(df_without_ghost, THRESHOLDS)

    store_margin_with = profiles_with[0].store_margin_pct
    store_margin_without = profiles_without[0].store_margin_pct
    # a receita fantasma some da AVALIAÇÃO (só V-01 aparece nos dois casos), mas o
    # benchmark da loja muda porque a receita walk-in ainda está lá pesando na média
    assert {p.salesperson for p in profiles_with} == {"V-01"}
    assert store_margin_with != pytest.approx(store_margin_without, abs=0.001)


def test_store_benchmark_is_local_not_network_wide():
    """Loja L2 tem um mix inteiramente diferente de L1 — um vendedor de L2 não pode
    ser avaliado contra a margem de L1."""
    rows = (
        _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)  # loja L1: 50/50
        + _make_seller_rows("V-05", "L2", n_alto=10, n_baixo=10)  # loja L2: 50/50, mesmo mix da própria loja
    )
    df = _sales(rows)
    profiles = detect_seller_margin_mix(df, THRESHOLDS)
    by_seller = {p.salesperson: p for p in profiles}
    assert by_seller["V-05"].is_margin_destructive is False
    assert by_seller["V-05"].store == "L2"


def test_graceful_degradation_missing_columns():
    df = pd.DataFrame([{"date": D0, "product": "X", "customer": "C1", "value": 100.0}])
    assert detect_seller_margin_mix(df, THRESHOLDS) == []


def test_graceful_degradation_no_entry_cost_column_present():
    rows = _make_seller_rows("V-01", "L1", n_alto=10, n_baixo=10)
    for r in rows:
        r.pop("entry_cost")
    df = _sales(rows)
    assert detect_seller_margin_mix(df, THRESHOLDS) == []

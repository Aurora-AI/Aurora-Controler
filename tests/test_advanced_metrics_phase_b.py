"""
Testes de regressão — Fase B (SPEC_Fase_B_Formulas_Avancadas.md): os 5 algoritmos
analíticos avançados (GMROI por SKU, Attach Rate, Corrosão de desconto por vendedor,
Concentração VIP por vendedor, Conversão Follow-on).

Cada bloco testa: (1) o caso onde o achado deve aparecer, (2) graceful degradation
quando a coluna/aba de origem falta, (3) as constraints explícitas da OS (nunca
ZeroDivisionError, nunca inventa achado sem base).
"""
from datetime import datetime

import pandas as pd
import pytest

from product_b.oracle.commercial_auditor import (
    detect_attach_rate_opportunities, detect_follow_on_conversion, detect_gmroi_by_sku,
    detect_seller_margin_corrosion, detect_vip_concentration_risk,
)
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

THRESHOLDS = AuditThresholdsConfig()


def _sales(rows):
    return pd.DataFrame([{
        "date": pd.Timestamp(datetime(2026, 1, 1)), "quantity": 1.0, **r,
    } for r in rows])


def _estoque(rows):
    # infer_column_roles exige "last_movement" p/ QUALQUER detector de Estoque (papel
    # obrigatório em _ESTOQUE_REQUIRED_ROLES), mesmo quando o detector em si não usa a
    # data — mantém as fixtures deste arquivo alinhadas a esse contrato.
    return pd.DataFrame([{"data_ultimo_mov": pd.Timestamp(datetime(2026, 1, 1)), **r} for r in rows])


# ---------------------------------------------------------------------- Algoritmo 1


def test_gmroi_by_sku_flags_high_markup_slow_turnover():
    vendas = _sales([
        {"product": "OPT-01", "customer": "C1", "value": 200.0, "entry_cost": 50.0, "category": "armacao"},
        {"product": "OPT-01", "customer": "C2", "value": 200.0, "entry_cost": 50.0, "category": "armacao"},
    ])
    estoque = _estoque([
        {"sku": "OPT-01", "custo_unit": 50.0, "qtd_atual": 500.0, "categoria": "armacao"},
    ])
    alerts = detect_gmroi_by_sku(vendas, estoque, THRESHOLDS)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.sku == "OPT-01"
    assert a.markup_pct == pytest.approx(75.0)
    assert a.capital_frozen == pytest.approx(25000.0)
    assert a.gmroi < THRESHOLDS.gmroi_sku_low_ratio
    assert a.is_illusory_margin is True


def test_gmroi_by_sku_ignores_healthy_turnover():
    vendas = _sales([
        {"product": "OPT-02", "customer": "C1", "value": 200.0, "entry_cost": 50.0, "category": "armacao"},
    ])
    estoque = _estoque([
        {"sku": "OPT-02", "custo_unit": 50.0, "qtd_atual": 1.0, "categoria": "armacao"},
    ])
    assert detect_gmroi_by_sku(vendas, estoque, THRESHOLDS) == []


def test_gmroi_by_sku_ignores_zero_capital():
    vendas = _sales([
        {"product": "OPT-03", "customer": "C1", "value": 200.0, "entry_cost": 50.0, "category": "armacao"},
    ])
    estoque = _estoque([
        {"sku": "OPT-03", "custo_unit": 50.0, "qtd_atual": 0.0, "categoria": "armacao"},
    ])
    assert detect_gmroi_by_sku(vendas, estoque, THRESHOLDS) == []


def test_gmroi_by_sku_no_estoque_sheet_degrades_gracefully():
    vendas = _sales([
        {"product": "OPT-01", "customer": "C1", "value": 200.0, "entry_cost": 50.0, "category": "armacao"},
    ])
    assert detect_gmroi_by_sku(vendas, None, THRESHOLDS) == []
    assert detect_gmroi_by_sku(vendas, pd.DataFrame(), THRESHOLDS) == []


# ---------------------------------------------------------------------- Algoritmo 2


def test_attach_rate_finds_cross_sell_gap():
    df = _sales([
        {"product": "LENTE", "customer": "C1", "value": 300.0, "category": "lente"},
        {"product": "LENTE", "customer": "C2", "value": 100.0, "category": "lente"},
        {"product": "LENTE", "customer": "C3", "value": 500.0, "category": "lente"},
        {"product": "SOLAR", "customer": "C1", "value": 400.0, "category": "solar"},
    ])
    result = detect_attach_rate_opportunities(df, THRESHOLDS)
    assert len(result) == 1
    finding = result[0]
    assert finding.eligible_customers == 3
    assert finding.attach_rate_pct == pytest.approx(100.0 / 3.0)
    gap_ids = {c.customer_id for c in finding.cross_sell_gap}
    assert gap_ids == {"C2", "C3"}
    # ordenado por receita na âncora, maior primeiro
    assert finding.cross_sell_gap[0].customer_id == "C3"


def test_attach_rate_no_category_column_degrades_gracefully():
    df = _sales([{"product": "X", "customer": "C1", "value": 10.0}])
    assert detect_attach_rate_opportunities(df, THRESHOLDS) == []


def test_attach_rate_caps_gap_list_at_five():
    rows = [
        {"product": "LENTE", "customer": f"C{i}", "value": float(100 - i), "category": "lente"}
        for i in range(8)
    ]
    df = _sales(rows)
    result = detect_attach_rate_opportunities(df, THRESHOLDS)
    assert len(result[0].cross_sell_gap) == 5


# ---------------------------------------------------------------------- Algoritmo 3


def test_seller_corrosion_flags_outlier_discount():
    # loja L1: 6 vendedores praticam preço de tabela (0% de desconto); 1 dá desconto
    # pesado. Com n=7 e (n-1) pares em 0%, o z-score populacional do outlier é
    # sqrt(n-1) ≈ 2.45 — folgadamente acima do corte de 2 desvios-padrão (com n
    # pequeno demais o z-score máximo possível fica <= 2 e o teste nunca dispara).
    normais = [
        {"product": "SKU-A", "customer": f"C{i}", "value": 100.0, "salesperson": f"V-0{i}", "store": "L1"}
        for i in range(1, 7)
    ]
    outlier = [
        {"product": "SKU-A", "customer": "C9", "value": 20.0, "salesperson": "V-07", "store": "L1"},
    ]
    vendas = _sales(normais + outlier)
    estoque = _estoque([{"sku": "SKU-A", "custo_unit": 5.0, "qtd_atual": 10.0, "preco_venda": 100.0}])
    alerts = detect_seller_margin_corrosion(vendas, estoque, THRESHOLDS)
    by_seller = {a.salesperson: a for a in alerts}
    assert by_seller["V-01"].is_corrosive is False
    assert by_seller["V-07"].is_corrosive is True
    assert by_seller["V-07"].discount_pct > by_seller["V-01"].discount_pct


def test_seller_corrosion_no_list_price_degrades_gracefully():
    vendas = _sales([
        {"product": "SKU-A", "customer": "C1", "value": 100.0, "salesperson": "V-01", "store": "L1"},
    ])
    estoque = _estoque([{"sku": "SKU-A", "custo_unit": 30.0, "qtd_atual": 10.0}])
    assert detect_seller_margin_corrosion(vendas, estoque, THRESHOLDS) == []


def test_seller_corrosion_no_salesperson_column_degrades_gracefully():
    vendas = _sales([{"product": "SKU-A", "customer": "C1", "value": 100.0, "store": "L1"}])
    estoque = _estoque([{"sku": "SKU-A", "custo_unit": 30.0, "qtd_atual": 10.0, "preco_venda": 100.0}])
    assert detect_seller_margin_corrosion(vendas, estoque, THRESHOLDS) == []


# ---------------------------------------------------------------------- Algoritmo 4


def test_vip_concentration_flags_single_seller_dominance():
    rows = []
    # 10 clientes na loja L1: C1 é o VIP isolado (top 20% => 2 clientes: C1 e C2)
    for i in range(1, 11):
        rows.append({
            "product": "P", "customer": f"C{i}", "value": 1000.0 if i <= 2 else 50.0,
            "salesperson": "V-CONCENTRADO" if i <= 2 else f"V-{i}", "store": "L1",
        })
    df = _sales(rows)
    alerts = detect_vip_concentration_risk(df, THRESHOLDS)
    concentrado = [a for a in alerts if a.salesperson == "V-CONCENTRADO"]
    assert len(concentrado) == 1
    assert concentrado[0].is_high_risk is True
    assert concentrado[0].concentration_pct == pytest.approx(100.0)


def test_vip_concentration_no_store_column_degrades_gracefully():
    df = _sales([{"product": "P", "customer": "C1", "value": 10.0, "salesperson": "V-01"}])
    assert detect_vip_concentration_risk(df, THRESHOLDS) == []


def test_vip_concentration_excludes_pseudo_customer():
    rows = [
        {"product": "P", "customer": "SEM_CADASTRO", "value": 100000.0, "salesperson": "V-01", "store": "L1"},
        {"product": "P", "customer": "C1", "value": 100.0, "salesperson": "V-02", "store": "L1"},
    ]
    df = _sales(rows)
    alerts = detect_vip_concentration_risk(df, THRESHOLDS)
    assert all(a.salesperson != "V-01" for a in alerts) or not alerts


# ---------------------------------------------------------------------- Algoritmo 5


def test_follow_on_conversion_counts_strict_later_product_purchase():
    df = pd.DataFrame([
        {"date": pd.Timestamp(datetime(2026, 1, 1)), "customer": "C1", "category": "servico", "value": 50.0, "product": "CONSERTO"},
        {"date": pd.Timestamp(datetime(2026, 2, 1)), "customer": "C1", "category": "armacao", "value": 300.0, "product": "OPT-01"},
        {"date": pd.Timestamp(datetime(2026, 1, 1)), "customer": "C2", "category": "servico", "value": 50.0, "product": "CONSERTO"},
        # C2 nunca volta -> sem follow-on
        {"date": pd.Timestamp(datetime(2026, 1, 1)), "customer": "C3", "category": "armacao", "value": 300.0, "product": "OPT-01"},
        # C3 não iniciou por serviço -> fora da base
    ])
    rate = detect_follow_on_conversion(df, THRESHOLDS)
    assert rate == pytest.approx(0.5)


def test_follow_on_conversion_no_service_category_returns_none():
    df = pd.DataFrame([
        {"date": pd.Timestamp(datetime(2026, 1, 1)), "customer": "C1", "category": "armacao", "value": 300.0, "product": "OPT-01"},
    ])
    assert detect_follow_on_conversion(df, THRESHOLDS) is None


def test_follow_on_conversion_no_category_column_returns_none():
    df = pd.DataFrame([
        {"date": pd.Timestamp(datetime(2026, 1, 1)), "customer": "C1", "value": 300.0, "product": "OPT-01"},
    ])
    assert detect_follow_on_conversion(df, THRESHOLDS) is None


def test_follow_on_conversion_same_day_purchase_does_not_count():
    df = pd.DataFrame([
        {"date": pd.Timestamp(datetime(2026, 1, 1)), "customer": "C1", "category": "servico", "value": 50.0, "product": "CONSERTO"},
        {"date": pd.Timestamp(datetime(2026, 1, 1)), "customer": "C1", "category": "armacao", "value": 300.0, "product": "OPT-01"},
    ])
    rate = detect_follow_on_conversion(df, THRESHOLDS)
    assert rate == pytest.approx(0.0)

"""
Testes de regressão — Fase D2, D1.0: nome legível de SKU exportado do motor
(papel opcional `description` em Estoque), consumido por `dead_stock.sku_descriptions`
e `DiscrepancyTriageItem.sku_description`. Fallback honesto: sem a coluna, ou SKU
fora do catálogo, o campo fica `None`/vazio — nunca inventa nome.
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from product_b.oracle.commercial_auditor import (
    detect_dead_stock, detect_discrepancy_triage,
)
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

THRESHOLDS = AuditThresholdsConfig()
D0 = datetime(2026, 6, 1)


# ---------------------------------------------------------------- dead_stock


def test_dead_stock_carries_readable_description():
    estoque = pd.DataFrame([
        {"sku": "SOL-030", "descricao": "Óculos Solar Polarizado A", "custo_unit": 93.80,
         "qtd_atual": 27.0, "ultima_movimentacao_data": D0 - timedelta(days=280)},
        {"sku": "VIVO-01", "descricao": "Girando", "custo_unit": 50.0, "qtd_atual": 10.0,
         "ultima_movimentacao_data": D0},
    ])
    findings = detect_dead_stock(estoque, THRESHOLDS)
    assert findings[0].sku_descriptions == {"SOL-030": "Óculos Solar Polarizado A"}


def test_dead_stock_carries_per_sku_capital_and_months_since():
    estoque = pd.DataFrame([
        {"sku": "SOL-030", "descricao": "Óculos Solar Polarizado A", "custo_unit": 100.0,
         "qtd_atual": 10.0, "ultima_movimentacao_data": D0 - timedelta(days=270)},  # 9 meses
        {"sku": "SOL-031", "descricao": "Óculos Solar Polarizado B", "custo_unit": 50.0,
         "qtd_atual": 4.0, "ultima_movimentacao_data": D0 - timedelta(days=330)},  # 11 meses
        {"sku": "VIVO-01", "descricao": "Girando", "custo_unit": 20.0, "qtd_atual": 5.0,
         "ultima_movimentacao_data": D0},
    ])
    findings = detect_dead_stock(estoque, THRESHOLDS)
    f = findings[0]
    assert f.sku_capital == {"SOL-030": pytest.approx(1000.0), "SOL-031": pytest.approx(200.0)}
    assert f.sku_months_since["SOL-030"] >= 8 and f.sku_months_since["SOL-031"] >= 8
    assert f.sku_months_since["SOL-031"] > f.sku_months_since["SOL-030"]  # mais tempo parado
    # identidade que o validador (D3) vai conferir: soma por SKU == agregado
    assert sum(f.sku_capital.values()) == pytest.approx(f.capital_frozen)


def test_dead_stock_sku_capital_sums_across_multiple_stores():
    """SKU parado em 2 lojas -> capital somado, nunca sobrescrito."""
    estoque = pd.DataFrame([
        {"sku": "DEAD-01", "custo_unit": 100.0, "qtd_atual": 5.0,
         "ultima_movimentacao_data": D0 - timedelta(days=300)},
        {"sku": "DEAD-01", "custo_unit": 100.0, "qtd_atual": 3.0,
         "ultima_movimentacao_data": D0 - timedelta(days=300)},
        {"sku": "VIVO-01", "custo_unit": 20.0, "qtd_atual": 5.0, "ultima_movimentacao_data": D0},
    ])
    findings = detect_dead_stock(estoque, THRESHOLDS)
    assert findings[0].sku_capital == {"DEAD-01": pytest.approx(800.0)}  # (5+3)*100


def test_dead_stock_without_description_column_falls_back_honestly():
    estoque = pd.DataFrame([
        {"sku": "SOL-030", "custo_unit": 93.80, "qtd_atual": 27.0,
         "ultima_movimentacao_data": D0 - timedelta(days=280)},
        {"sku": "VIVO-01", "custo_unit": 50.0, "qtd_atual": 10.0, "ultima_movimentacao_data": D0},
    ])
    findings = detect_dead_stock(estoque, THRESHOLDS)
    assert findings[0].sku_descriptions == {}
    assert findings[0].skus == ["SOL-030"]  # o achado em si não é afetado


def test_dead_stock_description_never_drops_sku_when_description_blank():
    """Descrição ausente numa linha específica não pode derrubar o SKU do estoque
    morto — nome é decoração, não pré-requisito do cálculo."""
    estoque = pd.DataFrame([
        {"sku": "SOL-030", "descricao": None, "custo_unit": 93.80, "qtd_atual": 27.0,
         "ultima_movimentacao_data": D0 - timedelta(days=280)},
        {"sku": "VIVO-01", "descricao": "Girando", "custo_unit": 50.0, "qtd_atual": 10.0,
         "ultima_movimentacao_data": D0},
    ])
    findings = detect_dead_stock(estoque, THRESHOLDS)
    assert findings[0].skus == ["SOL-030"]
    assert findings[0].sku_descriptions == {}


# ------------------------------------------------------------ discrepancy_triage


def _sales(rows):
    return pd.DataFrame([{"date": D0, "quantity": 1.0, "source_row": i + 2, "entry_cost": None, **r}
                          for i, r in enumerate(rows)])


def test_triage_item_carries_readable_description():
    vendas = _sales([
        {"product": "ARP-013", "customer": "C1", "value": 300.0, "entry_cost": 320.0,
         "salesperson": "V-01", "store": "L1"},
    ])
    estoque = pd.DataFrame([
        {"sku": "ARP-013", "descricao": "Armação Grife Titânio", "custo_unit": 150.0,
         "qtd_atual": 5.0, "preco_venda": 890.0, "data_ultimo_mov": D0},
    ])
    compras = pd.DataFrame([{"data": D0 - timedelta(days=10), "sku": "ARP-013", "custo_unit": 150.0, "qtd": 3}])
    triage = detect_discrepancy_triage(vendas, estoque, compras, [], THRESHOLDS)
    assert triage.triggered_count == 1
    item = (triage.auto_classified + triage.manual_queue)[0]
    assert item.sku_description == "Armação Grife Titânio"


def test_triage_item_description_none_when_sku_not_in_catalog():
    vendas = _sales([
        {"product": "SKU-FORA-DO-CATALOGO", "customer": "C1", "value": 30.0, "entry_cost": 100.0,
         "salesperson": "V-01", "store": "L1"},
    ])
    triage = detect_discrepancy_triage(vendas, None, None, [], THRESHOLDS)
    item = (triage.auto_classified + triage.manual_queue)[0]
    assert item.sku_description is None

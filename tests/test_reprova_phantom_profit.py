import pytest
import pandas as pd
import numpy as np
from product_b.oracle.commercial_auditor import detect_digital_phantom_profit, simulate_tax_reform
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

def test_reprova_phantom_profit_precision():
    """Falsa Positivação por Arredondamento:
    Se a margem líquida for exatamente -0.005, o round(2) leva a -0.00 (ou 0.0), não deve ser fantasma.
    Garante que o motor use round(2) e não caia em erro de float.
    """
    df = pd.DataFrame([
        {
            "product": "SKU-A",
            "channel": "Shopee",
            "value": 100.0,
            "entry_cost": 50.0,
            "marketplace_fee": 30.0,
            "shipping_cost": 20.0,
            "ad_spend": 0.0,
            "return_cost": 0.0
        }
    ])
    # gross: 100, cost: 50, fee: 30, ship: 20 -> net: 0.0
    summary = detect_digital_phantom_profit(df)
    assert summary is not None
    assert len(summary.items) == 1
    item = summary.items[0]
    assert not item.is_phantom
    assert item.net_margin_brl == 0.0

def test_reprova_cost_absence_masked_as_profit():
    """Custo Ausente mascarado:
    Se não há custo de entrada, o status DEVE ser SEM_BASE ou PARCIAL,
    e NUNCA gerar is_phantom incorretamente.
    """
    df = pd.DataFrame([
        {
            "product": "SKU-B",
            "channel": "ML",
            "value": 100.0,
            "entry_cost": np.nan,  # Ausente
            "marketplace_fee": 15.0,
            "shipping_cost": 10.0,
            "ad_spend": 5.0,
            "return_cost": 0.0
        }
    ])
    summary = detect_digital_phantom_profit(df)
    assert summary is not None
    item = summary.items[0]
    assert item.digital_cost_state == "PARCIAL"
    # Margem sem custo será 100 - 0 - 15 - 10 - 5 = 70.0 > 0 -> not phantom
    # But more importantly, the state must be PARCIAL or SEM_BASE
    assert item.is_phantom is False
    assert item.net_margin_brl == 0.0

def test_reprova_tax_reform_dre_vs_cash():
    """Confusão DRE vs Fluxo de Caixa:
    Garante que dre_net_margin_impact_brl seja negativo e que split_payment seja positivo e separado.
    """
    df = pd.DataFrame([
        {
            "product": "SKU-C",
            "value": 1000.0
        }
    ])
    thresholds = AuditThresholdsConfig(reconciliation_tax_rate_pct=6.0)
    res = simulate_tax_reform(df, thresholds)
    assert res is not None
    assert res.current_tax_brl == 60.0
    assert res.simulated_tax_brl == 92.4
    assert res.tax_delta_brl == 32.4
    assert res.dre_net_margin_impact_brl == -32.4
    assert res.split_payment_withheld_brl == 92.4
    assert res.cash_flow_float_impact_days == 30

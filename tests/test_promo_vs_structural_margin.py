"""
Testes de regressão — C3 (falso-positivo PROMO): margem de contribuição negativa
causada por promoção DELIBERADA (`forma_pagto=promocao`) não é prejuízo estrutural.

Regra (Gabarito v3, "o que o motor NÃO pode marcar"): PROMO-001 aparece com margem
de contribuição negativa (preço 15,90 cobre o custo, mas não os 15% variáveis),
porém é decisão comercial — o alerta deve vir MARCADO `promotional=True` e ficar
FORA de `total_operational_loss` no sumário executivo. Produto no vermelho com
pagamento normal (NEG-001..003) continua estrutural (`promotional=False`).

Conservador por construção: basta UMA venda não-promocional para o produto voltar a
ser tratado como estrutural — promoção nunca vira tapete para prejuízo real.
"""
from datetime import datetime

import pandas as pd

from product_b.oracle.commercial_auditor import (
    build_executive_summary, detect_contribution_margin,
)
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

THRESHOLDS = AuditThresholdsConfig()


def _sales_df(rows):
    return pd.DataFrame([{
        "date": pd.Timestamp(datetime(2026, 1, 1)), "customer": "C-001",
        "category": "armacao", "store": "L1", "salesperson": "V-01",
        **r,
    } for r in rows])


def test_promo_only_product_is_flagged_promotional():
    df = _sales_df([
        {"product": "PROMO-001", "value": 200.0, "entry_cost": 190.0,
         "payment_method": "promocao"},
        {"product": "PROMO-001", "value": 200.0, "entry_cost": 190.0,
         "payment_method": "promocao"},
    ])
    alerts = detect_contribution_margin(df, THRESHOLDS)
    assert len(alerts) == 1
    assert alerts[0].promotional is True


def test_structural_negative_margin_stays_structural():
    df = _sales_df([
        {"product": "NEG-001", "value": 200.0, "entry_cost": 190.0,
         "payment_method": "cartao"},
    ])
    alerts = detect_contribution_margin(df, THRESHOLDS)
    assert len(alerts) == 1
    assert alerts[0].promotional is False


def test_mixed_payment_is_conservative_structural():
    df = _sales_df([
        {"product": "NEG-002", "value": 200.0, "entry_cost": 190.0,
         "payment_method": "promocao"},
        {"product": "NEG-002", "value": 200.0, "entry_cost": 190.0,
         "payment_method": "cartao"},
    ])
    alerts = detect_contribution_margin(df, THRESHOLDS)
    assert len(alerts) == 1
    assert alerts[0].promotional is False


def test_missing_payment_column_never_flags_promotional():
    df = _sales_df([
        {"product": "NEG-003", "value": 200.0, "entry_cost": 190.0},
    ])
    alerts = detect_contribution_margin(df, THRESHOLDS)
    assert len(alerts) == 1
    assert alerts[0].promotional is False


def test_executive_summary_excludes_promotional_from_operational_loss():
    df = _sales_df([
        {"product": "PROMO-001", "value": 200.0, "entry_cost": 190.0,
         "payment_method": "promocao"},
        {"product": "NEG-001", "value": 200.0, "entry_cost": 190.0,
         "payment_method": "cartao"},
    ])
    alerts = detect_contribution_margin(df, THRESHOLDS)
    structural = [a for a in alerts if not a.promotional]
    assert len(alerts) == 2 and len(structural) == 1

    summary = build_executive_summary(
        contribution_margin_alerts=alerts, dead_stock=[], churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=THRESHOLDS,
    )
    expected = sum(abs(a.contribution_margin) for a in structural)
    assert abs(summary.total_operational_loss - expected) < 0.01

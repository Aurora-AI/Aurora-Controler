# -*- coding: utf-8 -*-
"""
Testes de regressão — Fase E, E1: Risco de Evasão de Talentos.

Padrão de TDD desta casa: DataFrame sintético construído inline (mesmo estilo de
`test_seller_margin_mix_phase_d.py`), nunca a fixture xlsx real (ver
SPEC_Fase_E_Parte1_Execucao.md §3.5 — a Beta não tem gerador versionado, e as
fixtures otica_test_bom/ruim são de outra tese).
"""
from datetime import datetime

import pandas as pd
import pytest

from product_b.oracle.commercial_auditor import _ANONYMOUS_CUSTOMER, detect_seller_flight_risk
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

THRESHOLDS = AuditThresholdsConfig()


def _sales(rows):
    return pd.DataFrame([
        {"quantity": 1.0, "source_row": i + 2, **r} for i, r in enumerate(rows)
    ])


def _month_rows(salesperson, store, year, month, day, n_identified, n_anonymous, value, tag):
    date = datetime(year, month, day)
    rows = []
    for i in range(n_identified):
        rows.append({"date": date, "product": "P1", "customer": f"C{tag}{i}", "value": value,
                     "salesperson": salesperson, "store": store})
    for i in range(n_anonymous):
        rows.append({"date": date, "product": "P1", "customer": _ANONYMOUS_CUSTOMER, "value": value,
                     "salesperson": salesperson, "store": store})
    return rows


# captura: historico [80,80,70,80,90,80] (mean 80, std~6.32) -> recente [20,20,20] (mean 20)
# delta=60, sigma~9.5 >> 1.5 -> dispara
# ticket: historico [98,102,97,100,103,99] (mean~99.83, std~2.32) -> recente [60,58,62] (mean 60)
# delta~39.83, sigma~17.2 >> 1.5 -> dispara
_EVASAO_MONTHS = [
    (1, [8, 2], 98), (2, [8, 2], 102), (3, [7, 3], 97),
    (4, [8, 2], 100), (5, [9, 1], 103), (6, [8, 2], 99),
    (7, [2, 8], 60), (8, [2, 8], 58), (9, [2, 8], 62),
]


def _seller_evasao_rows(salesperson="V-EVASAO", store="L1"):
    rows = []
    for month, (n_ident, n_anon), value in _EVASAO_MONTHS:
        rows += _month_rows(salesperson, store, 2025, month, 15, n_ident, n_anon, value, f"{salesperson}m{month}")
    return rows


def _seller_estavel_rows(salesperson="V-ESTAVEL", store="L1"):
    rows = []
    for month in range(1, 10):
        rows += _month_rows(salesperson, store, 2025, month, 15, 8, 2, 100.0, f"{salesperson}m{month}")
    return rows


def test_flight_risk_dispara_com_2_pernas_e_vira_alerta():
    df = _sales(_seller_evasao_rows())
    alerts = detect_seller_flight_risk(df, None, THRESHOLDS)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.salesperson == "V-EVASAO" and a.store == "L1"
    assert set(a.risk_flags) == {"captura_em_queda", "ticket_em_queda"}
    assert a.capture_trend_pct == pytest.approx(60.0, abs=0.1)
    assert a.ticket_trend_pct == pytest.approx(39.83, abs=0.1)
    assert a.discount_trend_pp is None  # sem Estoque, perna nunca avaliada
    assert a.months_evaluated == 9
    assert a.carteira_em_risco_brl == pytest.approx(sum(v * 10 for _, _, v in _EVASAO_MONTHS))


def test_flight_risk_vendedor_estavel_nao_dispara():
    df = _sales(_seller_estavel_rows())
    alerts = detect_seller_flight_risk(df, None, THRESHOLDS)
    assert alerts == []


def test_flight_risk_vendedor_em_rampa_nunca_entra_mesmo_com_dado_dramatico():
    # só 2 meses de tenure (dias) — nunca vira achado, mesmo que os números
    # (se avaliados) disparariam todas as pernas.
    rows = []
    for month, (n_ident, n_anon), value in [(8, (9, 1), 100.0), (9, (1, 9), 20.0)]:
        rows += _month_rows("V-RAMPA", "L1", 2025, month, 15, n_ident, n_anon, value, f"rampa{month}")
    df = _sales(rows)
    alerts = detect_seller_flight_risk(df, None, THRESHOLDS)
    assert alerts == []


def test_flight_risk_uma_perna_so_nao_vira_alerta():
    # só captura cai (ticket e desconto não avaliados/não disparam) -> 1 flag < min_flags=2
    rows = []
    for month, n_ident_anon in zip(range(1, 10), [(8, 2)] * 6 + [(2, 8)] * 3):
        n_ident, n_anon = n_ident_anon
        rows += _month_rows("V-UMAFLAG", "L1", 2025, month, 15, n_ident, n_anon, 100.0, f"umaflag{month}")
    df = _sales(rows)
    alerts = detect_seller_flight_risk(df, None, THRESHOLDS)
    assert alerts == []


def test_flight_risk_menos_de_3_meses_de_historico_nao_avalia_perna():
    # 5 meses total (janela=3 recente + só 2 de histórico, < 3 exigido) — tenure em
    # dias É suficiente (mais de 180), mas a perna não tem base estatística.
    rows = []
    for month, (n_ident, n_anon) in zip(range(1, 6), [(8, 2), (8, 2), (2, 8), (2, 8), (2, 8)]):
        rows += _month_rows("V-POUCOMES", "L1", 2024, month, 15, n_ident, n_anon, 100.0, f"poucomes{month}")
    df = _sales(rows)
    alerts = detect_seller_flight_risk(df, None, THRESHOLDS)
    assert alerts == []


def test_flight_risk_desconto_dispara_com_estoque():
    # historico desconto baixo e estável, recente sobe forte -> perna 2 dispara
    # (junto com captura, que também cai) -> 2 flags -> alerta.
    rows = []
    prices = [10.0, 12.0, 9.0, 11.0, 13.0, 10.0, 40.0, 42.0, 38.0]  # desconto sobre lista de 100
    for month, (price, (n_ident, n_anon)) in enumerate(
        zip(prices, [(8, 2)] * 6 + [(2, 8)] * 3), start=1,
    ):
        rows += _month_rows("V-DESCONTO", "L1", 2025, month, 15, n_ident, n_anon, 100.0 - price, f"desc{month}")
    df = _sales(rows)
    estoque = pd.DataFrame([{"sku": "P1", "custo_unit": 50.0, "qtd_atual": 10.0, "preco_venda": 100.0,
                              "data_ultimo_mov": datetime(2025, 9, 30)}])
    alerts = detect_seller_flight_risk(df, estoque, THRESHOLDS)
    assert len(alerts) == 1
    a = alerts[0]
    assert "desconto_em_alta" in a.risk_flags
    assert a.discount_trend_pp is not None and a.discount_trend_pp > 0


def test_flight_risk_sem_coluna_vendedor_retorna_vazio():
    df = pd.DataFrame([{"date": datetime(2025, 1, 1), "product": "P1", "customer": "C1",
                         "value": 100.0, "quantity": 1.0, "store": "L1", "source_row": 2}])
    assert detect_seller_flight_risk(df, None, THRESHOLDS) == []


def test_flight_risk_sample_source_rows_respeita_teto():
    df = _sales(_seller_evasao_rows())
    alerts = detect_seller_flight_risk(df, None, AuditThresholdsConfig(provenance_sample_cap=5))
    assert len(alerts[0].sample_source_rows) == 5

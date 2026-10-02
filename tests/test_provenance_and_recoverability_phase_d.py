"""
Testes de regressão — Fase D, Pilares 2 e 3:

Pilar 2 (Chave de Rastreabilidade) — todo achado material carrega a linha de origem
no arquivo do cliente (`source_rows`/`sku_source_rows`/`sample_source_rows`), nunca
só um cálculo abstrato.

Pilar 3 (Índice de Recuperabilidade) — a fila de churn ordena por
dias-em-silêncio ÷ cadência PRÓPRIA do cliente (`silence_to_cycle_ratio`), não
cruamente por R$ histórico: um cliente de ciclo curto recém-silenciado é lead mais
quente que um cliente de ciclo longo silente há muito mais tempo em absoluto.
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from product_b.oracle.commercial_auditor import (
    detect_churn, detect_dead_stock, detect_seller_margin_corrosion, detect_seller_margin_mix,
)
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

THRESHOLDS = AuditThresholdsConfig()
D0 = datetime(2026, 6, 1)


# ---------------------------------------------------------------- Pilar 2: churn


def _churn_sales(customer, dates, source_row_start, value=100.0):
    return [
        {"date": d, "customer": customer, "product": "P", "value": value, "source_row": source_row_start + i}
        for i, d in enumerate(dates)
    ]


def test_churn_finding_carries_source_rows():
    dates = [D0 - timedelta(days=x) for x in (300, 250, 200)]  # cadência ~50d
    rows = _churn_sales("Client_A", dates, source_row_start=10)
    # âncora: outro cliente com compra recente — sem isso, a última compra do
    # Client_A vira o "hoje" do dataset (auto-referência) e months_silent fica 0.
    rows += _churn_sales("Client_Anchor", [D0], source_row_start=90)
    df = pd.DataFrame(rows)
    findings = {f.customer_id: f for f in detect_churn(df, THRESHOLDS)}
    assert findings["Client_A"].source_rows == [10, 11, 12]


# ------------------------------------------------------------ Pilar 3: recuperabilidade


def _cadence_sales(customer, cadence_days, days_since_last, source_row_start, value=100.0):
    """3 compras espaçadas por `cadence_days`, a última há `days_since_last` dias de D0."""
    offsets = [days_since_last + 2 * cadence_days, days_since_last + cadence_days, days_since_last]
    return [
        {"date": D0 - timedelta(days=o), "customer": customer, "product": "P", "value": value,
         "source_row": source_row_start + i}
        for i, o in enumerate(offsets)
    ]


def test_short_cycle_recent_churn_is_hotter_than_long_cycle_old_churn():
    """O caso do usuário: cliente de ciclo curto que acabou de estourar o PRÓPRIO
    ritmo (ratio menor) é lead mais quente que cliente de ciclo longo silente há
    muito mais tempo em absoluto — mesmo tendo MENOS R$ histórico. Os dois precisam
    limpar os 2 gates de detecção de churn (>=3 compras, silêncio > 2x a própria
    cadência E >=3 meses) pra sequer aparecerem na fila — por isso os números aqui
    não são arbitrários, foram calibrados pra cruzar ambos os gates."""
    quente = _cadence_sales("Client_Quente", cadence_days=30, days_since_last=70,
                             source_row_start=100, value=50.0)
    frio = _cadence_sales("Client_Frio", cadence_days=100, days_since_last=350,
                           source_row_start=200, value=500.0)
    ancora = _cadence_sales("Client_Anchor", cadence_days=10, days_since_last=0, source_row_start=900)
    df = pd.DataFrame(quente + frio + ancora)
    findings = {f.customer_id: f for f in detect_churn(df, THRESHOLDS)}

    assert findings["Client_Quente"].silence_to_cycle_ratio == pytest.approx(2.33, abs=0.02)
    assert findings["Client_Frio"].silence_to_cycle_ratio == pytest.approx(3.5, abs=0.02)
    # a inversão que só o índice revela: o de MENOS R$ é o lead mais quente
    assert findings["Client_Quente"].silence_to_cycle_ratio < findings["Client_Frio"].silence_to_cycle_ratio
    assert findings["Client_Quente"].historical_annual_value < findings["Client_Frio"].historical_annual_value

    ordenado_por_calor = sorted(findings.values(), key=lambda f: f.silence_to_cycle_ratio)
    ordenado_por_dinheiro = sorted(findings.values(), key=lambda f: -f.historical_annual_value)
    assert [f.customer_id for f in ordenado_por_calor] != [f.customer_id for f in ordenado_por_dinheiro]


# ---------------------------------------------------------------- Pilar 2: estoque


def test_dead_stock_carries_sku_source_rows():
    estoque = pd.DataFrame([
        {"sku": "DEAD-01", "descricao": "Parado", "custo_unit": 100.0, "qtd_atual": 5.0,
         "ultima_movimentacao_data": D0 - timedelta(days=300)},
        {"sku": "VIVO-01", "descricao": "Girando", "custo_unit": 50.0, "qtd_atual": 10.0,
         "ultima_movimentacao_data": D0 - timedelta(days=1)},
    ])
    findings = detect_dead_stock(estoque, THRESHOLDS)
    assert len(findings) == 1
    # header + 1-index: linha 0 do DataFrame -> linha 2 do arquivo
    assert findings[0].sku_source_rows == {"DEAD-01": [2]}


def test_dead_stock_same_sku_multiple_rows_never_overwrites():
    """SKU parado em 2 lojas -> as 2 linhas de origem, nunca só a última (dict
    sobrescrito seria perda silenciosa de procedência)."""
    estoque = pd.DataFrame([
        {"sku": "DEAD-01", "descricao": "Parado L1", "custo_unit": 100.0, "qtd_atual": 5.0,
         "ultima_movimentacao_data": D0 - timedelta(days=300)},
        {"sku": "DEAD-01", "descricao": "Parado L2", "custo_unit": 100.0, "qtd_atual": 3.0,
         "ultima_movimentacao_data": D0 - timedelta(days=300)},
        # âncora: item com movimento recente — sem isso, as 2 linhas paradas viram
        # o próprio "hoje" do estoque (auto-referência) e months_since fica 0.
        {"sku": "VIVO-01", "descricao": "Girando", "custo_unit": 50.0, "qtd_atual": 10.0,
         "ultima_movimentacao_data": D0},
    ])
    findings = detect_dead_stock(estoque, THRESHOLDS)
    assert findings[0].sku_source_rows == {"DEAD-01": [2, 3]}


# ---------------------------------------------------------- Pilar 2: vendedores


def _seller_rows(salesperson, store, n, source_row_start, value=100.0, entry_cost=50.0):
    return [
        {"date": D0, "product": "SKU-A", "customer": f"C{i}", "value": value, "entry_cost": entry_cost,
         "salesperson": salesperson, "store": store, "quantity": 1.0, "source_row": source_row_start + i}
        for i in range(n)
    ]


def test_seller_margin_corrosion_carries_sample_source_rows():
    rows = _seller_rows("V-01", "L1", n=3, source_row_start=50, value=80.0)
    vendas = pd.DataFrame(rows)
    estoque = pd.DataFrame([
        {"sku": "SKU-A", "custo_unit": 50.0, "qtd_atual": 5.0, "preco_venda": 100.0,
         "data_ultimo_mov": D0},
    ])
    alerts = detect_seller_margin_corrosion(vendas, estoque, THRESHOLDS)
    assert len(alerts) == 1
    assert alerts[0].sample_source_rows == [50, 51, 52]


def test_provenance_sample_is_capped():
    n = THRESHOLDS.provenance_sample_cap + 15
    rows = _seller_rows("V-01", "L1", n=n, source_row_start=1000, value=80.0)
    vendas = pd.DataFrame(rows)
    estoque = pd.DataFrame([
        {"sku": "SKU-A", "custo_unit": 50.0, "qtd_atual": 5.0, "preco_venda": 100.0,
         "data_ultimo_mov": D0},
    ])
    alerts = detect_seller_margin_corrosion(vendas, estoque, THRESHOLDS)
    assert alerts[0].sample_size == n  # total real preservado
    assert len(alerts[0].sample_source_rows) == THRESHOLDS.provenance_sample_cap  # amostra, não a lista inteira


def test_seller_margin_mix_carries_sample_source_rows():
    rows = _seller_rows("V-01", "L1", n=THRESHOLDS.seller_margin_mix_min_sample, source_row_start=700)
    for r in rows:
        r["category"] = "armacao"
    vendas = pd.DataFrame(rows)
    profiles = detect_seller_margin_mix(vendas, THRESHOLDS)
    assert len(profiles) == 1
    assert profiles[0].sample_source_rows[0] == 700
    assert len(profiles[0].sample_source_rows) <= THRESHOLDS.provenance_sample_cap

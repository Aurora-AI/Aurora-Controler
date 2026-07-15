"""
Testes de regressão — Bloco D, item D1 (macro) da spec de goal-loop v2
(docs/os/exrs-v2-goal-loop/SPEC.md): P&L por loja + ranking por margem de
contribuição real.

Lógica GERAL, não gabarito: nenhum destes testes lê a aba Gabarito nem crava nome de
loja específico ("L7 - Oeste" etc.) como resultado esperado — o agrupamento é
dinâmico (groupby sobre o que existir no dado). Os testes com `consultoria_real_test`
verificam apenas a FORMA da asserção (existe >=1 loja de volume alto com margem
negativa, os dois rankings divergem, o R$ mascarado bate com a soma das margens
negativas) recalculada a partir do próprio artefato, nunca um valor cravado em
duplicata. O teste sintético usa nomes de loja fabricados só para verificar a
ARITMÉTICA do detector, isolado de qualquer fixture real.
"""
from pathlib import Path

import pandas as pd

from product_b.oracle.commercial_auditor import (
    _records_to_frame, build_store_macro_summary, detect_store_performance,
    load_named_sheets, load_sales_records, run_audit,
)
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"
NO_STORE_FIXTURE = Path(__file__).parent / "fixtures" / "sales_history_test.xlsx"


# ── Aritmética isolada (sintética, sem depender de nenhuma fixture real) ────────────

def _synthetic_df() -> pd.DataFrame:
    """2 lojas fabricadas: 'Loja Saudavel' (preço >> custo) e 'Loja Prejuizo' (preço <<
    custo) — só para testar a fórmula, nomes nunca aparecem em produção. Datas
    espalhadas ao longo de 6 meses (não um único dia) para que as DUAS lojas fiquem
    acima do `cold_start_min_months` padrão (D3) — este teste mede a ARITMÉTICA da
    margem, isolado da rotulagem de cold-start (que tem teste dedicado em
    test_store_coldstart.py)."""
    rows = []
    dates = pd.date_range("2025-01-01", periods=10, freq="18D")  # ~5.6 meses de span
    for i in range(10):
        rows.append({
            "date": dates[i], "product": "P1", "customer": f"C{i}",
            "value": 100.0, "entry_cost": 40.0, "category": None, "store": "Loja Saudavel",
        })
    for i in range(10):
        rows.append({
            "date": dates[i], "product": "P2", "customer": f"C{i}",
            "value": 50.0, "entry_cost": 60.0, "category": None, "store": "Loja Prejuizo",
        })
    return pd.DataFrame(rows)


def test_detect_store_performance_computes_same_formula_as_contribution_margin():
    thresholds = AuditThresholdsConfig(variable_cost_pct=15.0)
    df = _synthetic_df()
    entries = detect_store_performance(df, thresholds)
    assert {e.store for e in entries} == {"Loja Saudavel", "Loja Prejuizo"}

    saudavel = next(e for e in entries if e.store == "Loja Saudavel")
    # Preço médio 100, custo médio 40, variável 15% de 100 = 15 -> margem = 45.
    assert abs(saudavel.contribution_margin_avg - 45.0) < 1e-6
    assert abs(saudavel.contribution_margin_total - 450.0) < 1e-6
    assert saudavel.gross_revenue == 1000.0
    assert saudavel.margin_sample_size == 10

    prejuizo = next(e for e in entries if e.store == "Loja Prejuizo")
    # Preço médio 50, custo médio 60, variável 15% de 50 = 7.5 -> margem = -17.5.
    assert abs(prejuizo.contribution_margin_avg - (-17.5)) < 1e-6
    assert abs(prejuizo.contribution_margin_total - (-175.0)) < 1e-6
    assert prejuizo.gross_revenue == 500.0


def test_store_macro_summary_masks_the_negative_stores():
    thresholds = AuditThresholdsConfig(variable_cost_pct=15.0)
    entries = detect_store_performance(_synthetic_df(), thresholds)
    summary = build_store_macro_summary(entries)
    assert summary is not None
    assert summary.stores_with_negative_margin == ["Loja Prejuizo"]
    assert abs(summary.masked_amount - 175.0) < 1e-6
    # Rede fecha positivo (450 - 175 = 275) só porque a loja saudável cobre a outra.
    assert abs(summary.network_contribution_margin_total - 275.0) < 1e-6
    # Faturamento bruto da "Loja Saudavel" é maior; ranking de margem também bate aqui
    # (caso simples de 2 lojas) — o teste de divergência real vive no dado de verdade.
    assert summary.revenue_rank[0] == "Loja Saudavel"
    assert summary.margin_rank[0] == "Loja Saudavel"


def test_detect_store_performance_returns_empty_without_a_store_column():
    """Sem papel 'loja' identificado no arquivo de origem, o detector não inventa
    loja — retorna vazio, e o resumo macro correspondente é None."""
    records, _ = load_sales_records(NO_STORE_FIXTURE)
    df = _records_to_frame(records)
    assert detect_store_performance(df, AuditThresholdsConfig()) == []
    assert build_store_macro_summary([]) is None


# ── Dado real (consultoria_real_test.xlsx) — só asserções de FORMA, nada cravado ────

def test_store_performance_procedence_matches_actual_row_counts():
    """Todo StorePerformance tem procedência: a soma de revenue_sample_size por loja
    bate com o nº de vendas efetivamente lidas do arquivo (nenhuma linha perdida ou
    duplicada na agregação)."""
    records, cleaning = load_sales_records(FIXTURE)
    report = run_audit(FIXTURE)
    assert report.store_performance, "fixture não tem coluna de loja mapeada — teste não testa nada"
    total_from_stores = sum(s.revenue_sample_size for s in report.store_performance)
    assert total_from_stores == len(records) == cleaning.rows_accepted


def test_at_least_one_high_volume_store_has_negative_real_margin():
    """D1: pelo menos uma loja com volume ALTO (definido aqui como acima da MEDIANA
    de vendas entre as lojas — nunca um nome cravado) aparece com margem de
    contribuição real negativa, mesmo a rede como um todo fechando positiva."""
    report = run_audit(FIXTURE)
    stores = report.store_performance
    assert stores, "fixture não tem coluna de loja mapeada — teste não testa nada"

    volumes = sorted(s.revenue_sample_size for s in stores)
    median_volume = volumes[len(volumes) // 2]
    high_volume_negative = [
        s for s in stores
        if s.revenue_sample_size >= median_volume and s.contribution_margin_total < 0
    ]
    assert high_volume_negative, (
        "esperava >=1 loja de volume acima da mediana com margem de contribuição real "
        "negativa (prejuízo mascarado pelo agregado saudável da rede)"
    )
    # A rede como um todo (soma de todas as lojas) segue positiva — é exatamente essa
    # mistura que o agregado "mascara".
    summary = report.store_macro_summary
    assert summary is not None
    assert summary.network_contribution_margin_total > 0


def test_margin_ranking_differs_from_revenue_ranking():
    """D1: o ranking por margem de contribuição real não é o mesmo que o ranking por
    faturamento bruto — pelo menos 1 loja muda de posição relativa."""
    report = run_audit(FIXTURE)
    summary = report.store_macro_summary
    assert summary is not None
    assert summary.rank_differs is True
    assert set(summary.revenue_rank) == set(summary.margin_rank)  # mesmo conjunto de lojas
    assert summary.revenue_rank != summary.margin_rank


def test_masked_amount_equals_sum_of_negative_store_margins():
    """D1: o R$ mascarado pelo agregado saudável é exatamente a soma (em módulo) da
    margem de contribuição real das lojas com prejuízo — recalculado aqui a partir do
    próprio artefato, não um valor cravado."""
    report = run_audit(FIXTURE)
    summary = report.store_macro_summary
    assert summary is not None
    negative_stores = [s for s in report.store_performance if s.contribution_margin_total < 0]
    assert negative_stores, "fixture não gerou nenhuma loja com margem negativa — teste não testa nada"
    expected_masked = sum(-s.contribution_margin_total for s in negative_stores)
    assert abs(summary.masked_amount - expected_masked) < 0.01
    assert summary.masked_amount > 0
    assert set(summary.stores_with_negative_margin) == {s.store for s in negative_stores}


def test_no_production_code_reads_the_gabarito_sheet():
    """Anti-overfit: o motor (src/product_b/oracle) nunca lê a aba 'Gabarito' — checagem
    indireta: rodar contra a fixture real não deve levantar exceção nem exigir a aba,
    e a aba Gabarito não é uma das séries B carregadas por load_named_sheets."""
    named_sheets = load_named_sheets(FIXTURE)
    assert "Gabarito" not in named_sheets

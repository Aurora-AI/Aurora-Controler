"""
Testes de regressão — Bloco D, item D3 da spec de goal-loop v2
(docs/os/exrs-v2-goal-loop/SPEC.md): cold-start — loja com histórico curto demais não
tem base estatística para que suas métricas sejam apresentadas como fato derivado com
a mesma confiança de uma loja madura.

Lógica GERAL, não gabarito: `detect_store_performance` calcula `months_of_history` POR
LOJA dinamicamente (groupby sobre o que existir no dado — `max(date) - min(date)` da
PRÓPRIA loja, nunca da rede) e compara contra `thresholds.cold_start_min_months`
(configurável, nunca um número mágico dentro da função). Os testes sintéticos usam
nomes de loja fabricados só para provar a ARITMÉTICA/threshold, isolados de qualquer
fixture real. O teste com `consultoria_real_test.xlsx` verifica apenas a FORMA da
asserção (existe >= 1 loja com histórico mais curto que o limiar padrão, e as lojas de
maior faturamento — descobertas rodando o código, nunca por nome — não são marcadas
cold-start) — nenhum nome de loja é cravado aqui.
"""
from pathlib import Path

import pandas as pd

from product_b.oracle.commercial_auditor import (
    build_store_macro_summary, detect_store_performance, run_audit,
)
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


# ── Aritmética isolada (sintética, sem depender de nenhuma fixture real) ────────────

def _synthetic_df_with_one_new_store() -> pd.DataFrame:
    """3 lojas fabricadas: duas maduras (~6 meses de histórico, margem positiva e
    negativa respectivamente) e uma nova (~1 mês de histórico, margem negativa — para
    provar que cold-start não vira "estrutural" no masked_amount mesmo quando a loja
    também dá prejuízo). Nomes nunca aparecem em produção."""
    rows = []
    mature_dates = pd.date_range("2025-01-01", periods=10, freq="18D")  # ~5.3 meses
    new_store_dates = pd.date_range("2025-06-01", periods=6, freq="5D")  # ~25 dias

    for i in range(10):
        rows.append({
            "date": mature_dates[i], "product": "P1", "customer": f"C{i}",
            "value": 100.0, "entry_cost": 40.0, "category": None, "store": "Loja Madura Boa",
        })
    for i in range(10):
        rows.append({
            "date": mature_dates[i], "product": "P2", "customer": f"D{i}",
            "value": 50.0, "entry_cost": 60.0, "category": None, "store": "Loja Madura Ruim",
        })
    for i in range(6):
        rows.append({
            "date": new_store_dates[i], "product": "P3", "customer": f"E{i}",
            "value": 50.0, "entry_cost": 60.0, "category": None, "store": "Loja Recem-Aberta",
        })
    return pd.DataFrame(rows)


def test_months_of_history_computed_from_store_own_date_span_not_network():
    thresholds = AuditThresholdsConfig()  # cold_start_min_months default = 4.0
    entries = detect_store_performance(_synthetic_df_with_one_new_store(), thresholds)
    by_store = {e.store: e for e in entries}

    madura_boa = by_store["Loja Madura Boa"]
    madura_ruim = by_store["Loja Madura Ruim"]
    nova = by_store["Loja Recem-Aberta"]

    assert madura_boa.months_of_history > thresholds.cold_start_min_months
    assert madura_boa.has_sufficient_history is True
    assert madura_ruim.months_of_history > thresholds.cold_start_min_months
    assert madura_ruim.has_sufficient_history is True

    # ~25 dias / 30.44 ≈ 0.82 mês — muito abaixo do limiar padrão de 4 meses.
    assert nova.months_of_history < thresholds.cold_start_min_months
    assert nova.has_sufficient_history is False
    assert 0.5 < nova.months_of_history < 1.5


def test_cold_start_threshold_is_configurable_not_hardcoded():
    """O mesmo dado sintético produz rótulos diferentes conforme o threshold injetado
    — prova que o limiar vem de AuditThresholdsConfig, não de um número cravado dentro
    da função."""
    df = _synthetic_df_with_one_new_store()

    permissive = AuditThresholdsConfig(cold_start_min_months=0.1)
    entries_permissive = detect_store_performance(df, permissive)
    assert all(e.has_sufficient_history for e in entries_permissive)

    strict = AuditThresholdsConfig(cold_start_min_months=999.0)
    entries_strict = detect_store_performance(df, strict)
    assert not any(e.has_sufficient_history for e in entries_strict)


def test_macro_summary_excludes_cold_start_from_masked_amount_but_not_from_rank_or_network_total():
    """D3: a loja nova ('Loja Recem-Aberta') também dá prejuízo, mas seu histórico
    curto demais não sustenta o rótulo de "mascaramento estrutural" — fica de fora de
    `stores_with_negative_margin`/`masked_amount`. Ainda assim aparece nos dois
    rankings e seu resultado (positivo ou negativo) continua somado ao
    `network_contribution_margin_total` (dinheiro real, fato bruto)."""
    thresholds = AuditThresholdsConfig()
    entries = detect_store_performance(_synthetic_df_with_one_new_store(), thresholds)
    summary = build_store_macro_summary(entries)
    assert summary is not None

    nova = next(e for e in entries if e.store == "Loja Recem-Aberta")
    assert nova.contribution_margin_total < 0, "fixture não gerou prejuízo na loja nova — teste não testa nada"
    madura_ruim = next(e for e in entries if e.store == "Loja Madura Ruim")
    assert madura_ruim.contribution_margin_total < 0

    # Só a loja MADURA com prejuízo entra na narrativa de mascaramento estrutural.
    assert summary.stores_with_negative_margin == ["Loja Madura Ruim"]
    assert abs(summary.masked_amount - (-madura_ruim.contribution_margin_total)) < 1e-6

    # Mas a loja nova continua nos rankings...
    assert "Loja Recem-Aberta" in summary.revenue_rank
    assert "Loja Recem-Aberta" in summary.margin_rank
    # ...e seu resultado real continua somado ao total da rede.
    expected_network_total = sum(e.contribution_margin_total for e in entries)
    assert abs(summary.network_contribution_margin_total - expected_network_total) < 1e-6


# ── Dado real (consultoria_real_test.xlsx) — só asserções de FORMA, nada cravado ────

def test_at_least_one_store_dynamically_flagged_as_cold_start_in_real_fixture():
    """D3: no dado real, pelo menos uma loja tem histórico próprio mais curto que o
    limiar padrão (4 meses) — descoberta rodando `detect_store_performance`, nunca por
    nome cravado aqui."""
    report = run_audit(FIXTURE)
    stores = report.store_performance
    assert stores, "fixture não tem coluna de loja mapeada — teste não testa nada"

    cold_start_stores = [s for s in stores if not s.has_sufficient_history]
    assert cold_start_stores, (
        "esperava >=1 loja com histórico insuficiente (< "
        f"{report.thresholds.cold_start_min_months} meses) no dado real"
    )
    for s in cold_start_stores:
        assert s.months_of_history < report.thresholds.cold_start_min_months
        # A loja continua no relatório com seus números reais — nunca removida.
        assert s.store in [x.store for x in stores]


def test_mature_high_revenue_stores_are_not_flagged_as_cold_start():
    """D3 (falso-positivo): as lojas de MAIOR faturamento da rede real — descobertas
    dinamicamente, nunca por nome — não podem ser marcadas cold-start; só histórico
    curto justifica o rótulo, não faturamento baixo nem qualquer outro critério."""
    report = run_audit(FIXTURE)
    stores = report.store_performance
    assert stores, "fixture não tem coluna de loja mapeada — teste não testa nada"

    top_revenue_stores = sorted(stores, key=lambda s: -s.gross_revenue)[:3]
    for s in top_revenue_stores:
        assert s.has_sufficient_history is True, (
            f"loja de alto faturamento {s.store!r} foi marcada cold-start "
            f"({s.months_of_history:.2f} meses) — inesperado"
        )


def test_cold_start_store_stays_in_report_not_removed_or_hidden():
    """D3: a loja cold-start não é removida do relatório nem some do groupby dinâmico
    — ela aparece com seus números reais, só rotulada (has_sufficient_history=False),
    igual ao padrão já usado em SeasonalityCurve.insufficient_data."""
    report = run_audit(FIXTURE)
    stores = report.store_performance
    cold_start_stores = [s for s in stores if not s.has_sufficient_history]
    assert cold_start_stores, "teste depende de haver >=1 loja cold-start no dado real"
    for s in cold_start_stores:
        # Continua no groupby com contagem real de vendas — nunca zerada/omitida.
        assert s.revenue_sample_size > 0
        assert s.store in report.store_macro_summary.revenue_rank
        assert s.store in report.store_macro_summary.margin_rank

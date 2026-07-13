"""
Testes de regressão — Bloco A (integridade de dado) da spec de goal-loop v2
(docs/os/exrs-v2-goal-loop/SPEC.md), itens A1 (estornos líquidos) e A2 (outlier
robusto). A3 (data robusta) já está coberta por test_column_mapper.py.

Lógica GERAL, não gabarito: nenhum destes testes lê a aba Gabarito nem crava um SKU
específico como "o outlier esperado" — os SKUs abaixo (ARP-006, ARP-001, ARM-001) são
usados só para achar as linhas no dado real e verificar a MATEMÁTICA do fix (sinal de
quantidade, razão-para-mediana), não porque o código precisa reconhecê-los.
"""
from pathlib import Path

import pandas as pd

from oracle.commercial_auditor import load_sales_records, run_audit, winsorize_outliers

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


def test_negative_quantity_lines_never_count_as_positive_revenue():
    """A1: qualquer linha com qtd<0 no arquivo real vira valor negativo, nunca
    positivo — verificação sobre TODAS as linhas negativas encontradas, não uma
    lista cravada."""
    records, _ = load_sales_records(FIXTURE)
    raw = pd.read_excel(FIXTURE, sheet_name="Vendas", dtype=str, engine="openpyxl")
    qtd = pd.to_numeric(raw["qtd"], errors="coerce")
    negative_rows = set(raw.index[qtd < 0] + 2)  # +2: 1-indexado + cabeçalho, casa com source_row
    assert negative_rows, "fixture não tem nenhuma linha de estorno — teste não testa nada"

    checked = 0
    for r in records:
        if r.source_row in negative_rows:
            assert r.value < 0, f"linha {r.source_row} (qtd<0) tem valor positivo: {r.value}"
            checked += 1
    assert checked == len(negative_rows)


def test_outlier_winsorization_uses_own_product_median_not_network_wide():
    """A2: a poda é por PRODUTO — um produto com muitas amostras e mediana alta não
    deve nunca ser podado por comparação com a rede inteira (regressão do bug pego
    pela própria fixture sintética: SOLAR-SEASONAL, ticket ~3x a mediana da rede, era
    podado por engano quando a cerca era global)."""
    from oracle.forensic_contracts import AuditThresholdsConfig
    from oracle.commercial_auditor import load_sales_records as load, _records_to_frame

    otica = Path(__file__).parent / "fixtures" / "otica_test_bom.xlsx"
    records, _ = load(otica)
    adjusted, winsorized = winsorize_outliers(records, AuditThresholdsConfig())
    solar_seasonal_capped = [w for w in winsorized if w.product == "SOLAR-SEASONAL"]
    assert not solar_seasonal_capped


def test_network_median_ticket_barely_moves_after_winsorization():
    """A2: podar os outliers reais não pode mexer materialmente na mediana da rede —
    ela já é robusta a cauda por natureza; a asserção é que winsorizar não a desloca
    além de uma tolerância pequena comparado a excluir os outliers manualmente."""
    records, _ = load_sales_records(FIXTURE)
    adjusted, winsorized = winsorize_outliers(records, __import__(
        "oracle.forensic_contracts", fromlist=["AuditThresholdsConfig"],
    ).AuditThresholdsConfig())
    assert winsorized, "fixture não gerou nenhuma poda — teste não testa nada"

    original_outlier_values = {round(w.original_value, 2) for w in winsorized}
    raw_median = pd.Series([r.value for r in records]).median()
    manually_excluded = pd.Series([
        r.value for r in records if round(r.value, 2) not in original_outlier_values
    ]).median()
    winsorized_median = pd.Series([r.value for r in adjusted]).median()

    assert manually_excluded != 0
    delta_pct = abs(winsorized_median - manually_excluded) / abs(manually_excluded) * 100.0
    assert delta_pct < 2.0
    assert raw_median != 0  # sanity: mediana bruta existe (outlier de cauda não a distorce por definição)


def test_contribution_margin_excludes_return_lines_from_average_price():
    """Consequência direta do A1: uma devolução (valor negativo) não é "uma venda a
    um preço" — não pode arrastar o preço médio de um produto pra baixo e gerar
    margem negativa artificial."""
    report = run_audit(FIXTURE)
    records, _ = load_sales_records(FIXTURE)
    return_products = {r.product for r in records if r.value < 0}
    assert return_products, "fixture não tem nenhuma linha de estorno — teste não testa nada"

    flagged_products = {c.product for c in report.contribution_margin_alerts}
    # Um produto que TEM estorno só pode aparecer como margem negativa se, mesmo
    # excluindo as linhas de estorno, a margem das vendas de verdade continuar
    # negativa — não porque a devolução contaminou a média.
    for product in return_products & flagged_products:
        real_sales = [r for r in records if r.product == product and r.value > 0 and r.entry_cost is not None]
        if not real_sales:
            continue
        avg_price = sum(r.value for r in real_sales) / len(real_sales)
        avg_cost = sum(r.entry_cost for r in real_sales) / len(real_sales)
        variable_cost = avg_price * report.thresholds.variable_cost_pct / 100.0
        assert avg_price - avg_cost - variable_cost < 0

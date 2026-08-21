"""
Golden master do laudo Beta — trava o resultado da auditoria sobre
`rede_oticas_beta_test.xlsx` (fixture adversarial de aceite, com aba Gabarito
descrevendo 7 "pegadinhas" plantadas contra o motor) contra o JSON exato validado
manualmente em 20/07/2026.

Por que existe: diferente de `consultoria_real_test.xlsx` (dado real de cliente, sem
gabarito), esta fixture foi desenhada especificamente para testar os limites do motor
— nomes de coluna diferentes (sem aba Financeiro/Vendedores; `preco_praticado`/
`preco_tabela` direto em Vendas), e 7 cenários adversariais documentados na própria
aba Gabarito do arquivo. Ela complementa (não substitui) `test_golden_laudo_v3.py`:
v3 trava contra dado real de reunião; beta trava contra um teste de aceite desenhado
para expor exatamente os edge cases que o motor precisa acertar (inclusive um
projetado contra os 3 achados corrigidos na revisão de QA da Fase C — ver
`test_discrepancy_triage_phase_c.py`).

Se este teste falhar depois de uma mudança legítima e intencional no motor (não uma
regressão), o laudo esperado precisa ser regenerado deliberadamente — nunca ajustar
o teste pra "passar", sempre confirmar que a nova saída está correta primeiro.
"""
import json
from collections import Counter
from pathlib import Path

from product_b.oracle.commercial_auditor import run_audit

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_PATH = FIXTURES / "golden_laudo_beta.json"
REAL_FIXTURE = FIXTURES / "rede_oticas_beta_test.xlsx"


def test_laudo_matches_golden_master_exactly():
    report = run_audit(REAL_FIXTURE)
    actual = report.model_dump(mode="json")
    actual.pop("generated_at", None)

    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    assert actual == expected, (
        "O laudo da rede Beta divergiu do golden master. Se a mudança no motor foi "
        "intencional, regenere tests/fixtures/golden_laudo_beta.json deliberadamente "
        "(nunca só pra fazer este teste passar) e confirme cada número novo — em "
        "especial as 7 pegadinhas da aba Gabarito do arquivo original — antes de "
        "commitar."
    )


def _triage_items(report):
    dt = report.advanced_metrics.discrepancy_triage
    return dt, {i.sku for i in dt.auto_classified + dt.manual_queue}


def test_ingestion_reads_alternate_column_names_with_zero_discard():
    """A fixture usa cabeçalhos nunca vistos antes (`quantidade`, `preco_praticado`,
    `preco_tabela` direto em Vendas, sem aba Financeiro/Vendedores) — prova que o
    mapeador de colunas generaliza, não decorou nomes de arquivo específicos."""
    report = run_audit(REAL_FIXTURE)
    assert report.cleaning.rows_read == report.cleaning.rows_accepted == 1426
    assert report.cleaning.rows_discarded_by_reason == {}
    assert report.cleaning.files_skipped == []


def test_pegadinha_1_sangria_isolada_e_below_cost_sale():
    """ARP-020/ARP-021: sangria isolada em meio a vendas normais do mesmo SKU — a
    mediana da loja fica baixa (maioria das vendas é normal), então E5 NÃO dispara e
    o veredito fica below_cost_sale puro, nunca suspected_cadastral_error."""
    report = run_audit(REAL_FIXTURE)
    dt, skus = _triage_items(report)
    below = [i for i in dt.auto_classified if i.sku in ("ARP-020", "ARP-021")]
    assert below and all(i.verdict == "below_cost_sale" for i in below)
    assert all(i.evidence.store_systemic_pattern is False for i in below)
    assert sum(len(i.source_rows) for i in below) == 20


def test_pegadinha_2_tabela_desalinhada_via_e5_padrao_sistemico():
    """LNT-900/Loja 02: 2+ vendedores reais distintos confirmam o mesmo desconto
    extremo -> E5 dispara -> suspected_cadastral_error, mesmo com below_cost=True."""
    report = run_audit(REAL_FIXTURE)
    dt, _ = _triage_items(report)
    lnt = [i for i in dt.auto_classified if i.sku == "LNT-900"]
    assert lnt and all(i.verdict == "suspected_cadastral_error" for i in lnt)
    assert all(i.evidence.store_systemic_pattern for i in lnt)


def test_pegadinha_3_vendedor_fantasma_nao_contamina_pseudo_entidade():
    """12 linhas com vendedor_id em branco viram VENDEDOR_NAO_IDENTIFICADO (pseudo-
    entidade real); 4 linhas com a STRING LITERAL '_UNKNOWN_SALESPERSON' (que só
    coincide com o NOME da constante Python, não com seu VALOR de runtime) precisam
    ser tratadas como vendedor real e distinto — nunca fundidas com a pseudo-entidade
    por uma comparação ingênua de string."""
    report = run_audit(REAL_FIXTURE)
    by_name = {sp.salesperson: sp for sp in report.salesperson_performance}
    assert by_name["VENDEDOR_NAO_IDENTIFICADO"].sample_size == 12
    assert by_name["_UNKNOWN_SALESPERSON"].sample_size == 4
    assert by_name["_UNKNOWN_SALESPERSON"] is not by_name["VENDEDOR_NAO_IDENTIFICADO"]


def test_pegadinha_4_promocao_legitima_cruza_com_estoque_morto():
    """SOL-030/031/032: forma_pagto=promocao + (SOL-030/031) em estoque morto ->
    deliberate_liquidation via E3+E2, custo sempre coberto (nunca below_cost)."""
    report = run_audit(REAL_FIXTURE)
    dt, _ = _triage_items(report)
    sol = [i for i in dt.auto_classified if i.sku in ("SOL-030", "SOL-031", "SOL-032")]
    assert sol and all(i.verdict == "deliberate_liquidation" for i in sol)
    assert all(i.evidence.is_promo_flagged and not i.evidence.below_cost for i in sol)
    assert sum(len(i.source_rows) for i in sol) == 18


def test_pegadinha_5_divergencia_custo_nf_reclassifica_para_cadastral():
    """ARP-013: custo_entrada registrado (R$320) diverge ~113% do custo real da NF
    (R$150, aba Compras) — parece sangria (below_cost), mas E4 reclassifica para
    suspected_cadastral_error: o cadastro está errado, não o vendedor."""
    report = run_audit(REAL_FIXTURE)
    dt, _ = _triage_items(report)
    arp13 = [i for i in dt.auto_classified if i.sku == "ARP-013"]
    assert arp13 and all(i.verdict == "suspected_cadastral_error" for i in arp13)
    assert all(i.evidence.cost_diverges_from_nf for i in arp13)
    assert all(i.entry_cost == 320.0 and i.nf_cost == 150.0 for i in arp13)
    assert sum(len(i.source_rows) for i in arp13) == 12


def test_pegadinha_6_estoque_morto_sol_030_031():
    report = run_audit(REAL_FIXTURE)
    assert report.dead_stock[0].skus == ["SOL-030", "SOL-031"]
    assert report.dead_stock[0].dead_stock_months == 8
    assert round(report.dead_stock[0].capital_frozen, 2) == 5101.24


def test_pegadinha_7_completude_baixa_global_dispara_contingencia():
    """Loja 02 tem telefone/CPF quase todo ausente — o detector NÃO segmenta por
    loja, então a completude GLOBAL da rede (24,8%) fica abaixo dos 30% e dispara a
    contingência, mesmo a Loja 01 tendo cadastro completo."""
    report = run_audit(REAL_FIXTURE)
    completeness = report.data_completeness[0]
    assert round(completeness.completeness_pct, 1) == 24.8
    assert completeness.contingency_triggered is True


def test_manual_review_queue_dimensioning_stays_small():
    """Critério de aceite da Fase C (Spec §6, item 1): a fila manual precisa ser o
    RESÍDUO, não o atacado — as 7 pegadinhas foram desenhadas pra serem todas
    classificáveis automaticamente."""
    report = run_audit(REAL_FIXTURE)
    dt = report.advanced_metrics.discrepancy_triage
    assert dt.triggered_count == 38
    assert dt.manual_queue == []
    assert Counter(i.verdict for i in dt.auto_classified) == Counter({
        "suspected_cadastral_error": 10, "deliberate_liquidation": 14, "below_cost_sale": 14,
    })

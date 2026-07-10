"""
Testes de regressão — Fix 3 etapa 2: leitura multi-aba (Estoque, Clientes) para B4
Estoque Morto, B2 GMROI e A1 Completude/Contingência.

Roda contra `consultoria_real_test.xlsx` — cópia de uma planilha real de consultoria
(dado sintético de demonstração, com seu próprio Gabarito oculto documentando as
anomalias plantadas; não é PII de cliente real). É a única fixture com Estoque/Clientes
deterministicamente plantados para esses três detectores — a fixture sintética
`otica_test_bom.xlsx` não sustenta B1/B2/B3 (ver nota no design spec).

B4 Estoque Morto: trava EXATO — 12 SKUs DEAD-001..012, custo_unit=800 × qtd_atual=3,
parados desde 2025-10-24 (249 dias, ~8 meses de calendário até a data de referência
2026-06-30) = R$28.800 exato. Bate o Gabarito da própria planilha.

A1 Completude: trava PRÓXIMO de ~88% (não exato — telefone e CPF faltam
independentemente por cliente no dado real, diferente da fixture sintética onde os 2
campos sempre andam juntos; a métrica por-campo mede 89,4%, com tolerância).

B2 GMROI: NÃO trava valor específico — é medição, não alvo (não foi engenheirado no
dado real). Trava só a forma do contrato (categorias presentes, tipos corretos).
"""
from pathlib import Path

from oracle.commercial_auditor import run_audit

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


def test_dead_stock_matches_real_gabarito_exactly():
    report = run_audit(FIXTURE)
    assert len(report.dead_stock) == 1
    finding = report.dead_stock[0]
    assert finding.sku_count == 12
    assert finding.capital_frozen == 28800.0
    assert set(finding.skus) == {f"DEAD-{i:03d}" for i in range(1, 13)}


def test_data_completeness_close_to_real_gabarito():
    report = run_audit(FIXTURE)
    assert len(report.data_completeness) == 1
    finding = report.data_completeness[0]
    assert finding.total_customers == 240
    # Gabarito diz "~88%"; medimos 89,4% por média de campo (telefone/CPF faltam
    # independentemente no dado real) — tolerância de 3 pontos, não força a fórmula.
    assert abs(finding.completeness_pct - 88.0) < 3.0
    assert finding.contingency_triggered is False  # completude alta -> motor roda normal


def test_gmroi_reports_measured_values_not_hardcoded_targets():
    report = run_audit(FIXTURE)
    assert len(report.gmroi) > 0
    categories = {g.category for g in report.gmroi}
    assert {"lente", "solar", "armacao_premium"} <= categories
    for entry in report.gmroi:
        assert entry.avg_inventory_value >= 0
        assert entry.sample_size >= 0
        if entry.avg_inventory_value == 0:
            assert entry.gmroi is None
        else:
            assert entry.gmroi == entry.gross_margin / entry.avg_inventory_value

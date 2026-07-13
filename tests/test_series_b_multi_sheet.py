"""
Testes de regressão — Fix 3 etapa 2: leitura multi-aba (Estoque, Clientes) para B4
Estoque Morto, B2 GMROI e A1 Completude/Contingência.

Roda contra `consultoria_real_test.xlsx` — cópia de uma planilha real de consultoria
(dado sintético de demonstração, com seu próprio Gabarito oculto documentando as
anomalias plantadas; não é PII de cliente real). É a única fixture com Estoque/Clientes
deterministicamente plantados para esses três detectores — a fixture sintética
`otica_test_bom.xlsx` não sustenta B1/B2/B3 (ver nota no design spec).

B4 Estoque Morto: trava por SUBSET de SKU (não total exato) — a fixture é uma planilha
real do cliente que continua evoluindo (v2 adicionou DEADX-001..004 em L6, "erosão de
margem por mix", junto do plantio original DEAD-001..012 em L1); travar um total exato
quebraria a cada atualização legítima do dado. DEAD-001..012 (custo_unit=800 ×
qtd_atual=3 = R$2.400 cada, 249 dias parado) é o plantio original do Gabarito.

A1 Completude: trava só a FORMA (completude alta, sem gatilho de contingência) — o
valor exato (hoje 93,9%, era 89,4% na v1 do arquivo) muda conforme a base de clientes
cresce a cada atualização real da planilha.

B2 GMROI: NÃO trava valor específico — é medição, não alvo (não foi engenheirado no
dado real). Trava só a forma do contrato (categorias presentes, tipos corretos).
"""
from pathlib import Path

from oracle.commercial_auditor import run_audit

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"

_ORIGINAL_DEAD_SKUS = {f"DEAD-{i:03d}" for i in range(1, 13)}


def test_dead_stock_catches_planted_skus():
    report = run_audit(FIXTURE)
    assert len(report.dead_stock) == 1
    finding = report.dead_stock[0]
    skus_found = set(finding.skus)
    assert _ORIGINAL_DEAD_SKUS <= skus_found
    # Capital do plantio original é auto-verificável (não hardcoded): 12 × R$2.400.
    assert finding.capital_frozen >= 12 * 2400.0


def test_data_completeness_is_high_with_no_contingency():
    report = run_audit(FIXTURE)
    assert len(report.data_completeness) == 1
    finding = report.data_completeness[0]
    assert finding.total_customers > 0
    assert finding.completeness_pct > 50.0  # bem acima do gatilho de 30%
    assert finding.contingency_triggered is False


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

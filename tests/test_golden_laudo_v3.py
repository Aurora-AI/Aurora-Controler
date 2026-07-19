"""
Golden master do laudo v3 — trava o resultado da auditoria sobre a planilha real do
cliente (`consultoria_real_test.xlsx`) contra o JSON exato apresentado na reunião.

Por que existe: a partir da convergência do Produto B ao kernel (commit 9750558), o
motor do laudo passou a depender de código compartilhado (`kernel.tabular`,
`kernel.robustness`) que vai evoluir por baixo dele conforme o kernel cresce (vista
tabular nova, robustez usada pelo Produto A). Sem este teste, uma mudança no kernel
pode derivar o laudo em SILÊNCIO — a suíte geral ficaria verde (cobre comportamento,
não o valor exato de cada campo do laudo real), e só se notaria relendo número por
número na próxima reunião. Este teste substitui essa conferência manual por uma
automática: qualquer divergência de QUALQUER campo falha aqui, na hora.

Se este teste falhar depois de uma mudança legítima e intencional no motor (não uma
regressão), o laudo esperado precisa ser regenerado deliberadamente — nunca ajustar
o teste pra "passar", sempre confirmar que a nova saída está correta primeiro.
"""
import json
from pathlib import Path

from product_b.oracle.commercial_auditor import run_audit

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_PATH = FIXTURES / "golden_laudo_v3.json"
REAL_FIXTURE = FIXTURES / "consultoria_real_test.xlsx"


def test_laudo_matches_golden_master_exactly():
    report = run_audit(REAL_FIXTURE)
    actual = report.model_dump(mode="json")
    actual.pop("generated_at", None)

    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    assert actual == expected, (
        "O laudo divergiu do golden master (laudo v3 apresentado na reunião). "
        "Se a mudança no motor foi intencional, regenere "
        "tests/fixtures/golden_laudo_v3.json deliberadamente (nunca só pra fazer "
        "este teste passar) e confirme cada número novo antes de commitar."
    )


def test_key_findings_from_the_meeting_stay_pinned():
    """Redundante com o teste acima (que já compara o JSON inteiro), mas isola os
    números que foram apresentados ao cliente — se algum quebrar, a mensagem de erro
    aponta direto pro achado, sem precisar garimpar um diff de JSON gigante."""
    report = run_audit(REAL_FIXTURE)
    d = report.model_dump(mode="json")

    l7 = next(s for s in d["service_decomposition"] if s["store"] == "L7 - Oeste")
    assert l7["masks_negative_product_margin"] is True
    assert round(l7["product_margin"], 2) == -3346.09
    assert round(l7["total_margin"], 2) == 10494.03

    assert d["dead_stock"][0]["capital_frozen"] == 35040.0
    assert d["dead_stock"][0]["sku_count"] == 16

    concentration = d["customer_concentration"][0]
    assert concentration["customer"] == "Client_B"
    assert round(concentration["concentration_pct"], 2) == 32.32

    assert len(d["churn_findings"]) == 47
    assert round(sum(c["historical_annual_value"] for c in d["churn_findings"]), 2) == 92077.99

    gaps = [r for r in d["service_reconciliation"] if r["has_gap"]]
    assert len(gaps) == 2

    summary = d["executive_summary"]
    assert round(summary["total_capital_frozen"], 2) == 35040.0
    assert round(summary["total_ltv_risk"], 2) == 92077.99
    assert [item["tier"] for item in summary["action_plan"]] == sorted(
        item["tier"] for item in summary["action_plan"]
    )
    assert {a["category"] for a in summary["discarded_alarms"]} <= {
        "salesperson_ramp", "store_cold_start",
    }

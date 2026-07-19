# Executive Summary (Backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o motor do Produto B (`AuroraControler`) calcular e expor `executive_summary` no `ExecutiveAuditReport` — os agregados de topo do laudo (perda operacional, capital parado, risco de LTV, alarmes descartados, plano de ação) que hoje só existem mockados no frontend.

**Architecture:** Uma função pura nova, `build_executive_summary(...)`, roda depois de todos os detectores existentes em `run_audit()` e recombina os outputs deles (nunca acessa `df` de novo, nunca soma achados de naturezas diferentes entre si). Três novos contratos Pydantic (`DiscardedAlarm`, `ActionPlanItem`, `ExecutiveSummary`) em `forensic_contracts.py`. O golden master é regenerado só depois de testes que recalculam os totais a partir da própria fonte (não do dump) confirmarem cada regra.

**Tech Stack:** Python 3.14, Pydantic V2, pandas, pytest.

## Global Constraints

- Frontend nunca calcula — todo agregado deste plano é produzido no backend; o frontend (fora de escopo deste plano) só remodela/exibe.
- `total_operational_loss`, `total_capital_frozen` e `total_ltv_risk` nunca são somados entre si em nenhum campo — três naturezas contábeis distintas.
- `total_operational_loss` NÃO exclui promoção (sem sinal disso no dado de origem hoje) — quem exibe este campo deve rotular "a confirmar", nunca como perda estrutural confirmada.
- `discarded_alarms` cobre só `salesperson_ramp` e `store_cold_start` nesta rodada — "queda sazonal descartada" fica fora (o motor não expõe candidatos abaixo do limiar de sazonalidade, só as anomalias que passaram).
- `action_plan` é ordenado por `tier` ascendente e, dentro do tier, por `impact_brl` descendente — nunca só por R$ bruto. Receita latente (`latent_revenue`) nunca entra no plano de ação nem em nenhum dos três totais.
- Golden master (`tests/fixtures/golden_laudo_v3.json`) só é regenerado depois que os testes de forma sobre dado real (Task 4) passarem — nunca regenerar primeiro e verificar depois.
- Spec de referência: `docs/superpowers/specs/2026-07-17-laudo-executive-summary-e-frontend-drilldown-design.md`.

---

### Task 1: Contratos Pydantic novos (`DiscardedAlarm`, `ActionPlanItem`, `ExecutiveSummary`)

**Files:**
- Modify: `src/product_b/oracle/forensic_contracts.py:400-402` (inserir 3 classes novas antes de `class ExecutiveAuditReport`, e adicionar campo `executive_summary` na classe)
- Test: `tests/test_forensic_contracts.py`

**Interfaces:**
- Produces: `DiscardedAlarm(category: str, entity_id: str, reason: str)`; `ActionPlanItem(id: str, category: str, title: str, description: str, impact_brl: float, nature: str, tier: int)`; `ExecutiveSummary(total_operational_loss: float, total_capital_frozen: float, total_ltv_risk: float, discarded_alarms: list[DiscardedAlarm] = [], action_plan: list[ActionPlanItem] = [])`; `ExecutiveAuditReport.executive_summary: ExecutiveSummary` (campo obrigatório, sem default).

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_forensic_contracts.py`:

```python
from product_b.oracle.forensic_contracts import (
    ActionPlanItem, DiscardedAlarm, ExecutiveSummary,
)


def test_discarded_alarm_carries_category_entity_and_reason():
    alarm = DiscardedAlarm(
        category="salesperson_ramp", entity_id="Vendedor Novo",
        reason="Vendedor em rampa há 60 dias — volume baixo não é penalizado.",
    )
    assert alarm.category == "salesperson_ramp"
    assert alarm.entity_id == "Vendedor Novo"


def test_action_plan_item_carries_tier_for_ordering():
    item = ActionPlanItem(
        id="act-operational", category="margem_produto", title="Estancar Sangria",
        description="...", impact_brl=1000.0, nature="operational", tier=1,
    )
    assert item.tier == 1
    assert item.nature == "operational"


def test_executive_summary_defaults_to_empty_alarms_and_plan():
    summary = ExecutiveSummary(
        total_operational_loss=0.0, total_capital_frozen=0.0, total_ltv_risk=0.0,
    )
    assert summary.discarded_alarms == []
    assert summary.action_plan == []


def test_executive_summary_natures_stay_as_three_separate_fields():
    """Guarda de regressão: os três totais são campos INDEPENDENTES — nenhum é
    calculado como soma dos outros dois (isso seria uma violação da regra de que as
    três naturezas contábeis nunca se somam)."""
    summary = ExecutiveSummary(
        total_operational_loss=100.0, total_capital_frozen=200.0, total_ltv_risk=300.0,
    )
    assert summary.total_operational_loss == 100.0
    assert summary.total_capital_frozen == 200.0
    assert summary.total_ltv_risk == 300.0
```

Também é preciso atualizar o teste já existente `test_executive_audit_report_assembles_all_sections` (linha ~100-110 do mesmo arquivo), que constrói um `ExecutiveAuditReport` sem `executive_summary` — vai quebrar assim que o campo virar obrigatório:

```python
def test_executive_audit_report_assembles_all_sections():
    report = ExecutiveAuditReport(
        period_start="2023-01", period_end="2024-12",
        cleaning=CleaningSummary(rows_read=258, rows_accepted=258,
                                  rows_discarded_by_reason={}, files_skipped=[]),
        thresholds=AuditThresholdsConfig(),
        revenue_leaks=[], churn_findings=[], product_trends=[], seasonality=[],
        executive_summary=ExecutiveSummary(
            total_operational_loss=0.0, total_capital_frozen=0.0, total_ltv_risk=0.0,
        ),
        generated_at="2026-07-06T00:00:00",
    )
    assert report.period_start == "2023-01"
    assert report.thresholds.revenue_drop_sigma == 2.0
    assert report.executive_summary.total_operational_loss == 0.0
```

E o import no topo do arquivo (linha 16-19) precisa incluir `ExecutiveSummary`:

```python
from product_b.oracle.forensic_contracts import (
    ActionPlanItem, AuditThresholdsConfig, ChurnFinding, CleaningSummary, DiscardedAlarm,
    ExecutiveAuditReport, ExecutiveSummary, ProductTrendEntry, RevenueLeakAnomaly,
    SalesRecord, SeasonalityCurve,
)
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `python -m pytest tests/test_forensic_contracts.py -v`
Expected: FAIL — `ImportError: cannot import name 'ActionPlanItem'` (as classes ainda não existem) e/ou `ValidationError` no teste atualizado (campo `executive_summary` ainda não existe no contrato).

- [ ] **Step 3: Implementar os contratos**

Em `src/product_b/oracle/forensic_contracts.py`, inserir estas 3 classes imediatamente antes de `class ExecutiveAuditReport(BaseModel):` (linha 402):

```python
class DiscardedAlarm(BaseModel):
    """ES — Sumário executivo: um candidato que o motor avaliou e decidiu NÃO
    reportar como achado, com o motivo. Cobre só categorias que o motor genuinamente
    checa hoje (rampa de vendedor, cold-start de loja) — nunca populado com um caso
    artificial só para não ficar vazio."""
    category: str  # "salesperson_ramp" | "store_cold_start"
    entity_id: str
    reason: str


class ActionPlanItem(BaseModel):
    """ES — Item do plano de ação, pré-ordenado pelo motor (tier ascendente, R$
    descendente dentro do tier). O frontend renderiza na ordem que veio, nunca
    reordena nem recalcula."""
    id: str
    category: str
    title: str
    description: str
    impact_brl: float
    nature: str  # "operational" | "capital" | "ltv_risk"
    tier: int  # 1 = perda certa/recorrente, 2 = capital recuperável, 3 = LTV projetado


class ExecutiveSummary(BaseModel):
    """ES — Agregados de topo do laudo. Cada total vem DA FONTE (dos detectores),
    contado uma vez; as três naturezas (operacional/capital/LTV) nunca são somadas
    entre si em lugar nenhum — são fatos de natureza contábil diferente. Receita
    latente (cenário) fica de fora: nunca soma aqui, nunca entra em `action_plan`.

    `total_operational_loss` não exclui promoção legítima (sem sinal disso no dado de
    origem hoje) — quem consome este campo DEVE rotular como "a confirmar", nunca
    como perda estrutural confirmada."""
    total_operational_loss: float
    total_capital_frozen: float
    total_ltv_risk: float
    discarded_alarms: list[DiscardedAlarm] = Field(default_factory=list)
    action_plan: list[ActionPlanItem] = Field(default_factory=list)
```

E adicionar o campo `executive_summary` na classe `ExecutiveAuditReport` (logo antes de `generated_at: str`, que fica por último):

```python
    salesperson_performance: list[SalespersonPerformance] = Field(default_factory=list)
    executive_summary: ExecutiveSummary
    generated_at: str
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

Run: `python -m pytest tests/test_forensic_contracts.py -v`
Expected: PASS (todos, incluindo os 4 novos e o `test_executive_audit_report_assembles_all_sections` atualizado)

- [ ] **Step 5: Commit**

```bash
git add src/product_b/oracle/forensic_contracts.py tests/test_forensic_contracts.py
git commit -m "feat(oracle): adiciona contratos DiscardedAlarm/ActionPlanItem/ExecutiveSummary"
```

---

### Task 2: `build_executive_summary(...)` — implementação completa (dado sintético)

**Files:**
- Modify: `src/product_b/oracle/commercial_auditor.py:1238` (inserir a função nova entre `detect_service_reconciliation` e `run_audit`) e `src/product_b/oracle/commercial_auditor.py:25-32` (imports)
- Test: `tests/test_executive_summary.py` (novo arquivo)

**Interfaces:**
- Consumes: `ContributionMarginAlert`, `DeadStockFinding`, `ChurnFinding`, `SalespersonPerformance`, `StorePerformance`, `AuditThresholdsConfig` (todos já existem em `forensic_contracts.py`, ver Task 1 para os 3 novos).
- Produces: `build_executive_summary(contribution_margin_alerts: list[ContributionMarginAlert], dead_stock: list[DeadStockFinding], churn_findings: list[ChurnFinding], salesperson_performance: list[SalespersonPerformance], store_performance: list[StorePerformance], thresholds: AuditThresholdsConfig) -> ExecutiveSummary`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/test_executive_summary.py`:

```python
"""
Testes de src/product_b/oracle/commercial_auditor.py::build_executive_summary.

Aritmética isolada (sintética): constrói os outputs dos detectores diretamente (não
roda o pipeline inteiro) para testar só a agregação, sem depender de nenhuma fixture
real. Os testes de FORMA sobre dado real ficam em test_executive_summary_real_data.py.
"""
import inspect

from product_b.oracle.commercial_auditor import build_executive_summary
from product_b.oracle.forensic_contracts import (
    AuditThresholdsConfig, ChurnFinding, ContributionMarginAlert, DeadStockFinding,
    SalespersonPerformance, StorePerformance,
)


def _thresholds():
    return AuditThresholdsConfig(sev_ramp_min_days=180.0, cold_start_min_months=4.0)


def test_total_operational_loss_sums_absolute_negative_margins():
    alerts = [
        ContributionMarginAlert(
            product="P1", avg_price=50.0, avg_entry_cost=60.0, variable_cost_pct=15.0,
            contribution_margin=-17.5, sample_size=10,
        ),
        ContributionMarginAlert(
            product="P2", avg_price=30.0, avg_entry_cost=35.0, variable_cost_pct=15.0,
            contribution_margin=-9.5, sample_size=4,
        ),
    ]
    summary = build_executive_summary(
        contribution_margin_alerts=alerts, dead_stock=[], churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert abs(summary.total_operational_loss - 27.0) < 1e-6


def test_total_capital_frozen_reads_the_single_dead_stock_finding():
    dead_stock = [DeadStockFinding(
        dead_stock_months=8, sku_count=16, capital_frozen=35040.0,
        total_inventory_value=100000.0, dead_stock_pct=35.04, skus=["SKU-1"],
    )]
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=dead_stock, churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.total_capital_frozen == 35040.0


def test_total_capital_frozen_is_zero_without_dead_stock():
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.total_capital_frozen == 0.0


def test_total_ltv_risk_sums_historical_annual_value():
    churn = [
        ChurnFinding(customer_id="Client_A", purchase_count=18, avg_cadence_days=30.0,
                     last_purchase="2024-06-15", months_silent=6, historical_annual_value=48000.0),
        ChurnFinding(customer_id="Client_B", purchase_count=5, avg_cadence_days=45.0,
                     last_purchase="2024-05-01", months_silent=4, historical_annual_value=12000.0),
    ]
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=churn,
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.total_ltv_risk == 60000.0


def test_discarded_alarms_flags_ramping_salesperson_and_cold_start_store():
    salespeople = [
        SalespersonPerformance(
            salesperson="Vendedor Novo", total_revenue=5000.0, sample_size=8,
            capture_rate_pct=70.0, low_capture_flag=False, days_since_first_sale=60,
            has_sufficient_tenure=False, low_volume_flag=False,
        ),
        SalespersonPerformance(
            salesperson="Vendedor Maduro", total_revenue=50000.0, sample_size=80,
            capture_rate_pct=70.0, low_capture_flag=False, days_since_first_sale=400,
            has_sufficient_tenure=True, low_volume_flag=False,
        ),
    ]
    stores = [
        StorePerformance(
            store="Loja Nova", gross_revenue=1000.0, revenue_sample_size=5,
            avg_price=100.0, avg_entry_cost=50.0, variable_cost_pct=15.0,
            contribution_margin_avg=35.0, contribution_margin_total=175.0,
            margin_sample_size=5, months_of_history=1.5, has_sufficient_history=False,
        ),
        StorePerformance(
            store="Loja Madura", gross_revenue=100000.0, revenue_sample_size=500,
            avg_price=100.0, avg_entry_cost=50.0, variable_cost_pct=15.0,
            contribution_margin_avg=35.0, contribution_margin_total=17500.0,
            margin_sample_size=500, months_of_history=24.0, has_sufficient_history=True,
        ),
    ]
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=[],
        salesperson_performance=salespeople, store_performance=stores,
        thresholds=_thresholds(),
    )
    categories_and_entities = {(a.category, a.entity_id) for a in summary.discarded_alarms}
    assert categories_and_entities == {
        ("salesperson_ramp", "Vendedor Novo"),
        ("store_cold_start", "Loja Nova"),
    }


def test_action_plan_orders_by_tier_then_impact_descending_within_tier():
    alerts = [ContributionMarginAlert(
        product="P1", avg_price=50.0, avg_entry_cost=60.0, variable_cost_pct=15.0,
        contribution_margin=-10.0, sample_size=5,
    )]  # total_operational_loss = 50.0 -> tier 1
    dead_stock = [DeadStockFinding(
        dead_stock_months=8, sku_count=1, capital_frozen=200.0,
        total_inventory_value=1000.0, dead_stock_pct=20.0, skus=["SKU-1"],
    )]  # total_capital_frozen = 200.0 -> tier 2
    churn = [ChurnFinding(
        customer_id="Client_A", purchase_count=5, avg_cadence_days=30.0,
        last_purchase="2024-01-01", months_silent=6, historical_annual_value=99999.0,
    )]  # total_ltv_risk = 99999.0 -> tier 3 (maior R$ de todos, mas último por natureza)
    summary = build_executive_summary(
        contribution_margin_alerts=alerts, dead_stock=dead_stock, churn_findings=churn,
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert [item.nature for item in summary.action_plan] == ["operational", "capital", "ltv_risk"]
    assert [item.tier for item in summary.action_plan] == [1, 2, 3]


def test_action_plan_omits_items_with_zero_impact():
    summary = build_executive_summary(
        contribution_margin_alerts=[], dead_stock=[], churn_findings=[],
        salesperson_performance=[], store_performance=[], thresholds=_thresholds(),
    )
    assert summary.action_plan == []


def test_build_executive_summary_cannot_leak_latent_revenue_into_the_plan():
    """Guarda de regressão: build_executive_summary não recebe latent_revenue como
    parâmetro — impossível vazar receita latente (cenário) para dentro do plano de
    ação como se fosse fato, mesmo por engano futuro."""
    params = inspect.signature(build_executive_summary).parameters
    assert "latent_revenue" not in params
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `python -m pytest tests/test_executive_summary.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_executive_summary'`

- [ ] **Step 3: Implementar `build_executive_summary`**

Em `src/product_b/oracle/commercial_auditor.py`, atualizar o bloco de import (linhas 25-32) para incluir os 3 contratos novos:

```python
from product_b.oracle.forensic_contracts import (
    ActionPlanItem, AuditThresholdsConfig, ChurnFinding, CleaningSummary,
    ContributionMarginAlert, CustomerConcentrationFinding, DataCompletenessFinding,
    DeadStockFinding, DiscardedAlarm, ExecutiveAuditReport, ExecutiveSummary,
    GmroiEntry, LatentRevenueFinding, ProductTrendEntry, RevenueLeakAnomaly, RFMChampion,
    SalesRecord, SalespersonPerformance, ServiceDecomposition, ServiceReconciliation,
    SeasonalityCurve, StoreMacroSummary, StorePerformance, WinsorizedValue,
)
```

Inserir esta função logo após `detect_service_reconciliation` (que termina em `return sorted(entries, key=lambda e: -abs(e.gap))`, linha 1237) e antes de `def run_audit(`:

```python
def build_executive_summary(
    contribution_margin_alerts: list[ContributionMarginAlert],
    dead_stock: list[DeadStockFinding],
    churn_findings: list[ChurnFinding],
    salesperson_performance: list[SalespersonPerformance],
    store_performance: list[StorePerformance],
    thresholds: AuditThresholdsConfig,
) -> ExecutiveSummary:
    """ES — Sumário executivo: agrega os outputs JÁ CALCULADOS pelos detectores acima
    em três totais de natureza contábil diferente (nunca somados entre si), mais os
    alarmes descartados e o plano de ação. Função pura, sem novo acesso a `df` — só
    recombina o que os detectores já retornaram, mesma filosofia de
    `build_store_macro_summary`.

    `total_operational_loss`: soma de |contribution_margin| de todo item em
    `contribution_margin_alerts` (a lista já só contém margem < 0, ver
    `detect_contribution_margin`). Não soma com `service_decomposition` (evitaria
    dupla contagem). Não exclui promoção (sem sinal no dado) — rotular como "a
    confirmar" é responsabilidade de quem exibe este campo, não deste cálculo.

    `total_capital_frozen`: `dead_stock[0].capital_frozen` se houver achado —
    `detect_dead_stock` estruturalmente nunca retorna mais que 1 item (sempre soma a
    rede inteira), então não há double-count possível aqui.

    `total_ltv_risk`: soma de `historical_annual_value` de todo `churn_findings`.

    `discarded_alarms`: só as duas categorias que o motor genuinamente checa hoje —
    vendedor em rampa (`has_sufficient_tenure=False`) e loja cold-start
    (`has_sufficient_history=False`). "Queda sazonal descartada" fica de fora: o
    motor de vazamento de receita não expõe candidatos que ficaram abaixo do limiar
    de sazonalidade, só os que viraram anomalia — ver
    docs/superpowers/specs/2026-07-17-laudo-executive-summary-e-frontend-drilldown-design.md,
    seção 4.3.

    `action_plan`: até 3 itens fixos (operacional/capital/LTV), cada um só aparece se
    o total correspondente for > 0, ordenados por tier ascendente e R$ descendente
    dentro do tier. Receita latente nunca entra aqui (é cenário, não fato) — por
    isso esta função nem recebe `latent_revenue` como parâmetro."""
    total_operational_loss = float(
        sum(abs(a.contribution_margin) for a in contribution_margin_alerts)
    )
    total_capital_frozen = float(dead_stock[0].capital_frozen) if dead_stock else 0.0
    total_ltv_risk = float(sum(c.historical_annual_value for c in churn_findings))

    discarded_alarms: list[DiscardedAlarm] = []
    for sp in salesperson_performance:
        if not sp.has_sufficient_tenure:
            discarded_alarms.append(DiscardedAlarm(
                category="salesperson_ramp", entity_id=sp.salesperson,
                reason=(
                    f"Vendedor em rampa há {sp.days_since_first_sale} dias "
                    f"(mínimo de maturidade: {thresholds.sev_ramp_min_days:.0f} dias) — "
                    "volume baixo não é penalizado."
                ),
            ))
    for s in store_performance:
        if not s.has_sufficient_history:
            discarded_alarms.append(DiscardedAlarm(
                category="store_cold_start", entity_id=s.store,
                reason=(
                    f"Loja com {s.months_of_history:.1f} meses de histórico "
                    f"(mínimo: {thresholds.cold_start_min_months:.0f} meses) — dado "
                    "insuficiente para tratar suas métricas com a mesma confiança de "
                    "uma loja madura."
                ),
            ))

    action_plan: list[ActionPlanItem] = []
    if total_operational_loss > 0:
        action_plan.append(ActionPlanItem(
            id="act-operational", category="margem_produto",
            title="Estancar Sangria Operacional",
            description=(
                "SKUs vendendo abaixo da margem de contribuição — ajustar "
                "precificação ou descontinuar. Pode incluir promoção intencional, "
                "a confirmar."
            ),
            impact_brl=total_operational_loss, nature="operational", tier=1,
        ))
    if total_capital_frozen > 0:
        action_plan.append(ActionPlanItem(
            id="act-capital", category="estoque",
            title="Liquidar Dinheiro Parado",
            description=(
                "Capital travado em estoque sem movimento — requer outlet ou "
                "transferência entre lojas."
            ),
            impact_brl=total_capital_frozen, nature="capital", tier=2,
        ))
    if total_ltv_risk > 0:
        action_plan.append(ActionPlanItem(
            id="act-ltv", category="churn",
            title="Mitigar Evasão Silenciosa (Churn)",
            description=(
                "Clientes recorrentes que sumiram além do ciclo de compra esperado — "
                "ativação via CRM prioritária."
            ),
            impact_brl=total_ltv_risk, nature="ltv_risk", tier=3,
        ))
    action_plan.sort(key=lambda item: (item.tier, -item.impact_brl))

    return ExecutiveSummary(
        total_operational_loss=total_operational_loss,
        total_capital_frozen=total_capital_frozen,
        total_ltv_risk=total_ltv_risk,
        discarded_alarms=discarded_alarms,
        action_plan=action_plan,
    )
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

Run: `python -m pytest tests/test_executive_summary.py -v`
Expected: PASS (todos os 8 testes)

- [ ] **Step 5: Commit**

```bash
git add src/product_b/oracle/commercial_auditor.py tests/test_executive_summary.py
git commit -m "feat(oracle): implementa build_executive_summary (agregados + plano de ação)"
```

---

### Task 3: Integração em `run_audit()`

**Files:**
- Modify: `src/product_b/oracle/commercial_auditor.py:1286-1318`
- Test: `tests/test_executive_summary.py` (adicionar teste de integração)

**Interfaces:**
- Consumes: `build_executive_summary(...)` (Task 2), todos os detectores já computados em `run_audit`.
- Produces: `ExecutiveAuditReport.executive_summary` populado em toda chamada de `run_audit(...)`.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar ao final de `tests/test_executive_summary.py`:

```python
from pathlib import Path

from product_b.oracle.commercial_auditor import run_audit

_FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


def test_run_audit_populates_executive_summary():
    report = run_audit(_FIXTURE)
    assert report.executive_summary is not None
    assert report.executive_summary.total_operational_loss >= 0.0
    assert report.executive_summary.total_capital_frozen >= 0.0
    assert report.executive_summary.total_ltv_risk >= 0.0
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `python -m pytest tests/test_executive_summary.py::test_run_audit_populates_executive_summary -v`
Expected: FAIL — `pydantic.ValidationError: executive_summary Field required` (o `ExecutiveAuditReport` construído em `run_audit` ainda não passa esse campo)

- [ ] **Step 3: Ligar `build_executive_summary` em `run_audit`**

Em `src/product_b/oracle/commercial_auditor.py`, dentro de `run_audit` (linha 1240), inserir a chamada logo depois de `service_reconciliation = detect_service_reconciliation(...)` (linha 1286) e antes de `_, identity_map = anonymize_customers(records)` (linha 1288):

```python
    service_decomposition = detect_service_decomposition(df, thresholds)
    service_reconciliation = detect_service_reconciliation(df, named_sheets.get("Financeiro"), thresholds)

    executive_summary = build_executive_summary(
        contribution_margin_alerts=contribution_margin_alerts,
        dead_stock=dead_stock,
        churn_findings=churn_findings,
        salesperson_performance=salesperson_performance,
        store_performance=store_performance,
        thresholds=thresholds,
    )

    _, identity_map = anonymize_customers(records)
```

E adicionar `executive_summary=executive_summary,` na construção de `report = ExecutiveAuditReport(...)` (linha 1307), por exemplo logo após `service_reconciliation=service_reconciliation,`:

```python
        service_decomposition=service_decomposition, service_reconciliation=service_reconciliation,
        executive_summary=executive_summary,
        generated_at=datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 4: Rodar o teste para confirmar que passa**

Run: `python -m pytest tests/test_executive_summary.py -v`
Expected: PASS (todos, incluindo `test_run_audit_populates_executive_summary`)

- [ ] **Step 5: Rodar a suíte inteira para checar por regressão de integração**

Run: `python -m pytest tests/ -q`
Expected: `test_golden_laudo_v3.py::test_laudo_matches_golden_master_exactly` FALHA agora (esperado — o dump ganhou um campo novo, será resolvido na Task 5). Nenhum outro teste deve falhar por causa desta mudança; se algum outro teste falhar, investigar antes de prosseguir.

- [ ] **Step 6: Commit**

```bash
git add src/product_b/oracle/commercial_auditor.py tests/test_executive_summary.py
git commit -m "feat(oracle): liga build_executive_summary em run_audit()"
```

---

### Task 4: Testes de forma sobre dado real (sem gabarito, recalculado da fonte)

Este é o passo de verificação independente exigido pela spec (seção 7.1) — recalcula os totais a partir do próprio relatório, nunca compara contra um valor cravado nem contra o dump. Precisa passar ANTES de regenerar o golden master (Task 5).

**Files:**
- Create: `tests/test_executive_summary_real_data.py`

**Interfaces:**
- Consumes: `run_audit(FIXTURE)` (já existente), `report.executive_summary`, `report.contribution_margin_alerts`, `report.dead_stock`, `report.churn_findings`.

- [ ] **Step 1: Escrever os testes (já nascem como a verificação — não há "implementação" nesta task, só os testes)**

Criar `tests/test_executive_summary_real_data.py`:

```python
"""
Testes de FORMA sobre dado real (consultoria_real_test.xlsx) para
build_executive_summary — nenhum valor cravado, tudo recalculado a partir do próprio
relatório. Este arquivo é o passo de verificação independente exigido antes de
regenerar tests/fixtures/golden_laudo_v3.json (ver
docs/superpowers/specs/2026-07-17-laudo-executive-summary-e-frontend-drilldown-design.md,
seção 7.1) — se algum teste aqui falhar, NÃO regenere o golden master; há um bug em
build_executive_summary para corrigir primeiro.
"""
from pathlib import Path

from product_b.oracle.commercial_auditor import run_audit

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


def test_executive_summary_totals_recompute_from_the_report_itself():
    report = run_audit(FIXTURE)
    summary = report.executive_summary

    expected_operational_loss = sum(
        abs(a.contribution_margin) for a in report.contribution_margin_alerts
    )
    assert abs(summary.total_operational_loss - expected_operational_loss) < 0.01

    expected_capital_frozen = (
        report.dead_stock[0].capital_frozen if report.dead_stock else 0.0
    )
    assert summary.total_capital_frozen == expected_capital_frozen

    expected_ltv_risk = sum(c.historical_annual_value for c in report.churn_findings)
    assert abs(summary.total_ltv_risk - expected_ltv_risk) < 0.01


def test_executive_summary_natures_are_never_summed_together():
    """Guarda simples contra double-count/merge acidental entre naturezas: nenhum
    total é igual à soma dos outros dois."""
    report = run_audit(FIXTURE)
    summary = report.executive_summary
    assert summary.total_operational_loss != (
        summary.total_capital_frozen + summary.total_ltv_risk
    )


def test_discarded_alarms_only_uses_categories_the_engine_actually_checks():
    report = run_audit(FIXTURE)
    categories = {a.category for a in report.executive_summary.discarded_alarms}
    assert categories <= {"salesperson_ramp", "store_cold_start"}


def test_action_plan_is_sorted_by_tier_then_impact_descending():
    report = run_audit(FIXTURE)
    plan = report.executive_summary.action_plan
    tiers = [item.tier for item in plan]
    assert tiers == sorted(tiers)
    for tier in set(tiers):
        impacts = [item.impact_brl for item in plan if item.tier == tier]
        assert impacts == sorted(impacts, reverse=True)


def test_action_plan_never_contains_a_latent_or_scenario_nature():
    report = run_audit(FIXTURE)
    natures = {item.nature for item in report.executive_summary.action_plan}
    assert "scenario" not in natures
    assert "latent" not in natures
    assert natures <= {"operational", "capital", "ltv_risk"}


def test_at_least_one_real_action_plan_item_exists_for_this_fixture():
    """`consultoria_real_test.xlsx` tem SKUs no vermelho, estoque morto e churn
    conhecidos (ver test_store_macro_pnl.py, test_forensic_contracts.py) — o plano de
    ação não deveria vir vazio para este dataset."""
    report = run_audit(FIXTURE)
    assert report.executive_summary.action_plan
```

- [ ] **Step 2: Rodar os testes**

Run: `python -m pytest tests/test_executive_summary_real_data.py -v`
Expected: PASS (todos os 6 testes). Se qualquer um falhar, **não prosseguir para a Task 5** — voltar à Task 2 e corrigir `build_executive_summary` antes de regenerar qualquer fixture.

- [ ] **Step 3: Commit**

```bash
git add tests/test_executive_summary_real_data.py
git commit -m "test(oracle): verificação independente de build_executive_summary sobre dado real"
```

---

### Task 5: Regenerar golden master + travar valores novos + suíte completa

**Only start this task after Task 4's tests are green.** Esta ordem é a trava contra "regenerar lava um bug" descrita na spec (seção 7.1).

**Files:**
- Modify: `tests/fixtures/golden_laudo_v3.json` (regenerado)
- Modify: `tests/test_golden_laudo_v3.py` (novas asserções pinadas)

**Interfaces:**
- Consumes: `run_audit(REAL_FIXTURE).model_dump(mode="json")`.

- [ ] **Step 1: Inspecionar os valores novos antes de congelar**

Run (a partir da raiz do repo, com `src` no `PYTHONPATH` — já configurado via `pyproject.toml`):

```bash
python -c "
from pathlib import Path
from product_b.oracle.commercial_auditor import run_audit
report = run_audit(Path('tests/fixtures/consultoria_real_test.xlsx'))
s = report.executive_summary
print('total_operational_loss:', s.total_operational_loss)
print('total_capital_frozen:', s.total_capital_frozen)
print('total_ltv_risk:', s.total_ltv_risk)
print('discarded_alarms:', [(a.category, a.entity_id) for a in s.discarded_alarms])
print('action_plan:', [(i.tier, i.nature, i.impact_brl) for i in s.action_plan])
"
```

Conferir manualmente contra a saída:
- `total_capital_frozen` deve bater exatamente com `35040.0` (mesmo valor já pinado em `test_key_findings_from_the_meeting_stay_pinned` para `dead_stock[0].capital_frozen`).
- `total_ltv_risk` deve bater exatamente com `92077.99` (mesmo valor já pinado para a soma de `churn_findings[].historical_annual_value`).
- `action_plan` deve ter natureza `operational` antes de `capital` antes de `ltv_risk` (tiers 1, 2, 3), e nenhuma entrada de natureza fora de `{operational, capital, ltv_risk}`.
- Estes três pontos já são garantidos automaticamente pelos testes da Task 4 — esta inspeção manual é a dupla-checagem exigida pela spec antes de tocar no golden master.

- [ ] **Step 2: Regenerar o golden master**

```bash
python -c "
import json
from pathlib import Path
from product_b.oracle.commercial_auditor import run_audit

report = run_audit(Path('tests/fixtures/consultoria_real_test.xlsx'))
dump = report.model_dump(mode='json')
dump.pop('generated_at', None)

out = Path('tests/fixtures/golden_laudo_v3.json')
out.write_text(json.dumps(dump, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')
print('regenerado:', out)
"
```

- [ ] **Step 3: Adicionar asserções pinadas para `executive_summary` em `test_key_findings_from_the_meeting_stay_pinned`**

Em `tests/test_golden_laudo_v3.py`, adicionar ao final da função `test_key_findings_from_the_meeting_stay_pinned` (depois da linha `assert len(gaps) == 2`):

```python
    summary = d["executive_summary"]
    assert round(summary["total_capital_frozen"], 2) == 35040.0
    assert round(summary["total_ltv_risk"], 2) == 92077.99
    assert [item["tier"] for item in summary["action_plan"]] == sorted(
        item["tier"] for item in summary["action_plan"]
    )
    assert {a["category"] for a in summary["discarded_alarms"]} <= {
        "salesperson_ramp", "store_cold_start",
    }
```

- [ ] **Step 4: Rodar a suíte completa**

Run: `python -m pytest tests/ -q`
Expected: `461 passed` (ou mais — as tasks anteriores adicionaram testes novos; o número exato deve ser maior que 461). Nenhum teste deve falhar. Se `test_laudo_matches_golden_master_exactly` ainda falhar aqui, o fixture não foi salvo corretamente no Step 2 — reexecutar o Step 2.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/golden_laudo_v3.json tests/test_golden_laudo_v3.py
git commit -m "test: regenera golden master v3 com executive_summary (verificado antes de congelar)"
```

---

## Definition of Done

- `python -m pytest tests/ -q` passa inteiro, sem nenhum teste pulado/quebrado.
- `ExecutiveAuditReport.executive_summary` é populado em toda chamada de `run_audit(...)`.
- `tests/fixtures/golden_laudo_v3.json` reflete o `executive_summary` real, verificado independentemente (Task 4) antes de ser congelado (Task 5).
- Nenhuma lógica de agregação nova foi duplicada fora de `build_executive_summary` (um único ponto de verdade para os 3 totais, `discarded_alarms` e `action_plan`).

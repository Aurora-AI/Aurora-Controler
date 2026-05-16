# Fase C — Gerador de Dashboards — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um pipeline determinístico C0→C4 que transforma um arquivo tabular (`.xlsx`/`.csv`) num dashboard executivo 4K, tendo o `DashboardSpec` JSON autocontido como artefato canônico.

**Architecture:** Cinco sub-fases sequenciais, cada uma lendo/escrevendo um artefato JSON: C0 (ingestão + un-pivot), C1 (modelo semântico), C2 (motor de métricas), C3 (recomendador + DashboardSpec), C4 (renderização HTML/PNG). Contratos Pydantic governam cada fronteira. A LLM é opcional e exclusiva da C3. C4 é um renderizador puro — só toca o `DashboardSpec`.

**Tech Stack:** Python 3.11+, pydantic v2, openpyxl, csv (stdlib), collections (stdlib), playwright (novo — só C4), pytest. Spec de referência: `docs/superpowers/specs/2026-05-16-phase-c-dashboard-generator-design.md`.

---

## Mapa de Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `libs/trustware/dashboard_contracts.py` | Todos os contratos Pydantic da Fase C (C0→C4) |
| `src/phase_c0/__init__.py` | Pacote C0 |
| `src/phase_c0/ingest.py` | Leitura de arquivo (.csv structured / .xlsx grid) → linhas cruas |
| `src/phase_c0/unpivot.py` | Detecção de estrutura, un-pivot, classificação de linhas, `C0Dataset` |
| `src/phase_c0/__main__.py` | Entry point standalone `python -m phase_c0 <arquivo>` |
| `src/phase_c1/__init__.py` | Pacote C1 |
| `src/phase_c1/semantic.py` | Inferência de tipo + `semantic_role` + `business_role` |
| `src/phase_c1/__main__.py` | Entry point `python -m phase_c1 output/<prefix>` |
| `src/phase_c2/__init__.py` | Pacote C2 |
| `src/phase_c2/aggregate.py` | Agregações group-by (Python puro) |
| `src/phase_c2/metrics.py` | Motor de KPI + validação + detecção de anomalias |
| `src/phase_c2/__main__.py` | Entry point `python -m phase_c2 output/<prefix>` |
| `src/phase_c3/__init__.py` | Pacote C3 |
| `src/phase_c3/catalog.py` | Lista `ChartRule` + `PREDICATE_REGISTRY` + `DATA_VIEW_BUILDER_REGISTRY` |
| `src/phase_c3/recommend.py` | `recommend()` — aplica catálogo, dedup por `analytical_intent` |
| `src/phase_c3/spec_builder.py` | Materializa `data_views`, monta `DashboardSpec` autocontido |
| `src/phase_c3/narrative.py` | Narrativa LLM opcional (atrás de flag) |
| `src/phase_c3/__main__.py` | Entry point `python -m phase_c3 output/<prefix> [--llm]` |
| `src/phase_c4/__init__.py` | Pacote C4 |
| `src/phase_c4/html_render.py` | `DashboardSpec` → HTML + ECharts |
| `src/phase_c4/screenshot.py` | Screenshot 4K via Playwright |
| `src/phase_c4/__main__.py` | Entry point `python -m phase_c4 output/<prefix>` |
| `tests/test_phase_c0.py` ... `test_phase_c4.py` | Testes unitários por fase |
| `run_pipeline.py` | Modificar — adicionar flag `--dashboard` |
| `requirements.txt` | Modificar — adicionar `playwright` |

**Convenção de prefixo:** todas as fases operam sobre `output/<stem>` onde `<stem>` é o nome do arquivo de entrada sem extensão. C0 recebe o arquivo bruto e deriva o prefixo; C1→C4 recebem o prefixo.

**Setup de `sys.path`:** cada `__main__.py` e cada arquivo de teste insere `libs/trustware` e o diretório `src/phase_cX` no `sys.path` — mesmo padrão das fases B.

---

## Task 1: Contratos C0 em `dashboard_contracts.py`

**Files:**
- Create: `libs/trustware/dashboard_contracts.py`
- Test: `tests/test_phase_c0.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_phase_c0.py`:

```python
"""Testes da Fase C0 — Ingestão + Un-pivot."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c0",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import (
    IngestionStrategy, DetectedStructure, SourceMapEntry,
    DiscardedRow, ValidationSummary, C0Dataset,
)


def test_ingestion_strategy_model():
    s = IngestionStrategy(primary="structured_model", fallback="grid_scraping",
                          used="grid_scraping", reason="pivot detected")
    assert s.used == "grid_scraping"


def test_validation_summary_closure_fields():
    v = ValidationSummary(total_rows_read=200, source_rows_emitted=120,
                          source_rows_context=25, source_rows_discarded=55,
                          dataset_rows_emitted=580)
    assert v.source_rows_emitted + v.source_rows_context + v.source_rows_discarded == v.total_rows_read
    assert v.warnings == []


def test_c0_dataset_roundtrip():
    ds = C0Dataset(
        source_file="Propostas.xlsx",
        ingestion_strategy=IngestionStrategy(primary="structured_model",
            fallback="grid_scraping", used="structured_model", reason="clean table"),
        detected_structure=DetectedStructure(table_kind="flat"),
        dataset=[{"row_id": 1, "cnpj": "X", "status": "Aprovado", "quantidade": 10}],
        source_map=[SourceMapEntry(row_id=1, origin_sheet="Plan1",
            origin_cells={"cnpj": "A2", "quantidade": "B2"})],
        discarded_rows=[DiscardedRow(origin_row=9, reason="grand_total", raw=["Total", 99])],
        validation_summary=ValidationSummary(total_rows_read=10, source_rows_emitted=8,
            source_rows_context=1, source_rows_discarded=1, dataset_rows_emitted=8),
    )
    assert ds.schema_version == "c0_dataset.v1"
    data = ds.model_dump()
    assert C0Dataset.model_validate(data).schema_version == "c0_dataset.v1"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c0.py -v`
Expected: `ModuleNotFoundError: No module named 'dashboard_contracts'`

- [ ] **Step 3: Criar `libs/trustware/dashboard_contracts.py` com os contratos C0**

```python
"""Contratos Pydantic da Fase C — Gerador de Dashboards.

Cada fronteira de fase (C0→C4) é governada por um contrato versionado.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ==========================================
# Fase C0 — Ingestão + Un-pivot
# ==========================================


class IngestionStrategy(BaseModel):
    """Registra qual estratégia de leitura a C0 usou."""
    primary: str = Field(..., description="Estratégia primária tentada")
    fallback: str = Field(..., description="Estratégia de fallback disponível")
    used: str = Field(..., description="Estratégia efetivamente usada")
    reason: str = Field(..., description="Por que essa estratégia foi escolhida")


class DetectedStructure(BaseModel):
    """Estrutura detectada na tabela de origem."""
    table_kind: str = Field(..., description="flat | wide | pivot_hierarchical")
    hierarchy: dict[str, str] = Field(default_factory=dict, description="parent/child")
    unpivot_source_columns: list[str] = Field(default_factory=list,
        description="Colunas largas que viraram valores de dimensão")
    canonical_dimension_from_columns: Optional[str] = Field(None,
        description="Nome da dimensão criada a partir das colunas largas")
    canonical_measure: Optional[str] = Field(None,
        description="Nome da measure canônica do modelo longo")
    subtotal_rows_detected: int = 0
    grand_total_row: Optional[int] = None


class SourceMapEntry(BaseModel):
    """Proveniência de uma linha do dataset: de qual célula veio cada campo."""
    row_id: int = Field(..., description="row_id correspondente em dataset")
    origin_sheet: str
    origin_cells: dict[str, str] = Field(...,
        description="campo -> referência de célula de origem")


class DiscardedRow(BaseModel):
    """Linha de origem descartada, com motivo auditável."""
    origin_row: int
    reason: str = Field(..., description="grand_total | subtotal | empty | malformed")
    raw: list[Any] = Field(..., description="Conteúdo bruto da linha descartada")


class ValidationSummary(BaseModel):
    """Resumo de contabilização de linhas da C0."""
    total_rows_read: int
    source_rows_emitted: int = Field(..., description="Linhas de origem que viraram dataset")
    source_rows_context: int = Field(..., description="Linhas de contexto (pai/cabeçalho)")
    source_rows_discarded: int = Field(..., description="Linhas descartadas")
    dataset_rows_emitted: int = Field(..., description="Linhas no dataset longo (independente)")
    warnings: list[str] = Field(default_factory=list)


class C0Dataset(BaseModel):
    """Artefato da C0: tabela longa limpa + proveniência completa."""
    schema_version: Literal["c0_dataset.v1"] = "c0_dataset.v1"
    source_file: str
    ingestion_strategy: IngestionStrategy
    detected_structure: DetectedStructure
    dataset: list[dict[str, Any]] = Field(..., description="Tabela longa canônica")
    source_map: list[SourceMapEntry]
    discarded_rows: list[DiscardedRow] = Field(default_factory=list)
    validation_summary: ValidationSummary
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c0.py -v`
Expected: 3 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add libs/trustware/dashboard_contracts.py tests/test_phase_c0.py
git commit -m "feat(c0): add C0 Pydantic contracts (C0Dataset and sub-models)"
```

---

## Task 2: Contratos C1 em `dashboard_contracts.py`

**Files:**
- Modify: `libs/trustware/dashboard_contracts.py` (append)
- Test: `tests/test_phase_c1.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_phase_c1.py`:

```python
"""Testes da Fase C1 — Modelo Semântico."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c1",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import SemanticField, SemanticModel


def test_semantic_field_model():
    f = SemanticField(name="cnpj", type="string", semantic_role="entity_id",
                      business_role="merchant_document", cardinality=47)
    assert f.semantic_role == "entity_id"
    assert f.business_role == "merchant_document"


def test_semantic_field_optional_business_role():
    f = SemanticField(name="perfil", type="category", semantic_role="breakdown_dimension")
    assert f.business_role is None


def test_semantic_model_roundtrip():
    m = SemanticModel(
        primary_dimension="cnpj", secondary_dimension="perfil",
        fields=[SemanticField(name="quantidade", type="integer", semantic_role="measure")],
    )
    assert m.schema_version == "c1_semantic.v1"
    assert SemanticModel.model_validate(m.model_dump()).primary_dimension == "cnpj"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c1.py -v`
Expected: `ImportError: cannot import name 'SemanticField'`

- [ ] **Step 3: Adicionar contratos C1 em `dashboard_contracts.py`**

Anexar ao final de `libs/trustware/dashboard_contracts.py`:

```python


# ==========================================
# Fase C1 — Modelo Semântico
# ==========================================


class SemanticField(BaseModel):
    """Papel semântico e de negócio de um campo da tabela longa."""
    name: str
    type: str = Field(..., description="string | integer | float | date | category")
    semantic_role: str = Field(...,
        description="entity_id | breakdown_dimension | measure | temporal | label")
    business_role: Optional[str] = Field(None,
        description="Papel de negócio inferido por heurística determinística")
    cardinality: Optional[int] = Field(None, description="Nº de valores distintos")


class SemanticModel(BaseModel):
    """Artefato da C1: papéis semânticos de todos os campos."""
    schema_version: Literal["c1_semantic.v1"] = "c1_semantic.v1"
    primary_dimension: Optional[str] = None
    secondary_dimension: Optional[str] = None
    fields: list[SemanticField]
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c1.py -v`
Expected: 3 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add libs/trustware/dashboard_contracts.py tests/test_phase_c1.py
git commit -m "feat(c1): add C1 semantic contracts (SemanticModel, SemanticField)"
```

---

## Task 3: Contratos C2 em `dashboard_contracts.py`

**Files:**
- Modify: `libs/trustware/dashboard_contracts.py` (append)
- Test: `tests/test_phase_c2.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_phase_c2.py`:

```python
"""Testes da Fase C2 — Motor de Métricas."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c2",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import KPI, AggregationRow, Aggregation, Anomaly, MetricsReport


def test_kpi_carries_evidence():
    k = KPI(metric="approval_rate", label="Taxa de Aprovação", value=0.2076,
            formula="sum(quantidade where status == 'Aprovado') / sum(quantidade)",
            numerator=769, denominator=3704, validation_status="ok")
    assert k.numerator == 769 and k.denominator == 3704


def test_aggregation_model():
    a = Aggregation(id="status_distribution", by="status", measure="quantidade",
                    rows=[AggregationRow(key="Aprovado", value=769)])
    assert a.rows[0].key == "Aprovado"


def test_metrics_report_roundtrip():
    r = MetricsReport(
        kpis=[KPI(metric="m", label="L", value=1.0, formula="f",
                  numerator=1, denominator=1, validation_status="ok")],
        aggregations=[Aggregation(id="a", by="status", measure="quantidade",
                                  rows=[AggregationRow(key="K", value=2)])],
        anomalies=[Anomaly(type="concentration", severity="high",
                           metric="m", evidence="evidência numérica")],
    )
    assert r.schema_version == "c2_metrics.v1"
    assert MetricsReport.model_validate(r.model_dump()).kpis[0].metric == "m"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c2.py -v`
Expected: `ImportError: cannot import name 'KPI'`

- [ ] **Step 3: Adicionar contratos C2 em `dashboard_contracts.py`**

Anexar ao final de `libs/trustware/dashboard_contracts.py`:

```python


# ==========================================
# Fase C2 — Motor de Métricas
# ==========================================


class KPI(BaseModel):
    """Indicador com evidência de cálculo completa."""
    metric: str
    label: str
    value: float
    formula: str = Field(..., description="Fórmula sobre o modelo longo")
    numerator: float
    denominator: float
    validation_status: str = Field(..., description="ok | mismatch | undefined")


class AggregationRow(BaseModel):
    """Uma linha de agregação: chave categórica + valor."""
    key: str
    value: float


class Aggregation(BaseModel):
    """Agregação group-by de uma measure por uma dimensão."""
    id: str
    by: str = Field(..., description="Dimensão agrupadora")
    measure: str = Field(..., description="Measure agregada")
    rows: list[AggregationRow]


class Anomaly(BaseModel):
    """Anomalia detectada, com evidência numérica obrigatória."""
    type: str = Field(..., description="concentration | outlier")
    severity: str = Field(..., description="low | medium | high")
    metric: str
    evidence: str = Field(..., description="Evidência numérica textual")


class MetricsReport(BaseModel):
    """Artefato da C2: KPIs + agregações + anomalias."""
    schema_version: Literal["c2_metrics.v1"] = "c2_metrics.v1"
    kpis: list[KPI]
    aggregations: list[Aggregation]
    anomalies: list[Anomaly] = Field(default_factory=list)
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c2.py -v`
Expected: 3 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add libs/trustware/dashboard_contracts.py tests/test_phase_c2.py
git commit -m "feat(c2): add C2 metrics contracts (MetricsReport, KPI, Aggregation, Anomaly)"
```

---

## Task 4: Contratos C3 em `dashboard_contracts.py`

**Files:**
- Modify: `libs/trustware/dashboard_contracts.py` (append)
- Test: `tests/test_phase_c3.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_phase_c3.py`:

```python
"""Testes da Fase C3 — Recomendador + DashboardSpec."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c3",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import (
    Resolution, DataView, DashboardComponent, Layout, NarrativeBlock,
    DashboardSpec, ChartRule, DashboardComponentSpec,
)


def test_data_view_typed():
    dv = DataView(kind="series", columns=["key", "value"],
                  rows=[{"key": "Aprovado", "value": 769}],
                  source={"aggregation_id": "status_distribution"})
    assert dv.kind == "series"


def test_chart_rule_carries_ids_not_functions():
    r = ChartRule(id="rule.status_distribution.horizontal_bar.v1", priority=20,
                  analytical_intent="status_distribution",
                  predicate_id="predicate.has_status_breakdown_and_measure.v1",
                  component_type="horizontal_bar",
                  data_view_builder_id="builder.status_distribution.v1")
    assert isinstance(r.predicate_id, str)
    assert isinstance(r.data_view_builder_id, str)


def test_dashboard_spec_roundtrip():
    spec = DashboardSpec(
        dashboard_id="d1", title="T", resolution=Resolution(),
        theme="executive_dark", llm_used=False,
        layout=Layout(kind="c_level_grid", rows=[["kpi_summary"]]),
        data_views={"kpis": DataView(kind="kpi_list", columns=["metric"],
                                     rows=[{"metric": "m"}])},
        components=[DashboardComponent(id="kpi_summary", type="kpi_cards",
            data_binding="data_views.kpis", analytical_intent="summary_kpis",
            generated_by_rule="rule.summary_kpis.kpi_cards.v1")],
    )
    assert spec.schema_version == "dashboard_spec.v1"
    assert spec.resolution.width == 3840
    assert DashboardSpec.model_validate(spec.model_dump()).dashboard_id == "d1"


def test_dashboard_component_spec_pair():
    cs = DashboardComponentSpec(
        component=DashboardComponent(id="c1", type="horizontal_bar",
            data_binding="data_views.c1", analytical_intent="status_distribution",
            generated_by_rule="rule.x.v1"),
        required_data_view=DataView(kind="series", columns=["key", "value"], rows=[]),
    )
    assert cs.component.id == "c1"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c3.py -v`
Expected: `ImportError: cannot import name 'Resolution'`

- [ ] **Step 3: Adicionar contratos C3 em `dashboard_contracts.py`**

Anexar ao final de `libs/trustware/dashboard_contracts.py`:

```python


# ==========================================
# Fase C3 — Recomendador + DashboardSpec
# ==========================================


class Resolution(BaseModel):
    """Resolução de renderização do dashboard."""
    width: int = 3840
    height: int = 2160


class DataView(BaseModel):
    """Bloco de dados tipado, materializado dentro do DashboardSpec."""
    kind: str = Field(..., description="series | kpi_list")
    columns: list[str]
    rows: list[dict[str, Any]]
    source: dict[str, Any] = Field(default_factory=dict,
        description="Rastro: de qual aggregation/kpi do C2 veio")


class DashboardComponent(BaseModel):
    """Um componente visual do dashboard."""
    id: str
    type: str = Field(..., description="kpi_cards | horizontal_bar | bar_ranking | heatmap | line | stacked_bar")
    data_binding: str = Field(..., description="Chave local: data_views.<nome>")
    analytical_intent: str
    generated_by_rule: str = Field(..., description="id da ChartRule que gerou")


class Layout(BaseModel):
    """Disposição em grade dos componentes."""
    kind: str = Field(..., description="c_level_grid | c_level_grid_dense")
    rows: list[list[str]] = Field(..., description="Grade de component ids")


class NarrativeBlock(BaseModel):
    """Bloco de narrativa executiva (gerado por LLM, opcional)."""
    level: str = Field(..., description="c_level | management | operational")
    text: str


class DashboardSpec(BaseModel):
    """Artefato canônico da Fase C — autocontido. C4 só toca este arquivo."""
    schema_version: Literal["dashboard_spec.v1"] = "dashboard_spec.v1"
    dashboard_id: str
    title: str
    resolution: Resolution
    theme: str
    llm_used: bool = False
    layout: Layout
    data_views: dict[str, DataView] = Field(...,
        description="Dados materializados; C4 resolve binding por lookup local")
    components: list[DashboardComponent]
    narrative: list[NarrativeBlock] = Field(default_factory=list)


class ChartRule(BaseModel):
    """Regra do catálogo de gráficos — carrega IDs estáveis, nunca funções."""
    id: str
    priority: int = Field(..., description="Numérica descendente: maior vence")
    analytical_intent: str
    predicate_id: str = Field(..., description="Chave em PREDICATE_REGISTRY")
    component_type: str
    data_view_builder_id: str = Field(..., description="Chave em DATA_VIEW_BUILDER_REGISTRY")


class DashboardComponentSpec(BaseModel):
    """Par emitido por uma ChartRule: componente + data_view exigido."""
    component: DashboardComponent
    required_data_view: DataView
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c3.py -v`
Expected: 4 tests PASSED.

- [ ] **Step 5: Rodar a suíte completa**

Run: `python -m pytest tests/ -q`
Expected: todos os testes passando (os anteriores + os 13 novos da Fase C).

- [ ] **Step 6: Commit**

```bash
git add libs/trustware/dashboard_contracts.py tests/test_phase_c3.py
git commit -m "feat(c3): add C3 contracts (DashboardSpec, DataView, ChartRule, etc.)"
```

---

## Task 5: C0 — Leitura de arquivo (`ingest.py`)

**Files:**
- Create: `src/phase_c0/__init__.py`
- Create: `src/phase_c0/ingest.py`
- Test: `tests/test_phase_c0.py` (append)

- [ ] **Step 1: Criar `src/phase_c0/__init__.py`**

```python
"""Fase C0 — Ingestão + Un-pivot."""
```

- [ ] **Step 2: Escrever o teste que falha**

Anexar a `tests/test_phase_c0.py`:

```python
# --- Task 5: ingest ---
import csv as _csv
from ingest import read_table


def test_read_table_csv(tmp_path):
    p = tmp_path / "dados.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
    sheet, rows = read_table(str(p))
    assert sheet == "dados"
    assert rows[0] == ["cnpj", "status", "quantidade"]
    assert rows[1] == ["X1", "Aprovado", "10"]


def test_read_table_rejects_unknown_format(tmp_path):
    p = tmp_path / "x.txt"
    p.write_text("nada", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        read_table(str(p))
```

- [ ] **Step 3: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c0.py -k read_table -v`
Expected: `ModuleNotFoundError: No module named 'ingest'`

- [ ] **Step 4: Criar `src/phase_c0/ingest.py`**

```python
"""Fase C0 — Leitura do arquivo de entrada (.csv / .xlsx)."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def read_table(path: str) -> tuple[str, list[list[Any]]]:
    """Lê .csv ou .xlsx e retorna (nome_da_aba, linhas).

    Cada linha é uma lista de células na ordem das colunas.
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".csv":
        import csv
        with p.open(encoding="utf-8", newline="") as fh:
            rows = [list(r) for r in csv.reader(fh)]
        return (p.stem, rows)

    if suffix in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(p, data_only=True, read_only=True)
        ws = wb.active
        rows = [list(row) for row in ws.iter_rows(values_only=True)]
        sheet = ws.title
        wb.close()
        return (sheet, rows)

    raise ValueError(f"Formato não suportado: {suffix}")
```

- [ ] **Step 5: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c0.py -k read_table -v`
Expected: 2 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/phase_c0/__init__.py src/phase_c0/ingest.py tests/test_phase_c0.py
git commit -m "feat(c0): add ingest.read_table for csv/xlsx input"
```

---

## Task 6: C0 — Detecção de estrutura + un-pivot wide (`unpivot.py`)

**Files:**
- Create: `src/phase_c0/unpivot.py`
- Test: `tests/test_phase_c0.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c0.py`:

```python
# --- Task 6: detecção + un-pivot wide ---
from unpivot import _is_number, classify_columns, detect_structure, unpivot_wide


def test_is_number_handles_locale():
    assert _is_number("1.234") is True
    assert _is_number("12,5") is True
    assert _is_number("Aprovado") is False
    assert _is_number(None) is False


def test_classify_columns_separates_dim_and_measure():
    header = ["cnpj", "Aprovado", "Reprovado"]
    data = [["X1", "10", "20"], ["X2", "5", "7"]]
    dim_idx, measure_idx = classify_columns(header, data)
    assert dim_idx == [0]
    assert measure_idx == [1, 2]


def test_detect_structure_wide():
    header = ["cnpj", "Aprovado", "Reprovado"]
    data = [["X1", "10", "20"]]
    s = detect_structure(header, data)
    assert s.table_kind == "wide"
    assert s.unpivot_source_columns == ["Aprovado", "Reprovado"]
    assert s.canonical_dimension_from_columns == "status"
    assert s.canonical_measure == "quantidade"


def test_detect_structure_flat():
    header = ["cnpj", "status", "quantidade"]
    data = [["X1", "Aprovado", "10"]]
    s = detect_structure(header, data)
    assert s.table_kind == "flat"


def test_unpivot_wide_emits_long_rows():
    header = ["cnpj", "Aprovado", "Reprovado"]
    data = [["X1", "10", "20"]]
    long_rows = unpivot_wide(header, data, [0], [1, 2])
    assert {"cnpj": "X1", "status": "Aprovado", "quantidade": 10.0} in long_rows
    assert {"cnpj": "X1", "status": "Reprovado", "quantidade": 20.0} in long_rows
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c0.py -k "is_number or classify or detect_structure or unpivot_wide" -v`
Expected: `ModuleNotFoundError: No module named 'unpivot'`

- [ ] **Step 3: Criar `src/phase_c0/unpivot.py`**

```python
"""Fase C0 — Detecção de estrutura e un-pivot para o modelo canônico longo."""
from __future__ import annotations

from typing import Any

from dashboard_contracts import DetectedStructure

# Valores que indicam linha de total geral (case-insensitive)
_GRAND_TOTAL_TOKENS = ("total geral", "grand total")


def _is_number(value: Any) -> bool:
    """True se o valor é numérico (aceita locale pt-BR: 1.234,56)."""
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return False
        s = s.replace(".", "").replace(",", ".")
        try:
            float(s)
            return True
        except ValueError:
            return False
    return False


def _to_number(value: Any) -> float:
    """Converte célula numérica em float (aceita locale pt-BR)."""
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(".", "").replace(",", ".")
    return float(s)


def classify_columns(
    header: list[str], data_rows: list[list[Any]]
) -> tuple[list[int], list[int]]:
    """Retorna (índices de colunas-dimensão, índices de colunas-measure).

    Uma coluna é measure se todos os seus valores não-vazios são numéricos.
    """
    dim_idx: list[int] = []
    measure_idx: list[int] = []
    for col in range(len(header)):
        values = [
            r[col] for r in data_rows
            if col < len(r) and r[col] not in (None, "")
        ]
        if values and all(_is_number(v) for v in values):
            measure_idx.append(col)
        else:
            dim_idx.append(col)
    return dim_idx, measure_idx


def detect_structure(
    header: list[str], data_rows: list[list[Any]]
) -> DetectedStructure:
    """Detecta se a tabela é `flat` (já longa) ou `wide` (precisa un-pivot)."""
    _, measure_idx = classify_columns(header, data_rows)
    if len(measure_idx) >= 2:
        return DetectedStructure(
            table_kind="wide",
            unpivot_source_columns=[header[i] for i in measure_idx],
            canonical_dimension_from_columns="status",
            canonical_measure="quantidade",
        )
    return DetectedStructure(table_kind="flat")


def unpivot_wide(
    header: list[str],
    data_rows: list[list[Any]],
    dim_idx: list[int],
    measure_idx: list[int],
) -> list[dict[str, Any]]:
    """Un-pivot: cada coluna-measure vira um valor da dimensão `status`.

    1 linha larga com N colunas-measure -> N linhas longas.
    """
    long_rows: list[dict[str, Any]] = []
    for row in data_rows:
        base = {header[i]: row[i] for i in dim_idx if i < len(row)}
        for mi in measure_idx:
            if mi >= len(row) or row[mi] in (None, ""):
                continue
            entry = dict(base)
            entry["status"] = header[mi]
            entry["quantidade"] = _to_number(row[mi])
            long_rows.append(entry)
    return long_rows
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c0.py -k "is_number or classify or detect_structure or unpivot_wide" -v`
Expected: 5 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/phase_c0/unpivot.py tests/test_phase_c0.py
git commit -m "feat(c0): add structure detection and wide un-pivot"
```

---

## Task 7: C0 — Montagem do `C0Dataset` (`build_c0_dataset`)

**Files:**
- Modify: `src/phase_c0/unpivot.py` (append)
- Test: `tests/test_phase_c0.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c0.py`:

```python
# --- Task 7: build_c0_dataset ---
from unpivot import build_c0_dataset


def test_build_c0_dataset_flat_csv(tmp_path):
    p = tmp_path / "flat.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
        w.writerow(["X2", "Reprovado", "20"])
    ds = build_c0_dataset(str(p))
    assert ds.ingestion_strategy.used == "structured_model"
    assert ds.detected_structure.table_kind == "flat"
    assert len(ds.dataset) == 2
    vs = ds.validation_summary
    assert vs.source_rows_emitted + vs.source_rows_context + vs.source_rows_discarded == vs.total_rows_read


def test_build_c0_dataset_wide_unpivot(tmp_path):
    p = tmp_path / "wide.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "Aprovado", "Reprovado"])
        w.writerow(["X1", "10", "20"])
    ds = build_c0_dataset(str(p))
    assert ds.ingestion_strategy.used == "grid_scraping"
    assert ds.detected_structure.table_kind == "wide"
    assert len(ds.dataset) == 2  # 1 linha larga -> 2 longas
    assert ds.validation_summary.dataset_rows_emitted == 2


def test_build_c0_dataset_discards_grand_total(tmp_path):
    p = tmp_path / "gt.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
        w.writerow(["Total Geral", "", "10"])
    ds = build_c0_dataset(str(p))
    assert len(ds.dataset) == 1
    assert any(d.reason == "grand_total" for d in ds.discarded_rows)


def test_build_c0_dataset_source_map_covers_dataset(tmp_path):
    p = tmp_path / "sm.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
    ds = build_c0_dataset(str(p))
    mapped_ids = {e.row_id for e in ds.source_map}
    dataset_ids = {r["row_id"] for r in ds.dataset}
    assert dataset_ids.issubset(mapped_ids)
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c0.py -k build_c0_dataset -v`
Expected: `ImportError: cannot import name 'build_c0_dataset'`

- [ ] **Step 3: Adicionar `build_c0_dataset` em `src/phase_c0/unpivot.py`**

Anexar ao final de `src/phase_c0/unpivot.py`:

```python


def _col_letter(idx: int) -> str:
    """Converte índice 0-based em letra de coluna estilo Excel (0->A, 1->B)."""
    letters = ""
    n = idx
    while True:
        letters = chr(ord("A") + n % 26) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return letters


def _is_grand_total(row: list[Any]) -> bool:
    """True se a linha é um total geral (primeira célula com token conhecido)."""
    if not row or row[0] in (None, ""):
        return False
    return any(tok in str(row[0]).strip().lower() for tok in _GRAND_TOTAL_TOKENS)


def _is_empty(row: list[Any]) -> bool:
    """True se todas as células da linha estão vazias."""
    return all(c in (None, "") for c in row)


def build_c0_dataset(path: str):
    """Lê o arquivo, detecta estrutura, un-pivota se preciso e monta o C0Dataset."""
    from ingest import read_table
    from dashboard_contracts import (
        C0Dataset, IngestionStrategy, SourceMapEntry,
        DiscardedRow, ValidationSummary,
    )

    sheet, raw_rows = read_table(path)
    if not raw_rows:
        raise ValueError(f"Arquivo vazio: {path}")

    header = [str(c) if c is not None else "" for c in raw_rows[0]]
    body = raw_rows[1:]
    total_rows_read = len(body)

    # Classificar linhas do corpo
    discarded: list[DiscardedRow] = []
    kept: list[tuple[int, list[Any]]] = []  # (origin_row_1based, row)
    for offset, row in enumerate(body):
        origin_row = offset + 2  # +1 header, +1 base-1
        if _is_empty(row):
            discarded.append(DiscardedRow(origin_row=origin_row, reason="empty", raw=list(row)))
        elif _is_grand_total(row):
            discarded.append(DiscardedRow(origin_row=origin_row, reason="grand_total", raw=list(row)))
        else:
            kept.append((origin_row, row))

    kept_rows = [r for _, r in kept]
    structure = detect_structure(header, kept_rows)
    dim_idx, measure_idx = classify_columns(header, kept_rows)

    # Emitir dataset longo
    dataset: list[dict[str, Any]] = []
    source_map: list[SourceMapEntry] = []
    row_id = 0

    if structure.table_kind == "wide":
        used, reason = "grid_scraping", "pivot-like wide table detected"
        for origin_row, row in kept:
            base = {header[i]: row[i] for i in dim_idx if i < len(row)}
            for mi in measure_idx:
                if mi >= len(row) or row[mi] in (None, ""):
                    continue
                row_id += 1
                entry = {"row_id": row_id, **base,
                         "status": header[mi], "quantidade": _to_number(row[mi])}
                dataset.append(entry)
                cells = {header[i]: f"{_col_letter(i)}{origin_row}"
                         for i in dim_idx if i < len(row)}
                cells["status"] = f"{_col_letter(mi)}1"
                cells["quantidade"] = f"{_col_letter(mi)}{origin_row}"
                source_map.append(SourceMapEntry(row_id=row_id, origin_sheet=sheet,
                                                 origin_cells=cells))
    else:
        used, reason = "structured_model", "clean flat table"
        for origin_row, row in kept:
            row_id += 1
            entry: dict[str, Any] = {"row_id": row_id}
            cells: dict[str, str] = {}
            for i, name in enumerate(header):
                if i >= len(row):
                    continue
                val = row[i]
                entry[name] = _to_number(val) if (i in measure_idx and _is_number(val)) else val
                cells[name] = f"{_col_letter(i)}{origin_row}"
            dataset.append(entry)
            source_map.append(SourceMapEntry(row_id=row_id, origin_sheet=sheet,
                                             origin_cells=cells))

    validation = ValidationSummary(
        total_rows_read=total_rows_read,
        source_rows_emitted=len(kept),
        source_rows_context=0,
        source_rows_discarded=len(discarded),
        dataset_rows_emitted=len(dataset),
    )

    return C0Dataset(
        source_file=path,
        ingestion_strategy=IngestionStrategy(
            primary="structured_model", fallback="grid_scraping",
            used=used, reason=reason),
        detected_structure=structure,
        dataset=dataset,
        source_map=source_map,
        discarded_rows=discarded,
        validation_summary=validation,
    )
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c0.py -k build_c0_dataset -v`
Expected: 4 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/phase_c0/unpivot.py tests/test_phase_c0.py
git commit -m "feat(c0): add build_c0_dataset with row classification and provenance"
```

---

## Task 8: C0 — Entry point (`__main__.py`)

**Files:**
- Create: `src/phase_c0/__main__.py`
- Test: `tests/test_phase_c0.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c0.py`:

```python
# --- Task 8: __main__ ---
import json as _json
import subprocess as _sub


def test_phase_c0_cli_writes_artifact(tmp_path):
    src = tmp_path / "Propostas.csv"
    with src.open("w", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["cnpj", "status", "quantidade"])
        w.writerow(["X1", "Aprovado", "10"])
    result = _sub.run(
        [sys.executable, "-m", "phase_c0", str(src)],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    out = src.with_name("Propostas_c0_dataset.json")
    assert out.exists()
    data = _json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "c0_dataset.v1"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c0.py -k cli -v`
Expected: FAIL — `returncode != 0` (módulo `phase_c0.__main__` não existe).

- [ ] **Step 3: Criar `src/phase_c0/__main__.py`**

```python
"""Fase C0 — Entry point. Uso: python -m phase_c0 <arquivo.xlsx|.csv>"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from unpivot import build_c0_dataset


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m phase_c0 <arquivo.xlsx|.csv>", file=sys.stderr)
        sys.exit(1)

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"Erro: arquivo não encontrado: {src}", file=sys.stderr)
        sys.exit(1)

    try:
        dataset = build_c0_dataset(str(src))
    except (ValueError, OSError) as exc:
        print(f"Erro ao ingerir {src}: {exc}", file=sys.stderr)
        sys.exit(1)

    out_path = src.with_name(f"{src.stem}_c0_dataset.json")
    out_path.write_text(dataset.model_dump_json(indent=2), encoding="utf-8")

    vs = dataset.validation_summary
    print(f"C0 OK: {src.name} -> {out_path.name}")
    print(f"  Estratégia: {dataset.ingestion_strategy.used}")
    print(f"  Estrutura : {dataset.detected_structure.table_kind}")
    print(f"  Dataset   : {vs.dataset_rows_emitted} linhas | "
          f"descartadas: {vs.source_rows_discarded}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c0.py -k cli -v`
Expected: PASS.

- [ ] **Step 5: Rodar a suíte completa**

Run: `python -m pytest tests/ -q`
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add src/phase_c0/__main__.py tests/test_phase_c0.py
git commit -m "feat(c0): add __main__ entry point — python -m phase_c0 <arquivo>"
```

---

## Task 9: C1 — Modelo semântico (`semantic.py`)

**Files:**
- Create: `src/phase_c1/__init__.py`
- Create: `src/phase_c1/semantic.py`
- Test: `tests/test_phase_c1.py` (append)

- [ ] **Step 1: Criar `src/phase_c1/__init__.py`**

```python
"""Fase C1 — Modelo Semântico."""
```

- [ ] **Step 2: Escrever o teste que falha**

Anexar a `tests/test_phase_c1.py`:

```python
# --- Task 9: semantic ---
from dashboard_contracts import C0Dataset, IngestionStrategy, DetectedStructure, ValidationSummary
from semantic import infer_type, infer_semantic_role, build_semantic_model


def _c0_fixture() -> C0Dataset:
    return C0Dataset(
        source_file="t.csv",
        ingestion_strategy=IngestionStrategy(primary="structured_model",
            fallback="grid_scraping", used="structured_model", reason="flat"),
        detected_structure=DetectedStructure(table_kind="flat"),
        dataset=[
            {"row_id": 1, "cnpj": "00.1/0001-01", "status": "Aprovado", "quantidade": 10.0},
            {"row_id": 2, "cnpj": "00.2/0001-02", "status": "Reprovado", "quantidade": 20.0},
        ],
        source_map=[], discarded_rows=[],
        validation_summary=ValidationSummary(total_rows_read=2, source_rows_emitted=2,
            source_rows_context=0, source_rows_discarded=0, dataset_rows_emitted=2),
    )


def test_infer_type_integer_and_category():
    assert infer_type([10.0, 20.0, 30.0]) == "integer"
    assert infer_type(["Aprovado", "Reprovado", "Aprovado"]) == "category"


def test_infer_semantic_role_measure_and_entity():
    assert infer_semantic_role("quantidade", "integer", None) == "measure"
    assert infer_semantic_role("cnpj", "string", 47) == "entity_id"


def test_build_semantic_model_assigns_roles():
    model = build_semantic_model(_c0_fixture())
    assert model.schema_version == "c1_semantic.v1"
    roles = {f.name: f.semantic_role for f in model.fields}
    assert roles["cnpj"] == "entity_id"
    assert roles["status"] == "breakdown_dimension"
    assert roles["quantidade"] == "measure"
    assert any(f.semantic_role == "measure" for f in model.fields)


def test_build_semantic_model_picks_primary_dimension():
    model = build_semantic_model(_c0_fixture())
    assert model.primary_dimension is not None
```

- [ ] **Step 3: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c1.py -k "infer or build_semantic" -v`
Expected: `ModuleNotFoundError: No module named 'semantic'`

- [ ] **Step 4: Criar `src/phase_c1/semantic.py`**

```python
"""Fase C1 — Inferência determinística de papéis semânticos."""
from __future__ import annotations

from typing import Any, Optional

from dashboard_contracts import C0Dataset, SemanticField, SemanticModel

_ENTITY_HINTS = ("cnpj", "cpf", "id", "codigo", "documento")
_TEMPORAL_HINTS = ("data", "date", "mes", "ano", "periodo")
_BUSINESS_ROLE_MAP = {
    "cnpj": "merchant_document",
    "cpf": "person_document",
    "status": "proposal_status",
    "quantidade": "record_count",
}


def _is_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        s = value.strip().replace(".", "").replace(",", ".")
        try:
            float(s)
            return True
        except ValueError:
            return False
    return False


def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).strip().replace(".", "").replace(",", "."))


def infer_type(values: list[Any]) -> str:
    """Infere o tipo de uma coluna: integer | float | category | string."""
    non_empty = [v for v in values if v not in (None, "")]
    if not non_empty:
        return "string"
    if all(_is_number(v) for v in non_empty):
        nums = [_as_float(v) for v in non_empty]
        return "integer" if all(n.is_integer() for n in nums) else "float"
    distinct = len({str(v) for v in non_empty})
    if distinct <= 20:
        return "category"
    return "string"


def infer_semantic_role(name: str, col_type: str, cardinality: Optional[int]) -> str:
    """Atribui semantic_role de forma determinística."""
    lname = name.lower()
    if col_type in ("integer", "float"):
        return "measure"
    if any(h in lname for h in _ENTITY_HINTS):
        return "entity_id"
    if any(h in lname for h in _TEMPORAL_HINTS):
        return "temporal"
    if col_type == "category":
        return "breakdown_dimension"
    return "label"


def _business_role(name: str) -> Optional[str]:
    lname = name.lower()
    for key, role in _BUSINESS_ROLE_MAP.items():
        if key in lname:
            return role
    return None


def build_semantic_model(c0: C0Dataset) -> SemanticModel:
    """Constrói o SemanticModel a partir do C0Dataset."""
    dataset = c0.dataset
    field_names = [k for k in dataset[0].keys() if k != "row_id"] if dataset else []

    fields: list[SemanticField] = []
    for name in field_names:
        values = [r.get(name) for r in dataset]
        col_type = infer_type(values)
        non_empty = [v for v in values if v not in (None, "")]
        cardinality = len({str(v) for v in non_empty})
        role = infer_semantic_role(name, col_type, cardinality)
        fields.append(SemanticField(
            name=name, type=col_type, semantic_role=role,
            business_role=_business_role(name),
            cardinality=None if role == "measure" else cardinality,
        ))

    dims = [f for f in fields if f.semantic_role in ("entity_id", "breakdown_dimension")]
    dims_sorted = sorted(dims, key=lambda f: f.cardinality or 0, reverse=True)
    primary = dims_sorted[0].name if dims_sorted else None
    secondary = dims_sorted[1].name if len(dims_sorted) > 1 else None

    return SemanticModel(
        primary_dimension=primary, secondary_dimension=secondary, fields=fields,
    )
```

- [ ] **Step 5: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c1.py -k "infer or build_semantic" -v`
Expected: 4 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/phase_c1/__init__.py src/phase_c1/semantic.py tests/test_phase_c1.py
git commit -m "feat(c1): add semantic role inference (build_semantic_model)"
```

---

## Task 10: C1 — Entry point (`__main__.py`)

**Files:**
- Create: `src/phase_c1/__main__.py`
- Test: `tests/test_phase_c1.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c1.py`:

```python
# --- Task 10: __main__ ---
import json as _json
import subprocess as _sub
import os as _os


def test_phase_c1_cli_writes_artifact(tmp_path):
    c0 = tmp_path / "T_c0_dataset.json"
    c0.write_text(_c0_fixture().model_dump_json(indent=2), encoding="utf-8")
    result = _sub.run(
        [sys.executable, "-m", "phase_c1", str(tmp_path / "T")],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**_os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    out = tmp_path / "T_c1_semantic.json"
    assert out.exists()
    assert _json.loads(out.read_text(encoding="utf-8"))["schema_version"] == "c1_semantic.v1"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c1.py -k cli -v`
Expected: FAIL — `returncode != 0`.

- [ ] **Step 3: Criar `src/phase_c1/__main__.py`**

```python
"""Fase C1 — Entry point. Uso: python -m phase_c1 output/<prefix>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dashboard_contracts import C0Dataset
from semantic import build_semantic_model


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m phase_c1 output/<prefix>", file=sys.stderr)
        sys.exit(1)

    prefix = Path(sys.argv[1])
    c0_path = Path(f"{prefix}_c0_dataset.json")
    if not c0_path.exists():
        print(f"Erro: arquivo não encontrado: {c0_path}", file=sys.stderr)
        sys.exit(1)

    try:
        c0 = C0Dataset.model_validate(json.loads(c0_path.read_text(encoding="utf-8")))
    except Exception as exc:  # JSONDecodeError | ValidationError
        print(f"Erro: C0Dataset inválido em {c0_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    model = build_semantic_model(c0)
    out_path = Path(f"{prefix}_c1_semantic.json")
    out_path.write_text(model.model_dump_json(indent=2), encoding="utf-8")

    print(f"C1 OK: {out_path.name}")
    print(f"  Campos: {len(model.fields)} | "
          f"dimensão primária: {model.primary_dimension}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c1.py -k cli -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phase_c1/__main__.py tests/test_phase_c1.py
git commit -m "feat(c1): add __main__ entry point — python -m phase_c1"
```

---

## Task 11: C2 — Motor de agregação (`aggregate.py`)

**Files:**
- Create: `src/phase_c2/__init__.py`
- Create: `src/phase_c2/aggregate.py`
- Test: `tests/test_phase_c2.py` (append)

- [ ] **Step 1: Criar `src/phase_c2/__init__.py`**

```python
"""Fase C2 — Motor de Métricas."""
```

- [ ] **Step 2: Escrever o teste que falha**

Anexar a `tests/test_phase_c2.py`:

```python
# --- Task 11: aggregate ---
from aggregate import aggregate_by

_DATASET = [
    {"row_id": 1, "cnpj": "X1", "status": "Aprovado", "quantidade": 10.0},
    {"row_id": 2, "cnpj": "X1", "status": "Reprovado", "quantidade": 20.0},
    {"row_id": 3, "cnpj": "X2", "status": "Aprovado", "quantidade": 5.0},
]


def test_aggregate_by_status():
    agg = aggregate_by(_DATASET, by="status", measure="quantidade", agg_id="status_distribution")
    rows = {r.key: r.value for r in agg.rows}
    assert rows["Aprovado"] == 15.0
    assert rows["Reprovado"] == 20.0
    assert agg.id == "status_distribution"


def test_aggregate_by_entity():
    agg = aggregate_by(_DATASET, by="cnpj", measure="quantidade", agg_id="cnpj_ranking")
    rows = {r.key: r.value for r in agg.rows}
    assert rows["X1"] == 30.0
    assert rows["X2"] == 5.0
```

- [ ] **Step 3: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c2.py -k aggregate -v`
Expected: `ModuleNotFoundError: No module named 'aggregate'`

- [ ] **Step 4: Criar `src/phase_c2/aggregate.py`**

```python
"""Fase C2 — Agregações group-by em Python puro.

Limite operacional do MVP: até 100.000 linhas normalizadas. Acima disso,
o pipeline deve emitir warning de escala (ver build_metrics_report).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from dashboard_contracts import Aggregation, AggregationRow


def aggregate_by(
    dataset: list[dict[str, Any]], by: str, measure: str, agg_id: str
) -> Aggregation:
    """Soma `measure` agrupando por `by`. Retorna Aggregation ordenada desc."""
    sums: dict[str, float] = defaultdict(float)
    for row in dataset:
        key = str(row.get(by, ""))
        value = row.get(measure, 0.0)
        if isinstance(value, (int, float)):
            sums[key] += float(value)
    rows = [
        AggregationRow(key=k, value=v)
        for k, v in sorted(sums.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return Aggregation(id=agg_id, by=by, measure=measure, rows=rows)
```

- [ ] **Step 5: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c2.py -k aggregate -v`
Expected: 2 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/phase_c2/__init__.py src/phase_c2/aggregate.py tests/test_phase_c2.py
git commit -m "feat(c2): add group-by aggregation engine"
```

---

## Task 12: C2 — Motor de métricas (`metrics.py`)

**Files:**
- Create: `src/phase_c2/metrics.py`
- Test: `tests/test_phase_c2.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c2.py`:

```python
# --- Task 12: metrics ---
from dashboard_contracts import (
    C0Dataset, IngestionStrategy, DetectedStructure, ValidationSummary,
    SemanticModel, SemanticField,
)
from metrics import compute_kpis, detect_anomalies, build_metrics_report


def _c0() -> C0Dataset:
    return C0Dataset(
        source_file="t.csv",
        ingestion_strategy=IngestionStrategy(primary="structured_model",
            fallback="grid_scraping", used="structured_model", reason="flat"),
        detected_structure=DetectedStructure(table_kind="flat"),
        dataset=list(_DATASET), source_map=[], discarded_rows=[],
        validation_summary=ValidationSummary(total_rows_read=3, source_rows_emitted=3,
            source_rows_context=0, source_rows_discarded=0, dataset_rows_emitted=3),
    )


def _c1() -> SemanticModel:
    return SemanticModel(primary_dimension="cnpj", secondary_dimension="status",
        fields=[
            SemanticField(name="cnpj", type="string", semantic_role="entity_id", cardinality=2),
            SemanticField(name="status", type="category", semantic_role="breakdown_dimension",
                          business_role="proposal_status", cardinality=2),
            SemanticField(name="quantidade", type="integer", semantic_role="measure"),
        ])


def test_compute_kpis_rate_over_long_model():
    kpis = compute_kpis(list(_DATASET), _c1())
    by_metric = {k.metric: k for k in kpis}
    assert "total_quantidade" in by_metric
    assert by_metric["total_quantidade"].value == 35.0
    aprov = by_metric["aprovado_rate"]
    assert abs(aprov.value - 15.0 / 35.0) < 1e-9
    assert aprov.numerator == 15.0 and aprov.denominator == 35.0
    assert aprov.validation_status == "ok"


def test_detect_anomalies_concentration():
    skewed = [
        {"row_id": 1, "status": "Reprovado", "quantidade": 90.0},
        {"row_id": 2, "status": "Aprovado", "quantidade": 10.0},
    ]
    kpis = compute_kpis(skewed, _c1())
    anomalies = detect_anomalies(skewed, _c1(), kpis)
    assert any(a.type == "concentration" for a in anomalies)


def test_build_metrics_report_complete():
    report = build_metrics_report(_c0(), _c1())
    assert report.schema_version == "c2_metrics.v1"
    assert len(report.kpis) >= 1
    assert any(a.id == "status_distribution" for a in report.aggregations)


def test_kpi_division_by_zero_is_undefined():
    empty = []
    kpis = compute_kpis(empty, _c1())
    total = {k.metric: k for k in kpis}.get("total_quantidade")
    assert total is not None and total.value == 0.0
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c2.py -k "compute_kpis or anomalies or build_metrics or division" -v`
Expected: `ModuleNotFoundError: No module named 'metrics'`

- [ ] **Step 3: Criar `src/phase_c2/metrics.py`**

```python
"""Fase C2 — Motor de KPIs, validação e detecção de anomalias.

Toda fórmula opera sobre o modelo canônico longo: nunca assume colunas
físicas de status. KPIs carregam fórmula, numerador, denominador e validação.
"""
from __future__ import annotations

import sys
import unicodedata
from typing import Any

from dashboard_contracts import (
    Aggregation, Anomaly, C0Dataset, KPI, MetricsReport, SemanticModel,
)
from aggregate import aggregate_by

_SCALE_LIMIT = 100_000
_CONCENTRATION_THRESHOLD = 0.5


def _slug(text: str) -> str:
    """Normaliza um rótulo em chave ASCII minúscula (Aprovado -> aprovado)."""
    norm = unicodedata.normalize("NFKD", str(text))
    ascii_text = norm.encode("ascii", "ignore").decode("ascii")
    return ascii_text.strip().lower().replace(" ", "_")


def _measure_field(semantic: SemanticModel) -> str:
    for f in semantic.fields:
        if f.semantic_role == "measure":
            return f.name
    return "quantidade"


def _status_field(semantic: SemanticModel) -> str | None:
    for f in semantic.fields:
        if f.business_role == "proposal_status":
            return f.name
    for f in semantic.fields:
        if f.semantic_role == "breakdown_dimension":
            return f.name
    return None


def compute_kpis(dataset: list[dict[str, Any]], semantic: SemanticModel) -> list[KPI]:
    """Calcula KPIs sobre o modelo longo: total da measure + taxa por categoria."""
    measure = _measure_field(semantic)
    status = _status_field(semantic)
    total = sum(float(r.get(measure, 0.0)) for r in dataset
                if isinstance(r.get(measure), (int, float)))

    kpis: list[KPI] = [KPI(
        metric=f"total_{measure}", label=f"Total de {measure}", value=total,
        formula=f"sum({measure})", numerator=total, denominator=total,
        validation_status="ok",
    )]

    if status is None:
        return kpis

    per_cat: dict[str, float] = {}
    for r in dataset:
        val = r.get(measure, 0.0)
        if isinstance(val, (int, float)):
            per_cat[str(r.get(status, ""))] = per_cat.get(str(r.get(status, "")), 0.0) + float(val)

    parts_sum = sum(per_cat.values())
    for cat, num in per_cat.items():
        if total == 0:
            value, vstatus = 0.0, "undefined"
        else:
            value, vstatus = num / total, ("ok" if abs(parts_sum - total) < 1e-9 else "mismatch")
        kpis.append(KPI(
            metric=f"{_slug(cat)}_rate", label=f"Taxa de {cat}", value=value,
            formula=f"sum({measure} where {status} == '{cat}') / sum({measure})",
            numerator=num, denominator=total, validation_status=vstatus,
        ))
    return kpis


def detect_anomalies(
    dataset: list[dict[str, Any]], semantic: SemanticModel, kpis: list[KPI]
) -> list[Anomaly]:
    """Detecta concentração: alguma categoria de status acima de 50% do total."""
    anomalies: list[Anomaly] = []
    for k in kpis:
        if k.metric.endswith("_rate") and k.value > _CONCENTRATION_THRESHOLD:
            anomalies.append(Anomaly(
                type="concentration", severity="high", metric=k.metric,
                evidence=f"{k.value * 100:.1f}% concentrado em {k.label}",
            ))
    return anomalies


def build_metrics_report(c0: C0Dataset, semantic: SemanticModel) -> MetricsReport:
    """Monta o MetricsReport: KPIs + agregações + anomalias.

    Acima de _SCALE_LIMIT linhas, emite aviso de escala em stderr.
    """
    dataset = c0.dataset
    measure = _measure_field(semantic)
    if len(dataset) > _SCALE_LIMIT:
        print(f"[C2] Aviso de escala: {len(dataset)} linhas acima do limite "
              f"de {_SCALE_LIMIT} — considerar backend analítico futuro",
              file=sys.stderr)

    aggregations: list[Aggregation] = []
    for f in semantic.fields:
        if f.semantic_role == "breakdown_dimension":
            aggregations.append(aggregate_by(dataset, f.name, measure, f"{f.name}_distribution"))
        elif f.semantic_role == "entity_id":
            aggregations.append(aggregate_by(dataset, f.name, measure, f"{f.name}_ranking"))

    kpis = compute_kpis(dataset, semantic)
    anomalies = detect_anomalies(dataset, semantic, kpis)
    return MetricsReport(kpis=kpis, aggregations=aggregations, anomalies=anomalies)
```

> Nota: `_status_field` reusa `proposal_status` quando disponível; o `status_distribution`
> esperado pela C3 sai de uma `breakdown_dimension` chamada `status`.

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c2.py -k "compute_kpis or anomalies or build_metrics or division" -v`
Expected: 4 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/phase_c2/metrics.py tests/test_phase_c2.py
git commit -m "feat(c2): add KPI engine, validation and anomaly detection"
```

---

## Task 13: C2 — Entry point (`__main__.py`)

**Files:**
- Create: `src/phase_c2/__main__.py`
- Test: `tests/test_phase_c2.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c2.py`:

```python
# --- Task 13: __main__ ---
import json as _json
import subprocess as _sub
import os as _os


def test_phase_c2_cli_writes_artifact(tmp_path):
    (tmp_path / "T_c0_dataset.json").write_text(_c0().model_dump_json(indent=2), encoding="utf-8")
    (tmp_path / "T_c1_semantic.json").write_text(_c1().model_dump_json(indent=2), encoding="utf-8")
    result = _sub.run(
        [sys.executable, "-m", "phase_c2", str(tmp_path / "T")],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**_os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    out = tmp_path / "T_c2_metrics.json"
    assert out.exists()
    assert _json.loads(out.read_text(encoding="utf-8"))["schema_version"] == "c2_metrics.v1"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c2.py -k cli -v`
Expected: FAIL — `returncode != 0`.

- [ ] **Step 3: Criar `src/phase_c2/__main__.py`**

```python
"""Fase C2 — Entry point. Uso: python -m phase_c2 output/<prefix>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dashboard_contracts import C0Dataset, SemanticModel
from metrics import build_metrics_report


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m phase_c2 output/<prefix>", file=sys.stderr)
        sys.exit(1)

    prefix = Path(sys.argv[1])
    c0_path = Path(f"{prefix}_c0_dataset.json")
    c1_path = Path(f"{prefix}_c1_semantic.json")
    for path in (c0_path, c1_path):
        if not path.exists():
            print(f"Erro: arquivo não encontrado: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        c0 = C0Dataset.model_validate(json.loads(c0_path.read_text(encoding="utf-8")))
        c1 = SemanticModel.model_validate(json.loads(c1_path.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"Erro: artefato inválido: {exc}", file=sys.stderr)
        sys.exit(1)

    report = build_metrics_report(c0, c1)
    out_path = Path(f"{prefix}_c2_metrics.json")
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print(f"C2 OK: {out_path.name}")
    print(f"  KPIs: {len(report.kpis)} | agregações: {len(report.aggregations)} "
          f"| anomalias: {len(report.anomalies)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c2.py -k cli -v`
Expected: PASS.

- [ ] **Step 5: Rodar a suíte completa**

Run: `python -m pytest tests/ -q`
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add src/phase_c2/__main__.py tests/test_phase_c2.py
git commit -m "feat(c2): add __main__ entry point — python -m phase_c2"
```

---

> **Escopo do catálogo no MVP:** o catálogo implementa 3 regras — `summary_kpis`,
> `status_distribution`, `entity_ranking` — que cobrem 100% do exemplo canônico
> (CNPJ × status). As outras 3 intents da spec (`cross_breakdown`/heatmap,
> `temporal_trend`/line, `category_composition`/stacked_bar) são adições futuras:
> a arquitetura de registry torna cada uma um `ChartRule` + 1 predicado + 1 builder.

## Task 14: C3 — Catálogo de gráficos (`catalog.py`)

**Files:**
- Create: `src/phase_c3/__init__.py`
- Create: `src/phase_c3/catalog.py`
- Test: `tests/test_phase_c3.py` (append)

- [ ] **Step 1: Criar `src/phase_c3/__init__.py`**

```python
"""Fase C3 — Recomendador de Gráficos + DashboardSpec."""
```

- [ ] **Step 2: Escrever o teste que falha**

Anexar a `tests/test_phase_c3.py`:

```python
# --- Task 14: catalog ---
from dashboard_contracts import (
    MetricsReport, KPI, Aggregation, AggregationRow, SemanticModel, SemanticField,
)
from catalog import (
    CHART_RULES, PREDICATE_REGISTRY, DATA_VIEW_BUILDER_REGISTRY,
)


def _metrics() -> MetricsReport:
    return MetricsReport(
        kpis=[KPI(metric="total_quantidade", label="Total", value=35.0,
                  formula="sum(quantidade)", numerator=35, denominator=35,
                  validation_status="ok")],
        aggregations=[
            Aggregation(id="status_distribution", by="status", measure="quantidade",
                        rows=[AggregationRow(key="Aprovado", value=15.0),
                              AggregationRow(key="Reprovado", value=20.0)]),
            Aggregation(id="cnpj_ranking", by="cnpj", measure="quantidade",
                        rows=[AggregationRow(key="X1", value=30.0),
                              AggregationRow(key="X2", value=5.0)]),
        ],
    )


def _semantic() -> SemanticModel:
    return SemanticModel(primary_dimension="cnpj", secondary_dimension="status",
        fields=[SemanticField(name="quantidade", type="integer", semantic_role="measure")])


def test_every_rule_has_registered_predicate_and_builder():
    for rule in CHART_RULES:
        assert rule.predicate_id in PREDICATE_REGISTRY
        assert rule.data_view_builder_id in DATA_VIEW_BUILDER_REGISTRY


def test_predicates_fire_on_fixture():
    sem, met = _semantic(), _metrics()
    assert PREDICATE_REGISTRY["predicate.has_kpis.v1"](sem, met) is True
    assert PREDICATE_REGISTRY["predicate.has_status_breakdown_and_measure.v1"](sem, met) is True
    assert PREDICATE_REGISTRY["predicate.has_entity_and_measure.v1"](sem, met) is True


def test_builder_status_distribution_produces_series():
    dv = DATA_VIEW_BUILDER_REGISTRY["builder.status_distribution.v1"](_semantic(), _metrics())
    assert dv.kind == "series"
    assert dv.columns == ["key", "value"]
    assert {"key": "Aprovado", "value": 15.0} in dv.rows
    assert dv.source["aggregation_id"] == "status_distribution"
```

- [ ] **Step 3: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c3.py -k "rule or predicate or builder" -v`
Expected: `ModuleNotFoundError: No module named 'catalog'`

- [ ] **Step 4: Criar `src/phase_c3/catalog.py`**

```python
"""Fase C3 — Catálogo de regras de gráfico (dado versionado).

Cada ChartRule carrega IDs estáveis (predicate_id, data_view_builder_id)
resolvidos por registries. Nunca carrega funções Python diretamente.
"""
from __future__ import annotations

from typing import Callable

from dashboard_contracts import ChartRule, DataView, MetricsReport, SemanticModel

_RANKING_LIMIT = 15

Predicate = Callable[[SemanticModel, MetricsReport], bool]
Builder = Callable[[SemanticModel, MetricsReport], DataView]


# --------------------------------------------------------------------------
# Predicados — determinísticos, puros
# --------------------------------------------------------------------------
def _has_kpis(semantic: SemanticModel, metrics: MetricsReport) -> bool:
    return len(metrics.kpis) > 0


def _has_status_breakdown(semantic: SemanticModel, metrics: MetricsReport) -> bool:
    return any(a.id.endswith("_distribution") for a in metrics.aggregations)


def _has_entity_ranking(semantic: SemanticModel, metrics: MetricsReport) -> bool:
    return any(a.id.endswith("_ranking") for a in metrics.aggregations)


PREDICATE_REGISTRY: dict[str, Predicate] = {
    "predicate.has_kpis.v1": _has_kpis,
    "predicate.has_status_breakdown_and_measure.v1": _has_status_breakdown,
    "predicate.has_entity_and_measure.v1": _has_entity_ranking,
}


# --------------------------------------------------------------------------
# Builders de data_view — materializam dados do C2 num DataView tipado
# --------------------------------------------------------------------------
def _fmt_kpi(value: float, metric: str) -> str:
    if metric.endswith("_rate"):
        return f"{value * 100:.1f}%".replace(".", ",")
    return f"{value:,.0f}".replace(",", ".")


def _build_kpi_list(semantic: SemanticModel, metrics: MetricsReport) -> DataView:
    rows = [
        {"metric": k.metric, "label": k.label, "value": k.value,
         "display_value": _fmt_kpi(k.value, k.metric)}
        for k in metrics.kpis
    ]
    return DataView(
        kind="kpi_list", columns=["metric", "label", "value", "display_value"],
        rows=rows, source={"kpi_ids": [k.metric for k in metrics.kpis]},
    )


def _first_agg(metrics: MetricsReport, suffix: str):
    for a in metrics.aggregations:
        if a.id.endswith(suffix):
            return a
    raise ValueError(f"Nenhuma agregação com sufixo {suffix}")


def _build_status_distribution(semantic: SemanticModel, metrics: MetricsReport) -> DataView:
    agg = _first_agg(metrics, "_distribution")
    rows = [{"key": r.key, "value": r.value} for r in agg.rows]
    return DataView(kind="series", columns=["key", "value"], rows=rows,
                    source={"aggregation_id": agg.id})


def _build_entity_ranking(semantic: SemanticModel, metrics: MetricsReport) -> DataView:
    agg = _first_agg(metrics, "_ranking")
    rows = [{"key": r.key, "value": r.value} for r in agg.rows[:_RANKING_LIMIT]]
    return DataView(kind="series", columns=["key", "value"], rows=rows,
                    source={"aggregation_id": agg.id})


DATA_VIEW_BUILDER_REGISTRY: dict[str, Builder] = {
    "builder.kpi_list.v1": _build_kpi_list,
    "builder.status_distribution.v1": _build_status_distribution,
    "builder.entity_ranking.v1": _build_entity_ranking,
}


# --------------------------------------------------------------------------
# Catálogo — prioridade numérica descendente (maior vence)
# --------------------------------------------------------------------------
CHART_RULES: list[ChartRule] = [
    ChartRule(
        id="rule.summary_kpis.kpi_cards.v1", priority=100,
        analytical_intent="summary_kpis",
        predicate_id="predicate.has_kpis.v1",
        component_type="kpi_cards",
        data_view_builder_id="builder.kpi_list.v1",
    ),
    ChartRule(
        id="rule.status_distribution.horizontal_bar.v1", priority=80,
        analytical_intent="status_distribution",
        predicate_id="predicate.has_status_breakdown_and_measure.v1",
        component_type="horizontal_bar",
        data_view_builder_id="builder.status_distribution.v1",
    ),
    ChartRule(
        id="rule.entity_ranking.bar_ranking.v1", priority=60,
        analytical_intent="entity_ranking",
        predicate_id="predicate.has_entity_and_measure.v1",
        component_type="bar_ranking",
        data_view_builder_id="builder.entity_ranking.v1",
    ),
]
```

- [ ] **Step 5: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c3.py -k "rule or predicate or builder" -v`
Expected: 3 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/phase_c3/__init__.py src/phase_c3/catalog.py tests/test_phase_c3.py
git commit -m "feat(c3): add chart rule catalog with predicate/builder registries"
```

---

## Task 15: C3 — Recomendador (`recommend.py`)

**Files:**
- Create: `src/phase_c3/recommend.py`
- Test: `tests/test_phase_c3.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c3.py`:

```python
# --- Task 15: recommend ---
from recommend import recommend


def test_recommend_returns_component_specs():
    specs = recommend(_semantic(), _metrics())
    intents = {s.component.analytical_intent for s in specs}
    assert intents == {"summary_kpis", "status_distribution", "entity_ranking"}


def test_recommend_one_component_per_intent():
    specs = recommend(_semantic(), _metrics())
    intents = [s.component.analytical_intent for s in specs]
    assert len(intents) == len(set(intents))


def test_recommend_each_spec_has_data_view_and_rule():
    specs = recommend(_semantic(), _metrics())
    for s in specs:
        assert s.required_data_view.rows is not None
        assert s.component.generated_by_rule.startswith("rule.")
        assert s.component.data_binding == f"data_views.{s.component.id}"


def test_recommend_ordered_by_priority():
    specs = recommend(_semantic(), _metrics())
    # summary_kpis (100) vem antes de status_distribution (80) antes de entity_ranking (60)
    assert specs[0].component.analytical_intent == "summary_kpis"
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c3.py -k recommend -v`
Expected: `ModuleNotFoundError: No module named 'recommend'`

- [ ] **Step 3: Criar `src/phase_c3/recommend.py`**

```python
"""Fase C3 — Recomendação determinística de componentes.

Aplica o catálogo, deduplica por analytical_intent (maior priority vence),
e materializa o data_view de cada componente escolhido.
"""
from __future__ import annotations

from dashboard_contracts import (
    DashboardComponent, DashboardComponentSpec, MetricsReport, SemanticModel,
)
from catalog import CHART_RULES, DATA_VIEW_BUILDER_REGISTRY, PREDICATE_REGISTRY


def recommend(
    semantic: SemanticModel, metrics: MetricsReport
) -> list[DashboardComponentSpec]:
    """Retorna a lista de DashboardComponentSpec — componente + data_view."""
    # Dedup por intent: cada intent fica com a regra de maior priority
    chosen: dict[str, object] = {}
    for rule in CHART_RULES:
        predicate = PREDICATE_REGISTRY[rule.predicate_id]
        if not predicate(semantic, metrics):
            continue
        current = chosen.get(rule.analytical_intent)
        if current is None or rule.priority > current.priority:
            chosen[rule.analytical_intent] = rule

    ordered = sorted(chosen.values(), key=lambda r: -r.priority)

    specs: list[DashboardComponentSpec] = []
    for rule in ordered:
        builder = DATA_VIEW_BUILDER_REGISTRY[rule.data_view_builder_id]
        data_view = builder(semantic, metrics)
        component = DashboardComponent(
            id=rule.analytical_intent,
            type=rule.component_type,
            data_binding=f"data_views.{rule.analytical_intent}",
            analytical_intent=rule.analytical_intent,
            generated_by_rule=rule.id,
        )
        specs.append(DashboardComponentSpec(
            component=component, required_data_view=data_view))
    return specs
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c3.py -k recommend -v`
Expected: 4 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/phase_c3/recommend.py tests/test_phase_c3.py
git commit -m "feat(c3): add recommend — applies catalog, dedup by intent"
```

---

## Task 16: C3 — Montagem do DashboardSpec (`spec_builder.py`)

**Files:**
- Create: `src/phase_c3/spec_builder.py`
- Test: `tests/test_phase_c3.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c3.py`:

```python
# --- Task 16: spec_builder ---
from spec_builder import build_dashboard_spec, validate_spec_self_contained


def test_build_dashboard_spec_is_self_contained():
    spec = build_dashboard_spec(_semantic(), _metrics(),
                                dashboard_id="d1", title="Análise")
    assert spec.schema_version == "dashboard_spec.v1"
    # todo componente tem data_view materializado
    for comp in spec.components:
        assert comp.id in spec.data_views
    # todo id do layout tem componente correspondente
    comp_ids = {c.id for c in spec.components}
    for row in spec.layout.rows:
        for cid in row:
            assert cid in comp_ids


def test_build_dashboard_spec_layout_puts_kpis_first():
    spec = build_dashboard_spec(_semantic(), _metrics(), dashboard_id="d1", title="T")
    assert spec.layout.rows[0] == ["summary_kpis"]


def test_validate_spec_self_contained_passes():
    spec = build_dashboard_spec(_semantic(), _metrics(), dashboard_id="d1", title="T")
    validate_spec_self_contained(spec)  # não levanta exceção


def test_validate_spec_self_contained_catches_missing_binding():
    spec = build_dashboard_spec(_semantic(), _metrics(), dashboard_id="d1", title="T")
    del spec.data_views[spec.components[0].id]
    import pytest
    with pytest.raises(ValueError):
        validate_spec_self_contained(spec)


def test_build_dashboard_spec_no_llm_empty_narrative():
    spec = build_dashboard_spec(_semantic(), _metrics(), dashboard_id="d1",
                                title="T", llm_used=False)
    assert spec.narrative == []
    assert spec.llm_used is False
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c3.py -k "dashboard_spec or self_contained" -v`
Expected: `ModuleNotFoundError: No module named 'spec_builder'`

- [ ] **Step 3: Criar `src/phase_c3/spec_builder.py`**

```python
"""Fase C3 — Montagem do DashboardSpec autocontido.

O DashboardSpec sai daqui com todos os data_views materializados.
A C4 nunca precisa abrir o C2.
"""
from __future__ import annotations

from dashboard_contracts import (
    DashboardComponent, DashboardSpec, DataView, Layout, MetricsReport,
    Resolution, SemanticModel,
)
from recommend import recommend


def _build_layout(components: list[DashboardComponent]) -> Layout:
    """KPIs na primeira linha; demais componentes em pares."""
    kpi_ids = [c.id for c in components if c.type == "kpi_cards"]
    other_ids = [c.id for c in components if c.type != "kpi_cards"]
    rows: list[list[str]] = []
    if kpi_ids:
        rows.append(kpi_ids)
    for i in range(0, len(other_ids), 2):
        rows.append(other_ids[i:i + 2])
    if not rows:
        rows = [[c.id for c in components]]
    return Layout(kind="c_level_grid", rows=rows)


def validate_spec_self_contained(spec: DashboardSpec) -> None:
    """Garante que todo componente e todo id de layout têm data_view e componente.

    Levanta ValueError se a regra de autocontenção for violada.
    """
    comp_ids = {c.id for c in spec.components}
    for comp in spec.components:
        if comp.id not in spec.data_views:
            raise ValueError(f"Componente '{comp.id}' sem data_view materializado")
    for row in spec.layout.rows:
        for cid in row:
            if cid not in comp_ids:
                raise ValueError(f"Layout referencia '{cid}' sem componente")


def build_dashboard_spec(
    semantic: SemanticModel,
    metrics: MetricsReport,
    dashboard_id: str,
    title: str,
    theme: str = "executive_dark",
    llm_used: bool = False,
) -> DashboardSpec:
    """Monta o DashboardSpec autocontido a partir de C1 + C2."""
    specs = recommend(semantic, metrics)

    data_views: dict[str, DataView] = {}
    components: list[DashboardComponent] = []
    for s in specs:
        data_views[s.component.id] = s.required_data_view
        components.append(s.component)

    spec = DashboardSpec(
        dashboard_id=dashboard_id, title=title, resolution=Resolution(),
        theme=theme, llm_used=llm_used, layout=_build_layout(components),
        data_views=data_views, components=components, narrative=[],
    )
    validate_spec_self_contained(spec)
    return spec
```

- [ ] **Step 4: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c3.py -k "dashboard_spec or self_contained" -v`
Expected: 5 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/phase_c3/spec_builder.py tests/test_phase_c3.py
git commit -m "feat(c3): add spec_builder — self-contained DashboardSpec assembly"
```

---

## Task 17: C3 — Narrativa LLM opcional + entry point

**Files:**
- Create: `src/phase_c3/narrative.py`
- Create: `src/phase_c3/__main__.py`
- Test: `tests/test_phase_c3.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_phase_c3.py`:

```python
# --- Task 17: narrative + __main__ ---
import json as _json
import subprocess as _sub
import os as _os
from narrative import build_narrative_prompt


def test_build_narrative_prompt_includes_kpis():
    prompt = build_narrative_prompt(_metrics())
    assert "total_quantidade" in prompt
    assert "Total" in prompt


def test_phase_c3_cli_writes_spec_without_llm(tmp_path):
    sem = _semantic()
    met = _metrics()
    (tmp_path / "T_c1_semantic.json").write_text(sem.model_dump_json(indent=2), encoding="utf-8")
    (tmp_path / "T_c2_metrics.json").write_text(met.model_dump_json(indent=2), encoding="utf-8")
    result = _sub.run(
        [sys.executable, "-m", "phase_c3", str(tmp_path / "T")],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**_os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    out = tmp_path / "T_c3_dashboard_spec.json"
    assert out.exists()
    data = _json.loads(out.read_text(encoding="utf-8"))
    assert data["schema_version"] == "dashboard_spec.v1"
    assert data["llm_used"] is False
    assert data["narrative"] == []
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c3.py -k "narrative_prompt or cli" -v`
Expected: `ModuleNotFoundError: No module named 'narrative'`

- [ ] **Step 3: Criar `src/phase_c3/narrative.py`**

```python
"""Fase C3 — Narrativa executiva opcional via LLM.

A LLM só redige texto (títulos, narrativa). Nunca calcula números nem
altera data_views. Sem LLM disponível, retorna lista vazia.
"""
from __future__ import annotations

from dashboard_contracts import MetricsReport, NarrativeBlock


def build_narrative_prompt(metrics: MetricsReport) -> str:
    """Monta o prompt da narrativa a partir dos KPIs e anomalias do C2."""
    lines = ["Você é um analista executivo. Com base nos indicadores abaixo,",
             "escreva 2 frases de leitura executiva. Não invente números.\n",
             "KPIs:"]
    for k in metrics.kpis:
        lines.append(f"- {k.metric} ({k.label}): {k.value}")
    if metrics.anomalies:
        lines.append("Anomalias:")
        for a in metrics.anomalies:
            lines.append(f"- {a.evidence}")
    return "\n".join(lines)


def generate_narrative(metrics: MetricsReport) -> list[NarrativeBlock]:
    """Gera a narrativa via LLM. Qualquer falha resulta em lista vazia."""
    prompt = build_narrative_prompt(metrics)
    try:
        from litellm import completion
        resp = completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp["choices"][0]["message"]["content"].strip()
        return [NarrativeBlock(level="c_level", text=text)]
    except Exception:
        return []
```

- [ ] **Step 4: Criar `src/phase_c3/__main__.py`**

```python
"""Fase C3 — Entry point. Uso: python -m phase_c3 output/<prefix> [--llm]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dashboard_contracts import MetricsReport, SemanticModel
from spec_builder import build_dashboard_spec, validate_spec_self_contained
from narrative import generate_narrative


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_llm = "--llm" in sys.argv
    if not args:
        print("Uso: python -m phase_c3 output/<prefix> [--llm]", file=sys.stderr)
        sys.exit(1)

    prefix = Path(args[0])
    c1_path = Path(f"{prefix}_c1_semantic.json")
    c2_path = Path(f"{prefix}_c2_metrics.json")
    for path in (c1_path, c2_path):
        if not path.exists():
            print(f"Erro: arquivo não encontrado: {path}", file=sys.stderr)
            sys.exit(1)

    try:
        c1 = SemanticModel.model_validate(json.loads(c1_path.read_text(encoding="utf-8")))
        c2 = MetricsReport.model_validate(json.loads(c2_path.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"Erro: artefato inválido: {exc}", file=sys.stderr)
        sys.exit(1)

    spec = build_dashboard_spec(
        c1, c2, dashboard_id=prefix.name, title=f"Dashboard — {prefix.name}",
        llm_used=use_llm,
    )
    if use_llm:
        spec.narrative = generate_narrative(c2)
        spec.llm_used = bool(spec.narrative)

    validate_spec_self_contained(spec)

    out_path = Path(f"{prefix}_c3_dashboard_spec.json")
    out_path.write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    print(f"C3 OK: {out_path.name}")
    print(f"  Componentes: {len(spec.components)} | LLM: {spec.llm_used}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c3.py -k "narrative_prompt or cli" -v`
Expected: 2 tests PASSED.

- [ ] **Step 6: Rodar a suíte completa**

Run: `python -m pytest tests/ -q`
Expected: todos passando.

- [ ] **Step 7: Commit**

```bash
git add src/phase_c3/narrative.py src/phase_c3/__main__.py tests/test_phase_c3.py
git commit -m "feat(c3): add optional LLM narrative and __main__ entry point"
```

---

## Task 18: C4 — Renderização HTML (`html_render.py`)

**Files:**
- Create: `src/phase_c4/__init__.py`
- Create: `src/phase_c4/html_render.py`
- Test: `tests/test_phase_c4.py`

- [ ] **Step 1: Criar `src/phase_c4/__init__.py`**

```python
"""Fase C4 — Renderização HTML + PNG 4K."""
```

- [ ] **Step 2: Escrever o teste que falha**

Criar `tests/test_phase_c4.py`:

```python
"""Testes da Fase C4 — Renderização."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_c4",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import (
    DashboardSpec, DataView, DashboardComponent, Layout, Resolution,
)
from html_render import render_html


def _spec() -> DashboardSpec:
    return DashboardSpec(
        dashboard_id="d1", title="Análise de Propostas", resolution=Resolution(),
        theme="executive_dark", llm_used=False,
        layout=Layout(kind="c_level_grid",
                      rows=[["summary_kpis"], ["status_distribution"]]),
        data_views={
            "summary_kpis": DataView(kind="kpi_list",
                columns=["metric", "label", "value", "display_value"],
                rows=[{"metric": "total", "label": "Total", "value": 35.0,
                       "display_value": "35"}]),
            "status_distribution": DataView(kind="series", columns=["key", "value"],
                rows=[{"key": "Aprovado", "value": 15.0}]),
        },
        components=[
            DashboardComponent(id="summary_kpis", type="kpi_cards",
                data_binding="data_views.summary_kpis",
                analytical_intent="summary_kpis",
                generated_by_rule="rule.summary_kpis.kpi_cards.v1"),
            DashboardComponent(id="status_distribution", type="horizontal_bar",
                data_binding="data_views.status_distribution",
                analytical_intent="status_distribution",
                generated_by_rule="rule.status_distribution.horizontal_bar.v1"),
        ],
    )


def test_render_html_contains_title():
    html = render_html(_spec())
    assert "Análise de Propostas" in html


def test_render_html_has_container_per_component():
    html = render_html(_spec())
    assert 'id="comp-summary_kpis"' in html
    assert 'id="comp-status_distribution"' in html


def test_render_html_embeds_spec_and_echarts():
    html = render_html(_spec())
    assert "echarts" in html
    assert "data_views" in html  # SPEC embutido como JSON


def test_render_html_sets_4k_dimensions():
    html = render_html(_spec())
    assert "3840" in html and "2160" in html
```

- [ ] **Step 3: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c4.py -k render_html -v`
Expected: `ModuleNotFoundError: No module named 'html_render'`

- [ ] **Step 4: Criar `src/phase_c4/html_render.py`**

```python
"""Fase C4 — Renderização do DashboardSpec em HTML + ECharts.

C4 é renderizador puro: lê o DashboardSpec, monta o HTML. Não calcula,
não interpreta, não altera o spec.
"""
from __future__ import annotations

import json

from dashboard_contracts import DashboardSpec

_ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"

_RENDER_JS = """
SPEC.components.forEach(function (comp) {
  var el = document.getElementById('comp-' + comp.id);
  if (!el) return;
  var dv = SPEC.data_views[comp.id];
  if (!dv) return;
  if (comp.type === 'kpi_cards') {
    el.className = 'kpi-row';
    dv.rows.forEach(function (r) {
      var card = document.createElement('div');
      card.className = 'kpi';
      card.innerHTML = '<div class="label">' + r.label + '</div>' +
        '<div class="value">' + (r.display_value || r.value) + '</div>';
      el.appendChild(card);
    });
  } else {
    var chart = echarts.init(el, 'dark');
    var keys = dv.rows.map(function (r) { return r.key; });
    var vals = dv.rows.map(function (r) { return r.value; });
    chart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 240, right: 80, top: 32, bottom: 32 },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: keys.slice().reverse() },
      series: [{ type: 'bar', data: vals.slice().reverse(),
                 itemStyle: { color: '#3b82f6' } }]
    });
  }
});
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<script src="__ECHARTS__"></script>
<style>
  body { margin:0; background:#0e1117; color:#e6e6e6;
         font-family:'Segoe UI',Arial,sans-serif;
         width:__WIDTH__px; height:__HEIGHT__px; }
  h1 { padding:32px 48px 0; font-size:44px; font-weight:700; }
  .grid { display:flex; flex-direction:column; gap:24px; padding:24px 48px; }
  .row { display:flex; gap:24px; }
  .panel { flex:1; background:#161b22; border-radius:12px; height:560px; }
  .kpi-row { display:flex; gap:24px; flex:1; }
  .kpi { flex:1; background:#161b22; border-radius:12px; padding:36px; }
  .kpi .label { font-size:26px; color:#8b949e; }
  .kpi .value { font-size:68px; font-weight:700; margin-top:12px; }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<div class="grid">__GRID__</div>
<script>
const SPEC = __SPEC_JSON__;
__RENDER_JS__
</script>
</body>
</html>
"""


def render_html(spec: DashboardSpec) -> str:
    """Renderiza o DashboardSpec num documento HTML autocontido."""
    comp_by_id = {c.id: c for c in spec.components}

    grid = ""
    for row in spec.layout.rows:
        cells = ""
        for cid in row:
            comp = comp_by_id.get(cid)
            if comp is None:
                continue
            css = "kpi-row" if comp.type == "kpi_cards" else "panel"
            cells += f'<div class="{css}" id="comp-{cid}"></div>'
        grid += f'<div class="row">{cells}</div>'

    spec_json = json.dumps(spec.model_dump(), ensure_ascii=False)

    html = _TEMPLATE
    html = html.replace("__TITLE__", spec.title)
    html = html.replace("__ECHARTS__", _ECHARTS_CDN)
    html = html.replace("__WIDTH__", str(spec.resolution.width))
    html = html.replace("__HEIGHT__", str(spec.resolution.height))
    html = html.replace("__GRID__", grid)
    html = html.replace("__SPEC_JSON__", spec_json)
    html = html.replace("__RENDER_JS__", _RENDER_JS)
    return html
```

- [ ] **Step 5: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c4.py -k render_html -v`
Expected: 4 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/phase_c4/__init__.py src/phase_c4/html_render.py tests/test_phase_c4.py
git commit -m "feat(c4): add html_render — DashboardSpec to HTML+ECharts"
```

---

## Task 19: C4 — Screenshot 4K + entry point

**Files:**
- Create: `src/phase_c4/screenshot.py`
- Create: `src/phase_c4/__main__.py`
- Modify: `requirements.txt`
- Test: `tests/test_phase_c4.py` (append)

- [ ] **Step 1: Adicionar `playwright` ao `requirements.txt`**

O `requirements.txt` atual termina com `pytest>=8.0`. Adicionar uma linha:

```
playwright>=1.40
```

Após a edição, o engenheiro deve rodar (uma única vez): `playwright install chromium`.

- [ ] **Step 2: Escrever o teste que falha**

Anexar a `tests/test_phase_c4.py`:

```python
# --- Task 19: screenshot + __main__ ---
import json as _json
import subprocess as _sub
import os as _os
import pytest as _pytest


def test_render_png_rejects_missing_html(tmp_path):
    from screenshot import render_png
    with _pytest.raises(FileNotFoundError):
        render_png(str(tmp_path / "inexistente.html"), str(tmp_path / "x.png"))


def test_phase_c4_cli_writes_html(tmp_path):
    spec = _spec()
    (tmp_path / "T_c3_dashboard_spec.json").write_text(
        spec.model_dump_json(indent=2), encoding="utf-8")
    result = _sub.run(
        [sys.executable, "-m", "phase_c4", str(tmp_path / "T"), "--no-png"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**_os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "T_c4_dashboard.html").exists()


@_pytest.mark.integration
def test_render_png_produces_4k(tmp_path):
    """Teste de integração real — requer 'playwright install chromium'."""
    playwright = _pytest.importorskip("playwright")
    from html_render import render_html
    from screenshot import render_png
    html_path = tmp_path / "d.html"
    html_path.write_text(render_html(_spec()), encoding="utf-8")
    png_path = tmp_path / "d.png"
    try:
        render_png(str(html_path), str(png_path))
    except Exception as exc:  # browser não instalado
        _pytest.skip(f"Chromium indisponível: {exc}")
    assert png_path.exists()
    from PIL import Image  # opcional; se ausente, valida só existência
```

> Nota: o marcador `@pytest.mark.integration` deve ser registrado em `pytest.ini`
> ou `pyproject.toml`. Se o projeto não tiver config de markers, adicionar ao
> `pytest.ini` a seção `[pytest]` com `markers = integration: testes que exigem browser`.
> Os testes de integração rodam com `python -m pytest -m integration`.

- [ ] **Step 3: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_phase_c4.py -k "render_png_rejects or c4_cli" -v`
Expected: `ModuleNotFoundError: No module named 'screenshot'`

- [ ] **Step 4: Criar `src/phase_c4/screenshot.py`**

```python
"""Fase C4 — Screenshot 4K do dashboard via Playwright (Chromium headless)."""
from __future__ import annotations

from pathlib import Path


def render_png(
    html_path: str, png_path: str, width: int = 3840, height: int = 2160
) -> None:
    """Abre o HTML em Chromium headless e salva um screenshot PNG.

    Requer: pip install playwright && playwright install chromium.
    """
    html_file = Path(html_path)
    if not html_file.exists():
        raise FileNotFoundError(f"HTML não encontrado: {html_path}")

    from playwright.sync_api import sync_playwright

    url = html_file.resolve().as_uri()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1500)  # deixa o ECharts terminar de desenhar
        page.screenshot(path=png_path)
        browser.close()
```

- [ ] **Step 5: Criar `src/phase_c4/__main__.py`**

```python
"""Fase C4 — Entry point. Uso: python -m phase_c4 output/<prefix> [--no-png]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
for _p in [str(_HERE), str(_REPO / "libs" / "trustware")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dashboard_contracts import DashboardSpec
from html_render import render_html
from screenshot import render_png


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skip_png = "--no-png" in sys.argv
    if not args:
        print("Uso: python -m phase_c4 output/<prefix> [--no-png]", file=sys.stderr)
        sys.exit(1)

    prefix = Path(args[0])
    spec_path = Path(f"{prefix}_c3_dashboard_spec.json")
    if not spec_path.exists():
        print(f"Erro: arquivo não encontrado: {spec_path}", file=sys.stderr)
        sys.exit(1)

    try:
        spec = DashboardSpec.model_validate(
            json.loads(spec_path.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"Erro: DashboardSpec inválido: {exc}", file=sys.stderr)
        sys.exit(1)

    html_path = Path(f"{prefix}_c4_dashboard.html")
    html_path.write_text(render_html(spec), encoding="utf-8")
    print(f"C4: HTML -> {html_path.name}")

    if skip_png:
        print("C4: PNG pulado (--no-png).")
        return

    png_path = Path(f"{prefix}_c4_dashboard.png")
    try:
        render_png(str(html_path), str(png_path))
        print(f"C4: PNG 4K -> {png_path.name}")
    except Exception as exc:
        print(f"Aviso: PNG não gerado ({exc}). "
              f"Rode 'playwright install chromium'.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_phase_c4.py -k "render_png_rejects or c4_cli" -v`
Expected: 2 tests PASSED.

- [ ] **Step 7: Rodar a suíte completa (sem testes de integração)**

Run: `python -m pytest tests/ -q -m "not integration"`
Expected: todos passando.

- [ ] **Step 8: Commit**

```bash
git add src/phase_c4/screenshot.py src/phase_c4/__main__.py requirements.txt tests/test_phase_c4.py
git commit -m "feat(c4): add Playwright 4K screenshot and __main__ entry point"
```

---

## Task 20: Integração — `run_pipeline.py --dashboard`

**Files:**
- Modify: `run_pipeline.py`
- Test: `tests/test_integration.py` (append)

- [ ] **Step 1: Escrever o teste que falha**

Anexar a `tests/test_integration.py`:

```python
# --- Fase C: pipeline de dashboard ---
def test_run_dashboard_pipeline(tmp_path):
    """C0->C3 end-to-end a partir de um CSV (sem PNG, sem LLM)."""
    import csv
    import sys as _sys
    src_dir = REPO_ROOT / "src"
    for _p in ["phase_c0", "phase_c1", "phase_c2", "phase_c3", "phase_c4"]:
        p = str(src_dir / _p)
        if p not in _sys.path:
            _sys.path.insert(0, p)

    from run_pipeline import run_dashboard

    csv_path = tmp_path / "Propostas.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cnpj", "Aprovado", "Reprovado"])
        w.writerow(["X1", "10", "20"])
        w.writerow(["X2", "5", "7"])

    run_dashboard(csv_path, use_llm=False, render_png=False)

    stem = csv_path.with_suffix("")
    for suffix in ["_c0_dataset.json", "_c1_semantic.json",
                   "_c2_metrics.json", "_c3_dashboard_spec.json",
                   "_c4_dashboard.html"]:
        assert Path(f"{stem}{suffix}").exists(), f"faltou {suffix}"

    import json
    spec = json.loads(Path(f"{stem}_c3_dashboard_spec.json").read_text(encoding="utf-8"))
    assert spec["schema_version"] == "dashboard_spec.v1"
    comp_ids = {c["id"] for c in spec["components"]}
    for view_id in spec["data_views"]:
        assert view_id in comp_ids  # autocontido: todo data_view tem componente
```

- [ ] **Step 2: Rodar e confirmar que FALHA**

Run: `python -m pytest tests/test_integration.py -k run_dashboard -v`
Expected: `ImportError: cannot import name 'run_dashboard'`

- [ ] **Step 3: Adicionar `run_dashboard` em `run_pipeline.py`**

Adicionar a função abaixo em `run_pipeline.py`, após a função `run` existente:

```python
def _setup_c_paths():
    """Adiciona os módulos das fases C ao sys.path."""
    for phase in ["phase_c0", "phase_c1", "phase_c2", "phase_c3", "phase_c4"]:
        p = str(REPO_ROOT / "src" / phase)
        if p not in sys.path:
            sys.path.insert(0, p)


def run_dashboard(xlsx_path: Path, use_llm: bool = False, render_png: bool = True):
    """Pipeline de dashboard C0->C4 sobre um arquivo tabular."""
    _setup_c_paths()
    from unpivot import build_c0_dataset
    from semantic import build_semantic_model
    from metrics import build_metrics_report
    from spec_builder import build_dashboard_spec, validate_spec_self_contained
    from narrative import generate_narrative
    from html_render import render_html

    stem = xlsx_path.with_suffix("")
    print("\n" + "=" * 60)
    print(f"  Dashboard Pipeline — {xlsx_path.name}")
    print("=" * 60)

    # C0
    c0 = build_c0_dataset(str(xlsx_path))
    Path(f"{stem}_c0_dataset.json").write_text(
        c0.model_dump_json(indent=2), encoding="utf-8")
    print(f"[C0] {c0.detected_structure.table_kind} | "
          f"{c0.validation_summary.dataset_rows_emitted} linhas")

    # C1
    c1 = build_semantic_model(c0)
    Path(f"{stem}_c1_semantic.json").write_text(
        c1.model_dump_json(indent=2), encoding="utf-8")
    print(f"[C1] {len(c1.fields)} campos | dimensão primária: {c1.primary_dimension}")

    # C2
    c2 = build_metrics_report(c0, c1)
    Path(f"{stem}_c2_metrics.json").write_text(
        c2.model_dump_json(indent=2), encoding="utf-8")
    print(f"[C2] {len(c2.kpis)} KPIs | {len(c2.anomalies)} anomalias")

    # C3
    spec = build_dashboard_spec(c1, c2, dashboard_id=xlsx_path.stem,
                                title=f"Dashboard — {xlsx_path.stem}",
                                llm_used=use_llm)
    if use_llm:
        spec.narrative = generate_narrative(c2)
        spec.llm_used = bool(spec.narrative)
    validate_spec_self_contained(spec)
    Path(f"{stem}_c3_dashboard_spec.json").write_text(
        spec.model_dump_json(indent=2), encoding="utf-8")
    print(f"[C3] {len(spec.components)} componentes | LLM: {spec.llm_used}")

    # C4
    html_path = Path(f"{stem}_c4_dashboard.html")
    html_path.write_text(render_html(spec), encoding="utf-8")
    print(f"[C4] HTML -> {html_path.name}")
    if render_png:
        from screenshot import render_png as _render_png
        png_path = Path(f"{stem}_c4_dashboard.png")
        try:
            _render_png(str(html_path), str(png_path))
            print(f"[C4] PNG 4K -> {png_path.name}")
        except Exception as exc:
            print(f"[C4] Aviso: PNG não gerado ({exc})", file=sys.stderr)

    print(f"\n[DONE] Dashboard gerado. Artefatos em: {stem.parent}")
```

- [ ] **Step 4: Ligar a flag `--dashboard` no bloco `__main__` de `run_pipeline.py`**

No bloco `if __name__ == "__main__":` de `run_pipeline.py`, localizar o `argparse` e
adicionar o argumento e o desvio. O bloco final deve ficar assim:

```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EXRS Full Pipeline Runner")
    parser.add_argument("xlsx", type=Path, help="Caminho para o arquivo .xlsx")
    parser.add_argument("--llm", action="store_true", help="Ativar LLM")
    parser.add_argument("--hitl", action="store_true", help="Ativar simulação HITL (B3)")
    parser.add_argument("--dashboard", action="store_true",
                        help="Rodar o pipeline de dashboard (Fase C: C0->C4)")
    args = parser.parse_args()

    if not args.xlsx.exists():
        print(f"Erro: arquivo não encontrado: {args.xlsx}")
        sys.exit(1)

    if args.dashboard:
        run_dashboard(args.xlsx, use_llm=args.llm)
    else:
        run(args.xlsx, skip_llm=not args.llm, run_hitl_flag=args.hitl)
```

> Atenção: este bloco substitui o `if __name__ == "__main__":` existente. Preservar
> os argumentos `--llm` e `--hitl` já presentes; apenas adicionar `--dashboard` e o
> desvio `if args.dashboard`.

- [ ] **Step 5: Rodar e confirmar que PASSA**

Run: `python -m pytest tests/test_integration.py -k run_dashboard -v`
Expected: PASS — os 5 artefatos C0→C4 (html) criados.

- [ ] **Step 6: Rodar a suíte completa**

Run: `python -m pytest tests/ -q -m "not integration"`
Expected: todos passando.

- [ ] **Step 7: Commit**

```bash
git add run_pipeline.py tests/test_integration.py
git commit -m "feat(c): wire run_dashboard C0->C4 into run_pipeline --dashboard"
```

---

## Critérios de Aceite Finais

Ao completar todas as 20 tarefas, verificar:

1. `python run_pipeline.py <arquivo.xlsx> --dashboard` gera os 5 artefatos C0→C4.
2. O `DashboardSpec` é autocontido — `python -m phase_c4 output/<prefix>` roda sem
   acessar nenhum arquivo C2.
3. Todo KPI no `c2_metrics.json` tem `formula`, `numerator`, `denominator`,
   `validation_status`.
4. Toda linha de origem é contabilizada (`emitted + context + discarded == total`).
5. Sem `--llm`, o `DashboardSpec` tem `narrative: []` e `llm_used: false`.
6. A suíte `python -m pytest tests/ -q -m "not integration"` passa inteira.
7. CI verde no GitHub Actions.
8. Teste de integração real do PNG: `playwright install chromium` e depois
   `python -m pytest tests/ -m integration` produz um PNG 3840×2160.

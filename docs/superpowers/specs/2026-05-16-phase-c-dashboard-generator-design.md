# Fase C — Gerador de Dashboards — Documento de Design

> **Status:** Aprovado (Seções 1, 2 e 3 travadas com ajustes incorporados).
> **Data:** 2026-05-16
> **Produto:** Excel Reverse Engineering System — missão "transformar planilhas em Apps".
> **Próximo passo:** este design vira plano de execução via `superpowers:writing-plans`.

---

## 1. Objetivo da Fase C

A Fase C é um **pipeline determinístico e independente** para geração de dashboards
executivos a partir de dados tabulares. Recebe um arquivo (`.xlsx` ou `.csv`),
entende e organiza os dados, calcula métricas auditáveis e produz um dashboard
4K renderizado.

A Fase C é o segundo estágio da missão do produto:

| Estágio | O quê | Status |
|---|---|---|
| Entender a lógica | ExcelReverseEngine A0→A4, B1→B3 (fórmulas, regras) | Construído |
| Ver / organizar / calcular dados + gerar dashboards | **Fase C — este design** | A construir |

A Fase C **não depende** das Fases A e B. Trabalha direto sobre dados. Roda
standalone até num CSV puro.

---

## 2. Princípios arquiteturais

1. **O artefato canônico é o `DashboardSpec` JSON.** O HTML e o PNG 4K são apenas
   renderizações derivadas. Determinismo, auditabilidade e testabilidade vivem no spec.
2. **`DashboardSpec` é autocontido.** Sai da C3 com os `data_views` já materializados.
   A C4 toca **apenas** o `DashboardSpec` — nunca abre a C2, nunca resolve binding,
   nunca calcula, nunca interpreta.
3. **C4 é burro.** C4 não pensa, não calcula, não interpreta. Apenas renderiza.
4. **Toda fase é determinística.** A LLM é um enriquecimento opcional, exclusivo da
   C3, atrás da flag `--llm`. Sem LLM, o pipeline entrega o dashboard completo.
5. **Proveniência é trava de auditoria.** Todo valor extraído preserva origem.
   Nenhuma linha é descartada sem registro de motivo.
6. **Modelo canônico longo.** Após a C0, o padrão de dado é sempre tabela longa
   (`dimensão... | measure`), nunca tabela larga com colunas de status.
7. **Cada arquivo tem uma responsabilidade.** Unidades pequenas, interfaces claras.
8. **Os testes validam o spec, não os pixels.**

---

## 3. Fluxo C0→C4

```
arquivo.xlsx / .csv
        |  C0  — Ingestão + un-pivot
{stem}_c0_dataset.json        tabela longa + proveniencia + estrategia de ingestao
        |  C1  — Modelo semantico
{stem}_c1_semantic.json       papeis semanticos e de negocio de cada campo
        |  C2  — Motor de metricas
{stem}_c2_metrics.json        KPIs + agregacoes + anomalias, com evidencia
        |  C3  — Recomendador + DashboardSpec
{stem}_c3_dashboard_spec.json DashboardSpec AUTOCONTIDO (data_views materializados)
        |  C4  — Renderizacao
{stem}_c4_dashboard.html      versao interativa (ECharts)
{stem}_c4_dashboard.png       screenshot 4K via Playwright
```

**Estrutura de arquivos:**

```
src/phase_c0/   Ingestao + un-pivot
src/phase_c1/   Modelo semantico
src/phase_c2/   Motor de metricas
src/phase_c3/   Recomendador de graficos + DashboardSpec
src/phase_c4/   Renderizacao
tests/test_phase_c0.py ... test_phase_c4.py
libs/trustware/dashboard_contracts.py   contratos Pydantic da Fase C
```

**Dois modos de acionamento** (mesmo padrão de B1/B2/B3):

- Standalone:
  - `python -m phase_c0 <caminho_do_arquivo.xlsx|.csv>` — a C0 é a primeira fase
    e recebe o **arquivo bruto**; ela deriva o `<prefix>` do nome do arquivo.
  - `python -m phase_c1 output/<prefix>` ... até `phase_c4` — as fases seguintes
    recebem o **prefixo** e leem o JSON da fase anterior.
- Orquestrado: `python run_pipeline.py arquivo.xlsx --dashboard` roda C0→C4.
- LLM opcional: `--llm` ativa o enriquecimento narrativo na C3.

---

## 4. Contratos JSON

> Campos de texto exibível (`title`, `label`, `display_value`, `narrative`,
> `evidence`) são UTF-8 e preservam acentuação. Identificadores técnicos
> (`metric`, `id`, chaves de `data_views`) permanecem ASCII.

### 4.1 C0 — `{stem}_c0_dataset.json`

```json
{
  "schema_version": "c0_dataset.v1",
  "source_file": "Propostas.xlsx",
  "ingestion_strategy": {
    "primary": "structured_model",
    "fallback": "grid_scraping",
    "used": "grid_scraping",
    "reason": "pivot-like hierarchical table detected"
  },
  "detected_structure": {
    "table_kind": "pivot_hierarchical",
    "hierarchy": {"parent": "cnpj", "child": "perfil_operacional"},
    "unpivot_source_columns": ["aprovado", "reprovado", "analise", "pendente"],
    "canonical_dimension_from_columns": "status",
    "canonical_measure": "quantidade",
    "subtotal_rows_detected": 12,
    "grand_total_row": 145
  },
  "dataset": [
    {"row_id": 1, "cnpj": "00.656.565/0001-21",
     "perfil_operacional": "Atendente da Loja",
     "status": "Aprovado", "quantidade": 126}
  ],
  "source_map": [
    {"row_id": 1, "origin_sheet": "Plan1",
     "origin_cells": {"cnpj": "A5", "perfil_operacional": "A7",
                      "status": "F4", "quantidade": "F7"}}
  ],
  "discarded_rows": [
    {"origin_row": 145, "reason": "grand_total", "raw": ["Total Geral", 3704]}
  ],
  "validation_summary": {
    "total_rows_read": 200,
    "source_rows_emitted": 120,
    "source_rows_context": 25,
    "source_rows_discarded": 55,
    "dataset_rows_emitted": 580,
    "warnings": []
  }
}
```

A origem de `status` no `source_map` é tipicamente a célula de cabeçalho da coluna
antes do un-pivot.

**Regra de fechamento:** `source_rows_emitted + source_rows_context + source_rows_discarded == total_rows_read`.
Linhas de contexto (linha do CNPJ pai, cabeçalho, linha de agrupamento) são
consumidas mas não viram dataset diretamente. O número de linhas emitidas no
dataset longo (`dataset_rows_emitted`) é independente — o un-pivot transforma
1 linha de origem em N linhas de dataset.

### 4.2 C1 — `{stem}_c1_semantic.json`

```json
{
  "schema_version": "c1_semantic.v1",
  "primary_dimension": "cnpj",
  "secondary_dimension": "perfil_operacional",
  "fields": [
    {"name": "cnpj", "type": "string", "semantic_role": "entity_id",
     "business_role": "merchant_document", "cardinality": 47},
    {"name": "perfil_operacional", "type": "category",
     "semantic_role": "breakdown_dimension", "business_role": null, "cardinality": 5},
    {"name": "status", "type": "category", "semantic_role": "breakdown_dimension",
     "business_role": "proposal_status", "cardinality": 6},
    {"name": "quantidade", "type": "integer", "semantic_role": "measure",
     "business_role": "record_count", "cardinality": null}
  ]
}
```

`semantic_role` ∈ {`entity_id`, `breakdown_dimension`, `measure`, `temporal`, `label`}.

### 4.3 C2 — `{stem}_c2_metrics.json`

```json
{
  "schema_version": "c2_metrics.v1",
  "kpis": [
    {"metric": "approval_rate", "label": "Taxa de Aprovação", "value": 0.2076,
     "formula": "sum(quantidade where status == 'Aprovado') / sum(quantidade)",
     "numerator": 769, "denominator": 3704, "validation_status": "ok"}
  ],
  "aggregations": [
    {"id": "status_distribution", "by": "status", "measure": "quantidade",
     "rows": [{"key": "Aprovado", "value": 769}, {"key": "Reprovado", "value": 2497}]},
    {"id": "cnpj_ranking", "by": "cnpj", "measure": "quantidade",
     "rows": [{"key": "00.656.565/0001-21", "value": 448}, {"key": "12.999.038/0001-07", "value": 356}]}
  ],
  "anomalies": [
    {"type": "concentration", "severity": "high", "metric": "rejection_rate",
     "evidence": "67,4% das propostas estão reprovadas"}
  ]
}
```

**Regra de fórmula (corrigida):** todas as fórmulas de KPI operam sobre o modelo
canônico longo — `sum(quantidade where status == X)` — nunca assumem que valores
de status (`aprovado`, `reprovado`) existem como colunas físicas.

`validation_status` ∈ {`ok`, `mismatch`, `undefined`}.

### 4.4 C3 — `{stem}_c3_dashboard_spec.json` (AUTOCONTIDO)

```json
{
  "schema_version": "dashboard_spec.v1",
  "dashboard_id": "cnpj_status_analysis",
  "title": "Análise de Propostas por CNPJ",
  "resolution": {"width": 3840, "height": 2160},
  "theme": "executive_dark",
  "llm_used": false,
  "layout": {
    "kind": "c_level_grid",
    "rows": [["kpi_summary"], ["status_distribution", "cnpj_ranking"]]
  },
  "data_views": {
    "kpis": {
      "kind": "kpi_list",
      "columns": ["metric", "label", "value", "display_value"],
      "rows": [
        {"metric": "approval_rate", "label": "Taxa de Aprovação",
         "value": 0.2076, "display_value": "20,8%"}
      ],
      "source": {"kpi_ids": ["approval_rate"]}
    },
    "status_distribution": {
      "kind": "series",
      "columns": ["key", "value"],
      "rows": [
        {"key": "Aprovado", "value": 769},
        {"key": "Reprovado", "value": 2497}
      ],
      "source": {"aggregation_id": "status_distribution"}
    },
    "cnpj_ranking": {
      "kind": "series",
      "columns": ["key", "value"],
      "rows": [
        {"key": "00.656.565/0001-21", "value": 448},
        {"key": "12.999.038/0001-07", "value": 356}
      ],
      "source": {"aggregation_id": "cnpj_ranking"}
    }
  },
  "components": [
    {"id": "kpi_summary", "type": "kpi_cards",
     "data_binding": "data_views.kpis",
     "analytical_intent": "summary_kpis",
     "generated_by_rule": "rule.summary_kpis.kpi_cards.v1"},
    {"id": "status_distribution", "type": "horizontal_bar",
     "data_binding": "data_views.status_distribution",
     "analytical_intent": "status_distribution",
     "generated_by_rule": "rule.status_distribution.horizontal_bar.v1"},
    {"id": "cnpj_ranking", "type": "bar_ranking",
     "data_binding": "data_views.cnpj_ranking",
     "analytical_intent": "entity_ranking",
     "generated_by_rule": "rule.entity_ranking.bar_ranking.v1"}
  ],
  "narrative": []
}
```

Cada entrada de `data_views` é um objeto tipado (`kind`, `columns`, `rows`,
`source`). A C4 resolve `data_binding` por **lookup local** dentro de `data_views`
— nunca abre outro arquivo. **Todo `id` referenciado em `layout` tem componente e
`data_view` correspondentes** (validação obrigatória da C3).

---

## 5. Contratos Pydantic

Arquivo novo: `libs/trustware/dashboard_contracts.py` (separado do
`pipeline_contracts.py`, que já carrega os contratos A/B). Mesma governança
trustware. Todos os modelos raiz têm `schema_version` como `Literal[...]`.

```
C0  C0Dataset, IngestionStrategy, DetectedStructure,
    SourceMapEntry, DiscardedRow, ValidationSummary
C1  SemanticModel, SemanticField
C2  MetricsReport, KPI, Aggregation, AggregationRow, Anomaly
C3  DashboardSpec, DataViews, DataView, DashboardComponent, Layout,
    Resolution, NarrativeBlock, ChartRule, DashboardComponentSpec
```

`DataView` é o objeto tipado de cada entrada de `data_views` (`kind`, `columns`,
`rows`, `source`).

`DashboardComponentSpec` = par `(component, required_data_view)` emitido por uma
`ChartRule`; é o tipo intermediário entre o catálogo e o `DashboardSpec` final.

---

## 6. Catálogo ChartRule

O catálogo é **dado versionado**, não código espalhado: uma lista de `ChartRule`.

```python
ChartRule(
    id="rule.status_distribution.horizontal_bar.v1",
    priority=20,
    analytical_intent="status_distribution",
    predicate_id="predicate.has_status_breakdown_and_measure.v1",
    component_type="horizontal_bar",
    data_view_builder_id="builder.status_distribution.v1",
)
```

O `ChartRule` carrega apenas **IDs estáveis** — `predicate_id` e
`data_view_builder_id` — nunca funções Python diretas. Isso mantém o catálogo como
dado versionado e auditável. As funções são resolvidas por registries:

```python
PREDICATE_REGISTRY = {
    "predicate.has_status_breakdown_and_measure.v1": has_status_breakdown_and_measure,
}
DATA_VIEW_BUILDER_REGISTRY = {
    "builder.status_distribution.v1": build_status_distribution,
}
```

A função de recomendação é pura:

```
recommend(semantic, metrics) -> list[DashboardComponentSpec]
```

Cada `ChartRule` emite **gráfico + contrato de `data_view`** — não apenas o gráfico.
A C3 materializa esses `data_views` dentro do `DashboardSpec` autocontido.

**Tabela de regras (MVP):**

| id (estável) | intent | Condição | Componente |
|---|---|---|---|
| `rule.summary_kpis.kpi_cards.v1` | `summary_kpis` | Há `kpis` no C2 | `kpi_cards` |
| `rule.status_distribution.horizontal_bar.v1` | `status_distribution` | `breakdown_dimension` tipo status + measure | `horizontal_bar` |
| `rule.entity_ranking.bar_ranking.v1` | `entity_ranking` | `entity_id` + measure | `bar_ranking` (Top N) |
| `rule.cross_breakdown.heatmap.v1` | `cross_breakdown` | 2 `breakdown_dimension` + measure | `heatmap` |
| `rule.temporal_trend.line.v1` | `temporal_trend` | `temporal` + measure | `line` |
| `rule.category_composition.stacked_bar.v1` | `category_composition` | `breakdown_dimension` ≤7 cat. + measure | `stacked_bar` |

**Controle de duplicidade:** cada `analytical_intent` gera **no máximo um componente
primário**. Se duas regras disputam o mesmo intent, vence a de maior `priority`.
**Prioridade é numérica descendente: quanto maior o número, maior a precedência**
(ex.: 100 vence 20). Intents válidos: `summary_kpis`, `status_distribution`,
`entity_ranking`, `cross_breakdown`, `temporal_trend`, `category_composition`.

**Auditabilidade:** todo componente registra `generated_by_rule` com o `id` da
regra que o criou.

---

## 7. Papel da LLM

A LLM é **opcional, exclusiva da C3, atrás da flag `--llm`**. A C1 é 100%
determinística — a LLM não a toca.

| Tarefa | LLM pode? | Onde |
|---|---|---|
| Calcular qualquer número | Nunca | — |
| Inferir `semantic_role` / `business_role` | Nunca | C1 determinística |
| Alterar `data_views` | Nunca | — |
| Criar layout novo / alterar grid / resolução | Nunca | — |
| Alterar componentes obrigatórios | Nunca | — |
| Título executivo do dashboard | Sim | C3 |
| Títulos dos componentes | Sim | C3 |
| Narrativa executiva (com evidência numérica do C2) | Sim | C3 |
| **Sugerir** layout entre templates aprovados | Sim (sugestão) | C3 |

**Layout:** a LLM apenas sugere — `{"suggested_layout": "...", "reason": "..."}`.
A escolha final passa por validador determinístico da C3, que aceita ou ignora.
A LLM nunca cria layout novo.

**Garantia de determinismo:** sem `--llm`, o pipeline entrega o dashboard completo,
com títulos genéricos e `narrative: []`. Com `--llm`, ganha narrativa e títulos
redigidos. O `DashboardSpec` registra `llm_used: true/false` como proveniência.

---

## 8. Renderização 4K (C4)

- Entrada única: `{stem}_c3_dashboard_spec.json`.
- C4 valida o `DashboardSpec` contra o schema Pydantic antes de renderizar.
- Gera HTML com ECharts a partir do spec; cada `component.id` vira um container.
- Abre o HTML em Chromium headless via Playwright, viewport **3840×2160**.
- Tira screenshot PNG.
- Saídas: `{stem}_c4_dashboard.html` + `{stem}_c4_dashboard.png`.
- C4 não calcula, não interpreta, não altera o spec, não decide gráfico.

**Dependência nova:** `playwright` é a **única** dependência nova do pipeline
inteiro. C0→C3 rodam com openpyxl + pydantic (já presentes). Setup local:
`pip install -r requirements.txt` + um único `playwright install chromium`.

---

## 9. Testes TDD mínimos

**C0:** CSV simples → strategy `structured_model`; tabela dinâmica hierárquica →
un-pivot correto + hierarquia detectada; subtotal → `discarded_rows`; total geral →
descartado; linha de CNPJ pai / cabeçalho → contabilizada como `context`;
`source_map` cobre 100% dos campos de cada linha do dataset; arquivo inexistente →
erro limpo; `source_rows_emitted + source_rows_context + source_rows_discarded == total_rows_read`.

**C1:** coluna numérica → measure; coluna CNPJ → entity_id; categórica baixa
cardinalidade → breakdown_dimension; coluna de data → temporal; todo campo recebe
`semantic_role`; sem measure → warning explícito.

**C2:** `approval_rate` correto sobre modelo longo; soma das partes ≠ total →
`mismatch`; aggregation por status correta; anomalia de concentração acima do
limiar; divisão por zero → `undefined`, sem crash.

**C3:** status + entidade → catálogo escolhe horizontal_bar + ranking + heatmap;
todo componente tem `data_binding` resolvível dentro de `data_views`; todo `id` do
`layout` tem componente + `data_view` correspondentes; spec valida contra schema
Pydantic; `schema_version == "dashboard_spec.v1"`; sem `--llm` → `narrative` vazio
mas spec válido; cada `analytical_intent` gera ≤1 componente; todo componente tem
`generated_by_rule`; `ChartRule` resolve `predicate_id`/`data_view_builder_id` via
registry.

**C4:** spec mínimo → HTML existe; HTML contém um container por `component.id`;
PNG criado com dimensões exatas 3840×2160; spec inválido → erro antes de renderizar.
Playwright é mockado nos testes unitários; o teste de integração real com Chromium
fica separado e marcado.

---

## 10. Critérios de aceite finais

1. `python run_pipeline.py arquivo.xlsx --dashboard` produz os 5 artefatos C0→C4.
2. O `DashboardSpec` é autocontido — a C4 roda sem acesso a nenhum outro arquivo.
3. Todo número exibido tem rastro: fórmula, numerador, denominador, validação.
4. Toda linha de origem é contabilizada (emitida, contexto, ou descartada com motivo).
5. Sem `--llm`, o pipeline entrega dashboard completo (sem narrativa).
6. O PNG final tem exatamente 3840×2160.
7. Toda a suíte de testes passa, incluindo os testes novos C0→C4.
8. CI verde no GitHub Actions.

---

## 11. Fora de escopo (MVP)

- Stack web (FastAPI, React, Redis, Celery, PostgreSQL) — é MVP4 ("dashboard vivo").
- Banco de dados, histórico de uploads, comparação entre períodos, agendamento.
- Temas personalizados por cliente / branding (logo, cores) — MVP2.
- Inputs além de `.xlsx` e `.csv` (JSON, dados colados, API, SQL) — fase futura.
- Snapshot visual pixel-a-pixel — só se necessário no futuro.
- Exportação PPTX / PDF — fase futura (o MVP entrega HTML + PNG).

---

## 12. Riscos e decisões futuras

| Risco / Decisão | Mitigação / Encaminhamento |
|---|---|
| Un-pivot heurístico falha em layout dinâmico atípico | `ingestion_strategy` registra o modo usado; `discarded_rows` audita; testes cobrem variações |
| Extração de pivot cache / data model varia por versão do Excel | Modo híbrido: tenta estruturado, cai pro scraping; sempre registra `used` |
| Volume de dados acima do esperado | C2 em Python puro até **100.000 linhas normalizadas**; acima disso, emite warning de escala e abre caminho para backend analítico alternativo futuro |
| Variância de renderização do browser quebra teste | Testes validam o `DashboardSpec`, não pixels; C4 só testa existência/resolução/integridade |
| `playwright` adiciona peso de instalação | Isolado na C4; C0→C3 permanecem leves; setup é um único comando |
| Integração futura com a fábrica / Ozzomosis | Fora do escopo deste MVP; o pipeline determinístico e o `DashboardSpec` versionado já são a base contratual para essa integração |

---

## Trava final

```
DashboardSpec autocontido é o artefato canônico.
C4 toca apenas o DashboardSpec.
C4 não abre C2, não resolve regra, não calcula e não interpreta.
```

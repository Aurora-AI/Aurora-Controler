# Insight Board — Seções de Drill-Down Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levar o `aurora-frontend` (Next.js) ao nível de detalhamento do relatório-padrão EXRS v4 — componentizar o padrão de drill-down N0→N1→N2 já provado em `InsightBoard.tsx` e cobrir as seções que hoje o backend já entrega prontas (ranking de lojas, loja a loja, achados por tema, qualidade de dados, anexo de metodologia, e agora também sumário executivo + plano de ação, desbloqueados pelo `executive_summary` real do backend).

**Architecture:** Um primitivo `ExpandableCard` genérico (N0→N1→N2) reaproveitado por componentes de seção, cada um em seu próprio arquivo. Toda leitura/reshape do `ExecutiveAuditReport` fica isolada em `src/lib/selectors.ts` — só `.filter/.sort/.map/.find`, nenhuma soma/percentual/média. Todo número renderizado vem pronto de um campo do relatório; nenhum cálculo de negócio acontece no frontend.

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, CSS vanilla (`globals.css`, tokens `--accent`/`--accent-red`/`--border-subtle` etc). Sem test runner configurado no projeto — verificação é type-check (`npx tsc --noEmit`) + inspeção visual via `npm run dev`.

## Global Constraints

- **Frontend nunca calcula.** Todo valor exibido vem direto de um campo do `ExecutiveAuditReport` (`src/types/audit.ts`). Nenhuma soma, percentual, média ou razão é computada em nenhum componente ou em `selectors.ts` — só remodelagem estrutural (`.filter/.sort/.map/.find`, contagem via `.length`).
- `src/lib/selectors.ts` é o único arquivo que lê o `ExecutiveAuditReport` bruto — componentes de seção só chamam funções desse arquivo, nunca acessam campos do relatório diretamente com lógica condicional complexa embutida no JSX.
- Padrão de card: N0 (fechado — número + 1 frase) → N1 "O Mecanismo" (explicação causal, texto fixo condicionado a flags reais, ex.: `masks_negative_product_margin`) → N2 "Evidência" (dado bruto do relatório). Este padrão já existe hoje em `InsightBoard.tsx` nos cards "Prejuízo Mascarado" e "Lojas no Vermelho" — o `ExpandableCard` generaliza exatamente esse HTML/CSS, não inventa um novo.
- Paleta/tokens: usar só as classes/variáveis já existentes em `globals.css` (`.aurora-card`, `.number-highlight`, `.text-accent`, `--accent-red`, etc.) — não introduzir cores/tokens novos.
- Dados insuficientes/cenário nunca viram fato: `has_sufficient_history=false`, `insufficient_data=true`, `gmroi=null`/`is_directional_only=true`, e qualquer coisa vinda de `latent_revenue` precisam de rótulo visual explícito ("dado insuficiente"/"cenário assumido"), nunca tratados como iguais ao resto.
- Sem test runner — cada task termina com `npx tsc --noEmit` limpo (0 erros) como gate mínimo; tasks que mudam o que é renderizado também pedem inspeção visual via `npm run dev` antes do commit.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/lib/selectors.ts` (novo) | Toda remodelagem de dados do `ExecutiveAuditReport` — zero aritmética |
| `src/components/ExpandableCard.tsx` (novo) | Primitivo genérico N0→N1→N2 |
| `src/components/sections/SumarioExecutivo.tsx` (novo) | Seção 01 — KPIs de rede + cards existentes migrados pro primitivo |
| `src/components/sections/PlanoDeAcao.tsx` (novo) | Seção 07 — `executive_summary.action_plan`, renderizado na ordem que vier |
| `src/components/sections/RankingDeLojas.tsx` (novo) | Seção 02 — `store_macro_summary` + `store_performance` |
| `src/components/sections/LojaALoja.tsx` (novo) | Seção 03 — `service_decomposition`, todas as lojas |
| `src/components/sections/AchadosPorTema.tsx` (novo) | Seção 04 — Serviço/Estoque/Margem/Cliente/Vendedor |
| `src/components/sections/QualidadeDados.tsx` (novo) | Seção 06 — `cleaning` + `data_completeness` |
| `src/components/sections/AnexoMetodologia.tsx` (novo) | Seção 08 — `thresholds` |
| `src/components/InsightBoard.tsx` (modificado) | Vira orquestrador — importa e compõe as seções, mantém só o estado `expandedId` |
| `src/types/audit.ts` | Já atualizado (sessão anterior) — não precisa mudar nesta rodada |
| `src/data/mock_audit_report.json` | Já atualizado com dado real (sessão anterior) — não precisa mudar nesta rodada |

---

### Task 1: `ExpandableCard` — primitivo genérico N0→N1→N2

**Files:**
- Create: `src/components/ExpandableCard.tsx`

**Interfaces:**
- Produces: `ExpandableCard(props: ExpandableCardProps)` — componente React exportado default. Props: `id: string`, `expandedId: string | null`, `onToggle: (id: string) => void`, `title: string`, `highlight: React.ReactNode`, `highlightClassName?: string`, `summary: React.ReactNode`, `mechanism: React.ReactNode`, `evidence: React.ReactNode`, `footnote?: React.ReactNode`.

- [ ] **Step 1: Criar o componente**

```tsx
// src/components/ExpandableCard.tsx
"use client";

import React from 'react';

export interface ExpandableCardProps {
  id: string;
  expandedId: string | null;
  onToggle: (id: string) => void;
  title: string;
  highlight: React.ReactNode;
  highlightClassName?: string;
  summary: React.ReactNode;
  mechanism: React.ReactNode;
  evidence: React.ReactNode;
  footnote?: React.ReactNode;
}

export default function ExpandableCard({
  id,
  expandedId,
  onToggle,
  title,
  highlight,
  highlightClassName,
  summary,
  mechanism,
  evidence,
  footnote,
}: ExpandableCardProps) {
  const isExpanded = expandedId === id;

  return (
    <div
      className={`aurora-card clickable ${isExpanded ? 'expanded' : ''}`}
      onClick={() => onToggle(id)}
      style={{ cursor: 'pointer', border: isExpanded ? '2px solid var(--accent)' : '' }}
    >
      <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>{title}</h3>
      <div className={`number-highlight ${highlightClassName ?? ''}`}>{highlight}</div>
      <p className="text-sm" style={{ marginTop: '0.5rem' }}>{summary}</p>

      {isExpanded && (
        <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-subtle)' }}>
          <h4 className="text-md font-semibold text-accent">O Mecanismo (N1)</h4>
          <div style={{ marginTop: '0.5rem' }}>{mechanism}</div>

          <h4 className="text-md font-semibold text-accent" style={{ marginTop: '1.5rem' }}>Evidência (N2)</h4>
          <div style={{ marginTop: '0.5rem' }}>{evidence}</div>

          {footnote && (
            <p className="text-xs text-muted" style={{ marginTop: '1rem', fontStyle: 'italic' }}>{footnote}</p>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 3: Commit**

```bash
git add src/components/ExpandableCard.tsx
git commit -m "feat(insight-board): extrai ExpandableCard como primitivo N0/N1/N2 reutilizável"
```

---

### Task 2: `selectors.ts` — remodelagem central, zero aritmética

**Files:**
- Create: `src/lib/selectors.ts`

**Interfaces:**
- Consumes: `ExecutiveAuditReport` e os tipos de `@/types/audit` (já existentes).
- Produces: `rankedStores`, `sortedServiceDecomposition`, `storesWithMaskedProductLoss`, `decoupledProductTrends`, `sortedContributionMarginAlerts`, `sortedDeadStockSkus`, `sortedGmroi`, `sortedCustomerConcentration`, `sortedRfmChampions`, `sortedChurnFindings`, `sortedSalespersonPerformance`, `orderedActionPlan`, `discardedAlarmsByCategory` — todas exportadas, usadas pelas tasks seguintes.

- [ ] **Step 1: Criar o arquivo**

```ts
// src/lib/selectors.ts
//
// Único arquivo que lê o ExecutiveAuditReport bruto. Toda função aqui é
// .filter/.sort/.map/.find — REMODELAGEM ESTRUTURAL, nunca soma/percentual/média.
// Todo número exibido na UI vem pronto de um campo do relatório; se um componente
// precisar de um número que não existe como campo, o card correspondente fica de
// fora até o backend calcular (nunca inventar aqui).
import {
  ExecutiveAuditReport,
  StorePerformance,
  ServiceDecomposition,
  ProductTrendEntry,
  DiscardedAlarm,
  ActionPlanItem,
} from '@/types/audit';

export interface RankedStore {
  store: string;
  revenuePosition: number;
  marginPosition: number;
  performance: StorePerformance | undefined;
}

/** Seção 02 — ranking de lojas por faturamento vs. margem real, lado a lado. */
export function rankedStores(report: ExecutiveAuditReport): RankedStore[] {
  const macro = report.store_macro_summary;
  if (!macro) return [];
  return macro.revenue_rank.map((store, idx) => ({
    store,
    revenuePosition: idx + 1,
    marginPosition: macro.margin_rank.indexOf(store) + 1,
    performance: report.store_performance.find((s) => s.store === store),
  }));
}

/** Seção 03 — todas as lojas com decomposição produto x serviço, ordenadas pela
 * mais mascarada primeiro (produto mais negativo). Comparador de ordenação, não
 * cálculo de negócio (mesmo padrão de `sorted(key=...)` usado no backend). */
export function sortedServiceDecomposition(report: ExecutiveAuditReport): ServiceDecomposition[] {
  return [...report.service_decomposition].sort((a, b) => a.product_margin - b.product_margin);
}

export function storesWithMaskedProductLoss(report: ExecutiveAuditReport): ServiceDecomposition[] {
  return report.service_decomposition.filter((s) => s.masks_negative_product_margin);
}

/** Seção 04, tema Margem de Produto — produtos descolados da curva da empresa. */
export function decoupledProductTrends(report: ExecutiveAuditReport): ProductTrendEntry[] {
  return report.product_trends.filter((p) => p.decoupled);
}

export function sortedContributionMarginAlerts(report: ExecutiveAuditReport) {
  return [...report.contribution_margin_alerts].sort((a, b) => a.contribution_margin - b.contribution_margin);
}

/** Seção 04, tema Estoque. */
export function sortedDeadStockSkus(report: ExecutiveAuditReport) {
  return [...report.dead_stock].sort((a, b) => b.capital_frozen - a.capital_frozen);
}

export function sortedGmroi(report: ExecutiveAuditReport) {
  return [...report.gmroi].sort((a, b) => (a.gmroi ?? 0) - (b.gmroi ?? 0));
}

/** Seção 04, tema Cliente. */
export function sortedCustomerConcentration(report: ExecutiveAuditReport) {
  return [...report.customer_concentration].sort((a, b) => b.concentration_pct - a.concentration_pct);
}

export function sortedRfmChampions(report: ExecutiveAuditReport) {
  return [...report.rfm_champions].sort((a, b) => b.monetary - a.monetary);
}

export function sortedChurnFindings(report: ExecutiveAuditReport) {
  return [...report.churn_findings].sort((a, b) => b.historical_annual_value - a.historical_annual_value);
}

/** Seção 04, tema Vendedor. */
export function sortedSalespersonPerformance(report: ExecutiveAuditReport) {
  return [...report.salesperson_performance].sort((a, b) => b.total_revenue - a.total_revenue);
}

/** Seção 07 — plano de ação: o backend já entrega pré-ordenado (tier asc, R$ desc
 * dentro do tier) — esta função NÃO reordena, só existe pra manter o padrão de
 * "toda leitura passa por selectors.ts" sem tocar na ordem que veio pronta. */
export function orderedActionPlan(report: ExecutiveAuditReport): ActionPlanItem[] {
  return report.executive_summary.action_plan;
}

export function discardedAlarmsByCategory(
  report: ExecutiveAuditReport,
  category: DiscardedAlarm['category'],
): DiscardedAlarm[] {
  return report.executive_summary.discarded_alarms.filter((a) => a.category === category);
}
```

- [ ] **Step 2: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 3: Commit**

```bash
git add src/lib/selectors.ts
git commit -m "feat(insight-board): adiciona selectors.ts central (remodelagem, zero aritmética)"
```

---

### Task 3: Seção 01 + 07 — Sumário Executivo e Plano de Ação (desbloqueadas pelo `executive_summary` real)

**Files:**
- Create: `src/components/sections/SumarioExecutivo.tsx`
- Create: `src/components/sections/PlanoDeAcao.tsx`

**Interfaces:**
- Consumes: `ExpandableCard` (Task 1), `orderedActionPlan`, `discardedAlarmsByCategory` (Task 2), `ExecutiveAuditReport` de `@/types/audit`.
- Produces: `SumarioExecutivo({report, expandedId, onToggle}: SectionProps)`, `PlanoDeAcao({report}: {report: ExecutiveAuditReport})` — exportados default.

- [ ] **Step 1: Criar `SumarioExecutivo.tsx`**

```tsx
// src/components/sections/SumarioExecutivo.tsx
"use client";

import React from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import ExpandableCard from '@/components/ExpandableCard';
import {
  discardedAlarmsByCategory,
  sortedContributionMarginAlerts,
  sortedDeadStockSkus,
  sortedChurnFindings,
} from '@/lib/selectors';

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);

interface SectionProps {
  report: ExecutiveAuditReport;
  expandedId: string | null;
  onToggle: (id: string) => void;
}

export default function SumarioExecutivo({ report, expandedId, onToggle }: SectionProps) {
  const { executive_summary: summary } = report;
  const rampAlarms = discardedAlarmsByCategory(report, 'salesperson_ramp');
  const coldStartAlarms = discardedAlarmsByCategory(report, 'store_cold_start');

  return (
    <section>
      <h2 className="text-2xl" style={{ marginBottom: '2rem' }}>Sumário Executivo</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>

        {summary.total_operational_loss > 0 && (
          <ExpandableCard
            id="sumario-operational-loss"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Sangria Operacional"
            highlight={formatCurrency(summary.total_operational_loss)}
            highlightClassName="negative"
            summary="SKUs vendendo abaixo da margem de contribuição — pode incluir promoção intencional, a confirmar."
            mechanism={
              <p className="text-sm">
                Cada venda desses produtos dá prejuízo antes mesmo de despesa fixa. O valor soma a margem
                negativa de todos os SKUs no vermelho da rede — ainda não distingue erro de precificação de
                promoção deliberada.
              </p>
            }
            evidence={
              <div>
                {sortedContributionMarginAlerts(report).map((a) => (
                  <div key={a.product} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{a.product}</span>
                    <span className="text-xs text-accent-red">{formatCurrency(a.contribution_margin)}</span>
                  </div>
                ))}
              </div>
            }
            footnote="A confirmar: distinguir promoção legítima de erro de precificação é decisão do dono da rede, não do motor."
          />
        )}

        {summary.total_capital_frozen > 0 && (
          <ExpandableCard
            id="sumario-capital-frozen"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Dinheiro Parado"
            highlight={formatCurrency(summary.total_capital_frozen)}
            summary={`Capital travado em estoque que não gira há mais de ${report.thresholds.dead_stock_months} meses.`}
            mechanism={
              <p className="text-sm">
                Esse capital está imobilizado em prateleira, sem girar — é dinheiro parado, não perdido: uma
                liquidação ou transferência entre lojas recupera o valor.
              </p>
            }
            evidence={
              <div>
                {sortedDeadStockSkus(report).map((d) => (
                  <div key={d.dead_stock_months} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{d.sku_count} SKUs parados</span>
                    <span className="text-xs">{d.dead_stock_pct.toFixed(1)}% do estoque total</span>
                  </div>
                ))}
              </div>
            }
          />
        )}

        {summary.total_ltv_risk > 0 && (
          <ExpandableCard
            id="sumario-ltv-risk"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Evasão Silenciosa"
            highlight={formatCurrency(summary.total_ltv_risk)}
            highlightClassName="negative"
            summary="Valor histórico anual de clientes recorrentes que sumiram sem cancelamento formal."
            mechanism={
              <p className="text-sm">
                Cada cliente aqui comprava com regularidade e parou além do padrão de cadência dele — não é
                perda confirmada, é risco: LTV projetado que precisa de ativação via CRM para não virar perda de
                fato.
              </p>
            }
            evidence={
              <div>
                {sortedChurnFindings(report).slice(0, 10).map((c) => (
                  <div key={c.customer_id} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{c.customer_id}</span>
                    <span className="text-xs">{c.months_silent} meses em silêncio</span>
                  </div>
                ))}
              </div>
            }
            footnote={report.churn_findings.length > 10 ? `+ ${report.churn_findings.length - 10} outros clientes.` : undefined}
          />
        )}

        {(rampAlarms.length > 0 || coldStartAlarms.length > 0) && (
          <ExpandableCard
            id="sumario-nao-e-problema"
            expandedId={expandedId}
            onToggle={onToggle}
            title="O Que NÃO É Problema"
            highlight={`${summary.discarded_alarms.length} Alarmes Descartados`}
            highlightClassName=""
            summary="Vendedores em rampa e lojas cold-start que o motor avaliou e decidiu não penalizar."
            mechanism={
              <p className="text-sm">
                O motor checa maturidade antes de julgar performance — vendedor novo ou loja recém-aberta não
                têm base estatística suficiente para serem comparados com o resto da rede.
              </p>
            }
            evidence={
              <div>
                {summary.discarded_alarms.map((a) => (
                  <div key={`${a.category}-${a.entity_id}`} style={{ padding: '0.5rem 0', borderBottom: '1px solid var(--border-subtle)' }}>
                    <span className="text-sm font-semibold">{a.entity_id}</span>
                    <p className="text-xs text-muted">{a.reason}</p>
                  </div>
                ))}
              </div>
            }
          />
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Criar `PlanoDeAcao.tsx`**

```tsx
// src/components/sections/PlanoDeAcao.tsx
"use client";

import React from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import { orderedActionPlan } from '@/lib/selectors';

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);

export default function PlanoDeAcao({ report }: { report: ExecutiveAuditReport }) {
  const actionPlan = orderedActionPlan(report);
  if (actionPlan.length === 0) return null;

  return (
    <section style={{ padding: '2rem', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
      <h2 className="text-2xl" style={{ marginBottom: '1rem' }}>Plano de Ação</h2>
      <p className="text-sm text-muted" style={{ marginBottom: '1.5rem' }}>
        Ordenado pelo motor por certeza e urgência — sangria operacional certa primeiro, depois capital
        recuperável, depois risco de LTV projetado.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {actionPlan.map((action, idx) => (
          <div key={action.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '1rem', border: '1px solid var(--border-subtle)', borderRadius: '4px', background: 'var(--bg-primary)' }}>
            <div>
              <h4 className="font-semibold">{idx + 1}. {action.title}</h4>
              <p className="text-sm text-muted">{action.description}</p>
            </div>
            <div className="font-mono text-lg" style={{ color: action.nature === 'capital' ? 'var(--fg)' : 'var(--accent-red)' }}>
              {formatCurrency(action.impact_brl)}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 4: Commit**

```bash
git add src/components/sections/SumarioExecutivo.tsx src/components/sections/PlanoDeAcao.tsx
git commit -m "feat(insight-board): seções 01+07 — sumário executivo e plano de ação com dado real"
```

---

### Task 4: Seção 02 — Ranking de Lojas

**Files:**
- Create: `src/components/sections/RankingDeLojas.tsx`

**Interfaces:**
- Consumes: `rankedStores` (Task 2), `ExpandableCard` (Task 1).
- Produces: `RankingDeLojas({report, expandedId, onToggle}: SectionProps)`.

- [ ] **Step 1: Criar o componente**

```tsx
// src/components/sections/RankingDeLojas.tsx
"use client";

import React from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import ExpandableCard from '@/components/ExpandableCard';
import { rankedStores } from '@/lib/selectors';

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);

interface SectionProps {
  report: ExecutiveAuditReport;
  expandedId: string | null;
  onToggle: (id: string) => void;
}

export default function RankingDeLojas({ report, expandedId, onToggle }: SectionProps) {
  const macro = report.store_macro_summary;
  if (!macro) return null;
  const stores = rankedStores(report);

  return (
    <section>
      <h2 className="text-2xl" style={{ marginBottom: '2rem' }}>A Rede em Foco</h2>
      <ExpandableCard
        id="ranking-lojas"
        expandedId={expandedId}
        onToggle={onToggle}
        title="Ranking: faturamento vs. margem real"
        highlight={macro.rank_differs ? 'Rankings divergem' : 'Rankings coincidem'}
        summary={`${formatCurrency(macro.masked_amount)} mascarados pelo agregado saudável da rede.`}
        mechanism={
          <p className="text-sm">
            Loja de faturamento alto pode ter margem de contribuição real negativa — o agregado da rede fecha
            positivo só porque o resultado das lojas saudáveis absorve o prejuízo das lojas negativas.
          </p>
        }
        evidence={
          <div>
            {stores.map((s) => (
              <div key={s.store} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                <span className="text-sm font-semibold">{s.store}</span>
                <div style={{ display: 'flex', gap: '1rem', textAlign: 'right' }}>
                  <span className="text-xs text-muted">Faturamento: #{s.revenuePosition}</span>
                  <span className={`text-xs ${s.performance && s.performance.contribution_margin_total < 0 ? 'text-accent-red' : 'text-muted'}`}>
                    Margem: #{s.marginPosition}
                    {s.performance && !s.performance.has_sufficient_history ? ' (dado insuficiente)' : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        }
      />
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 3: Commit**

```bash
git add src/components/sections/RankingDeLojas.tsx
git commit -m "feat(insight-board): seção 02 — ranking de lojas por faturamento vs. margem real"
```

---

### Task 5: Seção 03 — Loja a Loja (substitui o card "Prejuízo Mascarado" atual)

**Files:**
- Create: `src/components/sections/LojaALoja.tsx`

**Interfaces:**
- Consumes: `sortedServiceDecomposition`, `storesWithMaskedProductLoss` (Task 2), `ExpandableCard` (Task 1).
- Produces: `LojaALoja({report, expandedId, onToggle}: SectionProps)`.

- [ ] **Step 1: Criar o componente**

```tsx
// src/components/sections/LojaALoja.tsx
"use client";

import React from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import ExpandableCard from '@/components/ExpandableCard';
import { sortedServiceDecomposition, storesWithMaskedProductLoss } from '@/lib/selectors';

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);

interface SectionProps {
  report: ExecutiveAuditReport;
  expandedId: string | null;
  onToggle: (id: string) => void;
}

export default function LojaALoja({ report, expandedId, onToggle }: SectionProps) {
  const decompositions = sortedServiceDecomposition(report);
  if (decompositions.length === 0) return null;
  const masked = storesWithMaskedProductLoss(report);

  return (
    <section>
      <h2 className="text-2xl" style={{ marginBottom: '2rem' }}>Loja a Loja: Produto vs. Serviço</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
        {decompositions.map((d) => (
          <ExpandableCard
            key={d.store}
            id={`loja-a-loja-${d.store}`}
            expandedId={expandedId}
            onToggle={onToggle}
            title={d.store}
            highlight={formatCurrency(d.total_margin)}
            highlightClassName={d.total_margin < 0 ? 'negative' : ''}
            summary={
              d.masks_negative_product_margin
                ? 'O produto vende no prejuízo, mas o total da loja aparece positivo por causa dos serviços.'
                : 'Produto e serviço decompostos.'
            }
            mechanism={
              <p className="text-sm">
                {d.masks_negative_product_margin
                  ? 'A margem de serviços está cobrindo a margem negativa dos produtos físicos vendidos — o resultado consolidado engana o DRE da loja.'
                  : 'Margem de produto e margem de serviço somam o resultado total da loja sem mascaramento.'}
              </p>
            }
            evidence={
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                  <span className="text-sm">Margem de produto</span>
                  <span className={`text-sm ${d.product_margin < 0 ? 'text-accent-red' : ''}`}>{formatCurrency(d.product_margin)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}>
                  <span className="text-sm">Margem de serviço</span>
                  <span className="text-sm">{formatCurrency(d.service_margin)}</span>
                </div>
                {d.follow_on_cac_effect > 0 && (
                  <p className="text-xs text-muted" style={{ marginTop: '0.5rem' }}>
                    {formatCurrency(d.follow_on_cac_effect)} em receita de produto vieram de clientes que entraram
                    primeiro via serviço.
                  </p>
                )}
              </div>
            }
          />
        ))}
      </div>
      {masked.length === 0 && (
        <p className="text-sm text-muted" style={{ marginTop: '1rem' }}>Nenhuma loja mascara prejuízo de produto com serviço nesta rodada.</p>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 3: Commit**

```bash
git add src/components/sections/LojaALoja.tsx
git commit -m "feat(insight-board): seção 03 — loja a loja, decomposição produto vs. serviço"
```

---

### Task 6: Seção 04 — Achados por Tema (Serviço, Estoque, Margem de Produto, Cliente, Vendedor)

**Files:**
- Create: `src/components/sections/AchadosPorTema.tsx`

**Interfaces:**
- Consumes: `decoupledProductTrends`, `sortedContributionMarginAlerts`, `sortedDeadStockSkus`, `sortedGmroi`, `sortedCustomerConcentration`, `sortedRfmChampions`, `sortedChurnFindings`, `sortedSalespersonPerformance` (Task 2), `ExpandableCard` (Task 1).
- Produces: `AchadosPorTema({report, expandedId, onToggle}: SectionProps)`.

- [ ] **Step 1: Criar o componente**

```tsx
// src/components/sections/AchadosPorTema.tsx
"use client";

import React from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import ExpandableCard from '@/components/ExpandableCard';
import {
  decoupledProductTrends,
  sortedContributionMarginAlerts,
  sortedDeadStockSkus,
  sortedGmroi,
  sortedCustomerConcentration,
  sortedRfmChampions,
  sortedChurnFindings,
  sortedSalespersonPerformance,
} from '@/lib/selectors';

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);

interface SectionProps {
  report: ExecutiveAuditReport;
  expandedId: string | null;
  onToggle: (id: string) => void;
}

export default function AchadosPorTema({ report, expandedId, onToggle }: SectionProps) {
  const marginAlerts = sortedContributionMarginAlerts(report);
  const decoupled = decoupledProductTrends(report);
  const deadStock = sortedDeadStockSkus(report);
  const gmroi = sortedGmroi(report);
  const concentration = sortedCustomerConcentration(report);
  const rfm = sortedRfmChampions(report);
  const churn = sortedChurnFindings(report);
  const salespeople = sortedSalespersonPerformance(report);

  return (
    <section>
      <h2 className="text-2xl" style={{ marginBottom: '2rem' }}>Achados por Tema</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>

        {marginAlerts.length > 0 && (
          <ExpandableCard
            id="tema-margem-produto"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Margem de Produto"
            highlight={`${marginAlerts.length} SKUs no vermelho`}
            highlightClassName="negative"
            summary="Produtos com margem de contribuição negativa — cada venda dá prejuízo."
            mechanism={<p className="text-sm">Preço médio menos custo de entrada menos custo variável fica abaixo de zero para estes SKUs.</p>}
            evidence={
              <div>
                {marginAlerts.map((a) => (
                  <div key={a.product} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{a.product}</span>
                    <span className="text-xs text-accent-red">{formatCurrency(a.contribution_margin)} ({a.sample_size} vendas)</span>
                  </div>
                ))}
              </div>
            }
          />
        )}

        {decoupled.length > 0 && (
          <ExpandableCard
            id="tema-produtos-descolados"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Produtos Descolados"
            highlight={`${decoupled.length} produtos`}
            summary="Crescimento do produto descolou do crescimento da empresa como um todo."
            mechanism={<p className="text-sm">Compara a curva de crescimento (1ª vs. 2ª metade do período) do produto contra a curva da empresa inteira.</p>}
            evidence={
              <div>
                {decoupled.map((p) => (
                  <div key={p.product} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{p.product}</span>
                    <span className="text-xs">Empresa: {p.company_growth_pct.toFixed(1)}% | Produto: {p.product_growth_pct.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            }
          />
        )}

        {deadStock.length > 0 && (
          <ExpandableCard
            id="tema-estoque-morto"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Estoque Morto"
            highlight={formatCurrency(deadStock[0].capital_frozen)}
            summary={`${deadStock[0].sku_count} SKUs sem movimento há ${deadStock[0].dead_stock_months}+ meses.`}
            mechanism={<p className="text-sm">Capital parado em prateleira — {deadStock[0].dead_stock_pct.toFixed(1)}% de todo o estoque válido da rede.</p>}
            evidence={
              <div>
                {deadStock[0].skus.map((sku) => (
                  <span key={sku} className="text-xs" style={{ display: 'inline-block', marginRight: '0.5rem', marginBottom: '0.25rem', padding: '0.25rem 0.5rem', background: 'var(--bg-secondary)', borderRadius: '4px' }}>{sku}</span>
                ))}
              </div>
            }
          />
        )}

        {gmroi.length > 0 && (
          <ExpandableCard
            id="tema-gmroi"
            expandedId={expandedId}
            onToggle={onToggle}
            title="GMROI por Categoria"
            highlight={`${gmroi.length} categorias`}
            summary="Retorno de margem bruta sobre o valor médio de estoque, por categoria."
            mechanism={<p className="text-sm">Margem bruta realizada dividida pelo valor de estoque médio a custo — mede o que o dado diz, sem alvo esperado.</p>}
            evidence={
              <div>
                {gmroi.map((g) => (
                  <div key={g.category} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{g.category}{g.is_directional_only ? ' (aproximação)' : ''}</span>
                    <span className="text-xs">{g.gmroi !== null ? g.gmroi.toFixed(2) : 'sem estoque na categoria'}</span>
                  </div>
                ))}
              </div>
            }
          />
        )}

        {concentration.length > 0 && (
          <ExpandableCard
            id="tema-concentracao-cliente"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Concentração de Cliente"
            highlight={`${concentration[0].concentration_pct.toFixed(1)}%`}
            highlightClassName="negative"
            summary={`${concentration[0].customer} concentra a receita de ${concentration[0].store}.`}
            mechanism={<p className="text-sm">Risco de key-account: se este cliente parar de comprar, a loja sente de verdade — perda desproporcional para uma única unidade de negócio.</p>}
            evidence={
              <div>
                {concentration.map((c) => (
                  <div key={`${c.store}-${c.customer}`} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{c.customer} @ {c.store}</span>
                    <span className="text-xs">{c.concentration_pct.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            }
          />
        )}

        {rfm.length > 0 && (
          <ExpandableCard
            id="tema-rfm-campeoes"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Clientes Campeões (RFM)"
            highlight={`${rfm.length} clientes`}
            summary="Topo em recência, frequência e valor monetário ao mesmo tempo — a base a proteger a qualquer custo."
            mechanism={<p className="text-sm">Metodologia RFM clássica: cada dimensão ranqueada em quantis, campeão é topo nas 3 ao mesmo tempo.</p>}
            evidence={
              <div>
                {rfm.map((c) => (
                  <div key={c.customer_id} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{c.customer_id}</span>
                    <span className="text-xs">{formatCurrency(c.monetary)}</span>
                  </div>
                ))}
              </div>
            }
          />
        )}

        {churn.length > 0 && (
          <ExpandableCard
            id="tema-churn"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Churn Invisível"
            highlight={`${churn.length} clientes`}
            highlightClassName="negative"
            summary="Clientes recorrentes que pararam de comprar sem cancelamento formal."
            mechanism={<p className="text-sm">Compra com cadência regular, some além do padrão multiplicado por um limiar de sensibilidade — nunca um número mágico solto, vem do contrato de limiares.</p>}
            evidence={
              <div>
                {churn.slice(0, 15).map((c) => (
                  <div key={c.customer_id} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{c.customer_id}</span>
                    <span className="text-xs">{formatCurrency(c.historical_annual_value)} | {c.months_silent}m silente</span>
                  </div>
                ))}
              </div>
            }
            footnote={churn.length > 15 ? `+ ${churn.length - 15} outros clientes.` : undefined}
          />
        )}

        {salespeople.length > 0 && (
          <ExpandableCard
            id="tema-vendedor"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Performance de Vendedor"
            highlight={`${salespeople.filter((s) => s.low_capture_flag).length} com captura baixa`}
            summary="% de vendas com cliente identificado, avaliado independente de tenure ou volume."
            mechanism={<p className="text-sm">Captura de cliente e ramp-up são duas asserções independentes — um vendedor pode converter bem e ainda ter captura baixa, uma dimensão nunca perdoa a outra.</p>}
            evidence={
              <div>
                {salespeople.map((s) => (
                  <div key={s.salesperson} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                    <span className="text-sm font-semibold">{s.salesperson}{!s.has_sufficient_tenure ? ' (em rampa)' : ''}</span>
                    <span className={`text-xs ${s.low_capture_flag ? 'text-accent-red' : 'text-muted'}`}>{s.capture_rate_pct.toFixed(1)}% captura</span>
                  </div>
                ))}
              </div>
            }
          />
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 3: Commit**

```bash
git add src/components/sections/AchadosPorTema.tsx
git commit -m "feat(insight-board): seção 04 — achados por tema (produto, estoque, cliente, vendedor)"
```

---

### Task 7: Seção 06 — Qualidade de Dados

**Files:**
- Create: `src/components/sections/QualidadeDados.tsx`

**Interfaces:**
- Consumes: `ExpandableCard` (Task 1). Lê `report.cleaning` e `report.data_completeness` diretamente (campos escalares, sem necessidade de selector).
- Produces: `QualidadeDados({report, expandedId, onToggle}: SectionProps)`.

- [ ] **Step 1: Criar o componente**

```tsx
// src/components/sections/QualidadeDados.tsx
"use client";

import React from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import ExpandableCard from '@/components/ExpandableCard';

interface SectionProps {
  report: ExecutiveAuditReport;
  expandedId: string | null;
  onToggle: (id: string) => void;
}

export default function QualidadeDados({ report, expandedId, onToggle }: SectionProps) {
  const { cleaning, data_completeness } = report;
  const completeness = data_completeness[0];

  return (
    <section>
      <h2 className="text-2xl" style={{ marginBottom: '2rem' }}>Qualidade dos Dados</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
        <ExpandableCard
          id="qualidade-ingestao"
          expandedId={expandedId}
          onToggle={onToggle}
          title="Ingestão e Limpeza"
          highlight={`${cleaning.rows_accepted.toLocaleString('pt-BR')} / ${cleaning.rows_read.toLocaleString('pt-BR')}`}
          summary="Linhas aceitas sobre linhas lidas — nada é descartado em silêncio."
          mechanism={<p className="text-sm">Toda linha descartada tem motivo rastreado; todo valor podado por outlier estatístico mantém proveniência até a linha de origem.</p>}
          evidence={
            <div>
              {Object.entries(cleaning.rows_discarded_by_reason).map(([reason, count]) => (
                <div key={reason} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                  <span className="text-sm">{reason}</span>
                  <span className="text-xs">{count}</span>
                </div>
              ))}
              {cleaning.values_winsorized.length > 0 && (
                <div style={{ marginTop: '1rem' }}>
                  <p className="text-xs text-muted" style={{ marginBottom: '0.5rem' }}>Valores podados por outlier (nunca deletados, só limitados ao teto estatístico):</p>
                  {cleaning.values_winsorized.map((w, idx) => (
                    <div key={idx} className="text-xs" style={{ padding: '0.25rem 0' }}>
                      {w.source_file}:{w.source_row} — {w.product}: {w.original_value} → {w.capped_value}
                    </div>
                  ))}
                </div>
              )}
            </div>
          }
        />

        {completeness && (
          <ExpandableCard
            id="qualidade-completude"
            expandedId={expandedId}
            onToggle={onToggle}
            title="Completude de Cadastro"
            highlight={`${completeness.completeness_pct.toFixed(1)}%`}
            summary={`${completeness.total_customers} clientes cadastrados.`}
            mechanism={<p className="text-sm">Média de preenchimento entre telefone e CPF — completude por campo, não por cliente (um cliente com só 1 dado faltando não é penalizado como um sem nenhum).</p>}
            evidence={
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}>
                  <span className="text-sm">Telefone preenchido</span>
                  <span className="text-xs">{completeness.phone_filled_pct.toFixed(1)}%</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0' }}>
                  <span className="text-sm">CPF preenchido</span>
                  <span className="text-xs">{completeness.document_filled_pct.toFixed(1)}%</span>
                </div>
              </div>
            }
            footnote={completeness.contingency_triggered ? 'Completude abaixo do limiar — dado de contato pouco confiável nesta rodada.' : undefined}
          />
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 3: Commit**

```bash
git add src/components/sections/QualidadeDados.tsx
git commit -m "feat(insight-board): seção 06 — qualidade de dados (limpeza + completude)"
```

---

### Task 8: Seção 08 — Anexo de Metodologia

**Files:**
- Create: `src/components/sections/AnexoMetodologia.tsx`

**Interfaces:**
- Consumes: `ExpandableCard` (Task 1). Lê `report.thresholds` diretamente (19 campos escalares).
- Produces: `AnexoMetodologia({report, expandedId, onToggle}: SectionProps)`.

- [ ] **Step 1: Criar o componente**

```tsx
// src/components/sections/AnexoMetodologia.tsx
"use client";

import React from 'react';
import { ExecutiveAuditReport, AuditThresholdsConfig } from '@/types/audit';
import ExpandableCard from '@/components/ExpandableCard';

interface SectionProps {
  report: ExecutiveAuditReport;
  expandedId: string | null;
  onToggle: (id: string) => void;
}

const THRESHOLD_LABELS: Record<keyof AuditThresholdsConfig, string> = {
  revenue_drop_sigma: 'Desvio de vazamento de receita (σ)',
  churn_cadence_multiplier: 'Multiplicador de cadência de churn',
  churn_min_purchases: 'Mínimo de compras para avaliar churn',
  trend_decoupling_pct: 'Descolamento de tendência de produto (%)',
  seasonality_min_months: 'Meses mínimos para curva de sazonalidade',
  materiality_revenue_pct: 'Materialidade de receita (%)',
  rfm_bins: 'Quantis RFM',
  variable_cost_pct: 'Custo variável (% do preço)',
  latent_revenue_anchor_category: 'Categoria âncora (receita latente)',
  latent_revenue_target_category: 'Categoria alvo (receita latente)',
  latent_revenue_conversion_pct: 'Conversão assumida (receita latente, %)',
  dead_stock_months: 'Estoque morto (meses parado)',
  contingency_completeness_pct: 'Completude mínima de cadastro (%)',
  outlier_median_ratio: 'Razão de outlier sobre a mediana',
  cold_start_min_months: 'Histórico mínimo de loja (meses)',
  sev_min_capture_pct: 'Captura mínima de cliente (%)',
  sev_ramp_min_days: 'Rampa mínima de vendedor (dias)',
  concentration_risk_pct: 'Risco de concentração de cliente (%)',
  service_category_label: 'Rótulo da categoria de serviço',
  service_reconciliation_gap_tolerance: 'Tolerância de reconciliação serviço (R$)',
};

export default function AnexoMetodologia({ report, expandedId, onToggle }: SectionProps) {
  const entries = Object.entries(report.thresholds) as [keyof AuditThresholdsConfig, string | number][];

  return (
    <section>
      <h2 className="text-2xl" style={{ marginBottom: '2rem' }}>Anexo — Metodologia</h2>
      <ExpandableCard
        id="anexo-metodologia"
        expandedId={expandedId}
        onToggle={onToggle}
        title="Limiares usados nesta rodada"
        highlight={`${entries.length} limiares`}
        summary="Nenhum limiar vive dentro de um detector — todos vêm de um contrato de configuração único, versionado junto com o motor."
        mechanism={<p className="text-sm">Reprodutibilidade: com estes limiares registrados, sabe-se exatamente com quais parâmetros a auditoria rodou.</p>}
        evidence={
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.5rem' }}>
            {entries.map(([key, value]) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                <span className="text-xs text-muted">{THRESHOLD_LABELS[key]}</span>
                <span className="text-xs font-mono">{String(value)}</span>
              </div>
            ))}
          </div>
        }
      />
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 3: Commit**

```bash
git add src/components/sections/AnexoMetodologia.tsx
git commit -m "feat(insight-board): seção 08 — anexo de metodologia (19 limiares nomeados)"
```

---

### Task 9: Integração final — `InsightBoard.tsx` compõe todas as seções

**Files:**
- Modify: `src/components/InsightBoard.tsx` (reescrita completa — vira orquestrador magro)

**Interfaces:**
- Consumes: todos os componentes das Tasks 1, 3-8.

- [ ] **Step 1: Reescrever `InsightBoard.tsx`**

```tsx
// src/components/InsightBoard.tsx
"use client";

import React, { useState } from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import SumarioExecutivo from '@/components/sections/SumarioExecutivo';
import RankingDeLojas from '@/components/sections/RankingDeLojas';
import LojaALoja from '@/components/sections/LojaALoja';
import AchadosPorTema from '@/components/sections/AchadosPorTema';
import QualidadeDados from '@/components/sections/QualidadeDados';
import AnexoMetodologia from '@/components/sections/AnexoMetodologia';
import PlanoDeAcao from '@/components/sections/PlanoDeAcao';

interface InsightBoardProps {
  report: ExecutiveAuditReport;
}

export default function InsightBoard({ report }: InsightBoardProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const toggleExpand = (id: string) => setExpandedId((prev) => (prev === id ? null : id));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4rem' }}>
      <SumarioExecutivo report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <RankingDeLojas report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <LojaALoja report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <AchadosPorTema report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <QualidadeDados report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <AnexoMetodologia report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <PlanoDeAcao report={report} />
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx tsc --noEmit`
Expected: 0 erros

- [ ] **Step 3: Verificação visual — rodar o dev server**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npm run dev`
Abrir `http://localhost:3000` e confirmar:
- Todas as 7 seções renderizam sem erro no console do navegador.
- Clicar em pelo menos 1 card de cada seção expande e mostra N1 ("O Mecanismo") + N2 ("Evidência").
- Nenhum valor aparece como `undefined`/`NaN`/`[object Object]`.
- Encerrar o servidor (Ctrl+C) depois de confirmar.

- [ ] **Step 4: Remover código morto (imports não usados de `next/font`/etc, se sobrou algum)**

Run: `cd C:\Projetos\Aurora\aurora-frontend && npx eslint src/components/InsightBoard.tsx src/components/sections src/lib/selectors.ts src/components/ExpandableCard.tsx`
Expected: 0 erros (avisos de estilo, se houver, corrigir antes de commitar)

- [ ] **Step 5: Commit**

```bash
git add src/components/InsightBoard.tsx
git commit -m "feat(insight-board): compõe todas as seções no orquestrador principal"
```

---

## Definition of Done

- `npx tsc --noEmit` limpo na raiz do projeto.
- `npx eslint .` sem erros nos arquivos tocados.
- Dev server roda sem erro de console, todas as 7 seções visíveis e expansíveis.
- Nenhum arquivo fora de `src/lib/selectors.ts` faz `.reduce`/soma/percentual sobre dado do relatório — todo número vem de um campo já pronto.
- `src/types/audit.ts` continua espelhando exatamente `ExecutiveAuditReport` do backend (sem campos inventados).

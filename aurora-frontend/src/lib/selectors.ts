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

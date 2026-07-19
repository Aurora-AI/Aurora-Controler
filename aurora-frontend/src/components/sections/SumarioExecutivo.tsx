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

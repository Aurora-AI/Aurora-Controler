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

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

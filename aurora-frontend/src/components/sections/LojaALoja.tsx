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

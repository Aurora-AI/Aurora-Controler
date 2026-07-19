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

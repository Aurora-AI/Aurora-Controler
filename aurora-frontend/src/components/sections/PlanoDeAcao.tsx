// src/components/sections/PlanoDeAcao.tsx
"use client";

import React from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import { orderedActionPlan } from '@/lib/selectors';

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(value);

// Nota: esta seção NÃO usa ExpandableCard de propósito — é um resumo final pra ação
// rápida, não uma seção de investigação; não faz sentido esconder a descrição atrás
// de um clique. Exceção documentada e confirmada, não um desvio do padrão N0/N1/N2.
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

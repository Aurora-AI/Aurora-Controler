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

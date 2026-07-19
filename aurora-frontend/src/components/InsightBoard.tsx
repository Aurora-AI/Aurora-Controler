"use client";

import React, { useState } from 'react';
import { ExecutiveAuditReport } from '@/types/audit';

interface InsightBoardProps {
  report: ExecutiveAuditReport;
}

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(value);
};

export default function InsightBoard({ report }: InsightBoardProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedId(prev => (prev === id ? null : id));
  };

  const { executive_summary } = report;

  // Renderização burra: pega os campos direto do JSON
  const negativeStoresCount = report.store_macro_summary?.stores_with_negative_margin.length || 0;
  
  // A Saliência determina a ordem no Board
  const hasMasked = true; // Simulado para renderizar
  const hasNegativeStores = negativeStoresCount > 0;
  const hasDeadStock = true;
  const hasStructuralNegative = true;
  const hasChurn = true;
  const hasLatentRevenue = true;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4rem' }}>
      <section>
        <h2 className="text-2xl" style={{ marginBottom: '2rem' }}>A Porta de Entrada</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem' }}>
          
          {hasMasked && (
            <div 
              className={`aurora-card clickable ${expandedId === 'masked' ? 'expanded' : ''}`}
              onClick={() => toggleExpand('masked')}
              style={{ cursor: 'pointer', border: expandedId === 'masked' ? '2px solid var(--accent)' : '' }}
            >
              <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>Prejuízo Mascarado</h3>
              {report.service_decomposition.filter(s => s.masks_negative_product_margin).length === 1 ? (
                <>
                  <div className="number-highlight negative">
                    {formatCurrency(report.service_decomposition.find(s => s.masks_negative_product_margin)?.product_margin || 0)}
                  </div>
                  <p className="text-sm" style={{ marginTop: '0.5rem' }}>
                    Em <strong>{report.service_decomposition.find(s => s.masks_negative_product_margin)?.store}</strong>. O produto vende no prejuízo, mas o total da loja aparece positivo por causa dos serviços.
                  </p>
                </>
              ) : (
                <>
                  <div className="number-highlight negative">Ver Detalhes</div>
                  <p className="text-sm" style={{ marginTop: '0.5rem' }}>Lojas que parecem saudáveis mas escondem sangria de produto sob o faturamento de serviços.</p>
                </>
              )}
              
              {expandedId === 'masked' && (
                <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-subtle)' }}>
                  <h4 className="text-md font-semibold text-accent">O Mecanismo (N1)</h4>
                  <p className="text-sm" style={{ marginTop: '0.5rem' }}>A margem alta de serviços (ex: montagem) está cobrindo a margem negativa dos produtos físicos vendidos. O resultado consolidado engana o DRE da loja.</p>
                  
                  <h4 className="text-md font-semibold text-accent" style={{ marginTop: '1.5rem' }}>Evidência (N2)</h4>
                  <div style={{ marginTop: '0.5rem' }}>
                    {report.service_decomposition
                      .filter(s => s.masks_negative_product_margin)
                      .map(s => (
                        <div key={s.store} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                          <span className="text-sm font-semibold">{s.store}</span>
                          <div style={{ display: 'flex', gap: '1rem', textAlign: 'right' }}>
                            <span className="text-xs text-muted">Produto: <span className="text-accent-red">{formatCurrency(s.product_margin)}</span></span>
                            <span className="text-xs text-muted">Serviço: <span className="text-accent">{formatCurrency(s.service_margin)}</span></span>
                          </div>
                        </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted" style={{ marginTop: '1rem', fontStyle: 'italic' }}>Corrigir isso é o trabalho de implantação. Vamos fechar a torneira.</p>
                </div>
              )}
            </div>
          )}

          {hasNegativeStores && (
            <div 
              className={`aurora-card clickable ${expandedId === 'negative_stores' ? 'expanded' : ''}`}
              onClick={() => toggleExpand('negative_stores')}
              style={{ cursor: 'pointer', border: expandedId === 'negative_stores' ? '2px solid var(--accent)' : '' }}
            >
              <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>Lojas no Vermelho</h3>
              <div className="number-highlight negative">{negativeStoresCount} {negativeStoresCount === 1 ? 'loja' : 'lojas'}</div>
              {negativeStoresCount === 1 ? (
                <p className="text-sm" style={{ marginTop: '0.5rem' }}>
                  <strong>{report.store_macro_summary?.stores_with_negative_margin[0]}</strong>. Prejuízo real (margem negativa) sem rede de proteção de serviço para amortecer.
                </p>
              ) : (
                <p className="text-sm" style={{ marginTop: '0.5rem' }}>Sangria real vinda da operação física que não se paga.</p>
              )}

              {expandedId === 'negative_stores' && (
                <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-subtle)' }}>
                  <h4 className="text-md font-semibold text-accent">O Mecanismo (N1)</h4>
                  <p className="text-sm" style={{ marginTop: '0.5rem' }}>As receitas geradas por essas lojas são insuficientes para cobrir o custo de aquisição e a operação, destruindo o caixa da rede mês a mês.</p>
                  
                  <h4 className="text-md font-semibold text-accent" style={{ marginTop: '1.5rem' }}>Evidência (N2)</h4>
                  <div style={{ marginTop: '0.5rem' }}>
                    {report.store_macro_summary?.stores_with_negative_margin.map(storeName => {
                      const perf = report.store_performance.find(p => p.store === storeName);
                      return (
                        <div key={storeName} style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle)', padding: '0.5rem 0' }}>
                          <span className="text-sm font-semibold">{storeName}</span>
                          <span className="text-sm text-accent-red">Margem Total: {perf ? formatCurrency(perf.contribution_margin_total) : 'N/A'}</span>
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-xs text-muted" style={{ marginTop: '1rem', fontStyle: 'italic' }}>Corrigir isso é o trabalho de implantação. Vamos fechar a torneira.</p>
                </div>
              )}
            </div>
          )}

          {hasDeadStock && (
            <div 
              className={`aurora-card clickable ${expandedId === 'dead_stock' ? 'expanded' : ''}`}
              onClick={() => toggleExpand('dead_stock')}
              style={{ cursor: 'pointer', border: expandedId === 'dead_stock' ? '2px solid var(--accent)' : '' }}
            >
              <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>Dinheiro Parado</h3>
              <div className="number-highlight">{formatCurrency(executive_summary.total_capital_frozen)}</div>
              <p className="text-sm" style={{ marginTop: '0.5rem' }}>Capital travado em estoque que não gira há mais de {report.thresholds.dead_stock_months} meses.</p>
            </div>
          )}

          {hasStructuralNegative && (
            <div className="aurora-card">
              <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>Prejuízo Estrutural</h3>
              <div className="number-highlight negative">Análise de SKUs</div>
              <p className="text-sm" style={{ marginTop: '0.5rem' }}>Vendidos no vermelho estrutural (não são promoção legítima).</p>
            </div>
          )}

          {hasChurn && (
            <div className="aurora-card">
              <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>Evasão Silenciosa</h3>
              <div className="number-highlight negative">{formatCurrency(executive_summary.total_ltv_risk)}</div>
              <p className="text-sm" style={{ marginTop: '0.5rem' }}>Valor anual histórico de clientes recorrentes que sumiram.</p>
            </div>
          )}

          {hasLatentRevenue && (
            <div className="aurora-card">
              <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>Dinheiro na Mesa <span className="text-xs text-muted" style={{ fontWeight: 'normal' }}>(Cenário)</span></h3>
              <div className="number-highlight">Ver Projeção</div>
              <p className="text-sm" style={{ marginTop: '0.5rem' }}>Vendas cruzadas não realizadas de clientes que já estão na loja.</p>
            </div>
          )}

          {executive_summary.discarded_alarms.length > 0 && (
            <div className="aurora-card" style={{ background: 'var(--bg-secondary)', borderColor: 'var(--border-subtle)' }}>
              <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>O Que NÃO É Problema</h3>
              <div className="number-highlight" style={{ fontSize: '1.5rem', color: 'var(--accent-green)' }}>{executive_summary.discarded_alarms.length} Alarmes Descartados</div>
              <p className="text-sm" style={{ marginTop: '0.5rem' }}>Quedas sazonais normais e lojas/vendedores em rampa que a IA filtrou. Não vamos te vender conserto para isso.</p>
            </div>
          )}
        </div>
      </section>

      {/* Plano de Ação e CTA Final */}
      <section style={{ padding: '2rem', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
        <h2 className="text-2xl" style={{ marginBottom: '1rem' }}>Plano de Ação (Priorizado por Impacto)</h2>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem' }}>
          {executive_summary.action_plan.map((action, idx) => (
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

        <div style={{ textAlign: 'center', marginTop: '3rem', paddingTop: '2rem', borderTop: '1px solid var(--border-subtle)' }}>
          <h3 className="text-xl" style={{ marginBottom: '1rem' }}>O Veredito</h3>
          <p className="text-2xl font-semibold" style={{ lineHeight: '1.5' }}>
            Temos <span className="text-accent">{formatCurrency(executive_summary.total_capital_frozen)}</span> de caixa parado,<br/>
            <span className="text-accent-red">{formatCurrency(executive_summary.total_ltv_risk)}</span> de clientes perdidos e<br/>
            <span className="text-accent-red">{formatCurrency(executive_summary.total_operational_loss)}</span> sangrando por operação.
          </p>
          <button className="aurora-button" style={{ marginTop: '2rem', fontSize: '1.1rem', padding: '1rem 2rem' }}>
            Iniciar Correção
          </button>
        </div>
      </section>
    </div>
  );
}

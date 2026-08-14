import React from 'react';
import { AuditDataV4, Sangramento } from "../types/audit_v4";
import { Masthead, Footerband } from "./Shared";

interface Ato3SangramentosProps {
  data: AuditDataV4;
}

export default function Ato3Sangramentos({ data }: Ato3SangramentosProps) {
  const brl = (n: number) => 'R$ ' + Math.abs(n).toLocaleString('pt-BR', { maximumFractionDigits: 0 });

  const renderChart = (s: Sangramento) => {
    if (s.id === 'cap-caixa') {
      if (Array.isArray(s.treemap_itens) && s.treemap_itens.length > 0) {
        const shown = s.treemap_itens.slice(0, 5);
        const rest = s.treemap_itens.slice(5);
        const restSum = rest.reduce((a, x) => a + x.valor, 0);
        return (
          <div className="chartbox sans">
            <div className="treemap">
              {shown.map((x, i) => (
                <div key={i} className="cell" style={{ flexGrow: x.valor }}>
                  <b>{brl(x.valor)}</b>{x.nome}
                </div>
              ))}
              {rest.length > 0 && (
                <div className="cell agg" style={{ flexGrow: restSum }}>
                  <b>{brl(restSum)}</b>+ {rest.length} produtos no anexo
                </div>
              )}
            </div>
            <p className="axis-note">Área proporcional ao capital preso por produto.</p>
          </div>
        );
      } else {
        return (
          <div className="chartbox sans">
            <div className="treemap">
              <div className="cell" style={{ flexGrow: 1 }}>
                <b>{s.valor_display}</b>{s.treemap_total_itens} produtos sem giro — detalhamento por item no anexo
              </div>
            </div>
            <p className="axis-note">Mapa por produto disponível quando o motor exportar o detalhamento (procedência preservada — nada é estimado aqui).</p>
          </div>
        );
      }
    } else if (s.id === 'cap-clientes') {
      if (Array.isArray(s.serie_mensal) && s.serie_mensal.length > 0) {
        const mx = Math.max(...s.serie_mensal.map(m => m.valor));
        return (
          <div className="chartbox sans">
            <div className="bars">
              {s.serie_mensal.map((m, i) => (
                <div key={i} className="b" style={{ height: `${(m.valor / mx) * 100}%` }}>
                  <span>{m.mes}</span>
                </div>
              ))}
            </div>
            <p className="axis-note">Receita histórica dos clientes que pararam de comprar, mês a mês — o gotejamento.</p>
          </div>
        );
      } else {
        return (
          <div className="chartbox sans" style={{ textAlign: 'center', padding: '56px 40px' }}>
            <div className="money-hero" style={{ fontSize: 'clamp(48px,7vw,84px)' }}>
              <span className="bleed">{s.valor_display}</span>
            </div>
            <p className="axis-note" style={{ marginTop: '18px' }}>
              de receita histórica foi embora em silêncio · série mensal do gotejamento disponível quando o motor exportar a linha do tempo — nada é estimado aqui.
            </p>
          </div>
        );
      }
    } else {
      return (
        <div className="chartbox sans" style={{ display: 'flex', gap: '32px', alignItems: 'center', justifyContent: 'center', padding: '48px 40px', flexWrap: 'wrap' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '13px', color: 'var(--ink-soft)' }}>você paga</div>
            <div style={{ fontSize: '52px', fontWeight: 700 }}>R$ 190</div>
          </div>
          <div style={{ fontSize: '30px', color: 'var(--ink-soft)' }}>→</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '13px', color: 'var(--ink-soft)' }}>vende por</div>
            <div style={{ fontSize: '52px', fontWeight: 700 }}>R$ 200</div>
          </div>
          <div style={{ fontSize: '30px', color: 'var(--ink-soft)' }}>=</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '13px', color: 'var(--red)' }}>depois do custo de operar</div>
            <div style={{ fontSize: '52px', fontWeight: 700, color: 'var(--red)' }}>prejuízo</div>
          </div>
        </div>
      );
    }
  };

  return (
    <>
      {data.sangramentos.map((s, i) => (
        <section className="act" id={s.id} key={s.id}>
          <Masthead cliente={data.cliente} rodada={data.rodada} sub={`Capítulo ${i + 1} de 3 · ${s.titulo}`} />
          
          <p className="kicker sans">Sangramento 0{i + 1} — {s.titulo}</p>
          <div className="chapter-num sans bleed">{s.valor_display}</div>
          <h2 className="headline" style={{ fontSize: 'clamp(20px,2.6vw,28px)' }}>{s.soco}</h2>
          
          {renderChart(s)}
          
          <div className="evidence sans">
            {s.evidencias.slice(0, 3).map((e, idx) => (
              <div className="ev" key={idx}>
                <p>{e}</p>
              </div>
            ))}
          </div>
          
          <p className="cost-line"><b>Se nada mudar:</b> {s.custo_mensal}</p>
          <div className="hookband sans">{s.gancho}</div>
          
          <Footerband procedencia={data.procedencia} cta={data.cta} />
        </section>
      ))}
    </>
  );
}

import { AuditDataV4 } from "../types/audit_v4";
import { Masthead, Footerband } from "./Shared";

interface Ato2ParadoxoProps {
  data: AuditDataV4;
}

export default function Ato2Paradoxo({ data }: Ato2ParadoxoProps) {
  const P = data.paradoxo;
  
  // Lógica exata do waterfall do HTML de referência
  const H = 340;
  const PAD = 34;
  const maxUp = Math.max(P.total, P.servico + P.produto, 0);
  const maxDown = Math.min(P.produto, 0);
  const scale = maxUp - maxDown === 0 ? 0 : (H - PAD * 2) / (maxUp - maxDown);
  const zeroY = PAD + maxUp * scale;
  const y = (v: number) => zeroY - v * scale;
  
  const prodTop = zeroY;
  const prodH = Math.abs(P.produto) * scale;
  
  const svcTop = y(P.produto + P.servico);
  const svcH = P.servico * scale;
  
  const totTop = y(P.total);
  const totH = P.total * scale;

  const brl = (n: number) => 'R$ ' + Math.abs(n).toLocaleString('pt-BR', { maximumFractionDigits: 0 });

  return (
    <section className="act" id="ato2">
      <Masthead cliente={data.cliente} rodada={data.rodada} sub={`Ato 2 · A causa raiz — ${P.loja}`} />
      
      <p className="kicker sans">O paradoxo</p>
      
      <h2 className="headline">
        Sua loja campeã <span className="bleed">perde dinheiro em cada produto que vende.</span>
      </h2>
      
      <p className="sub">
        A {P.loja} lidera os seus relatórios. Mas separando <strong>o que ela vende</strong> do <strong>que ela conserta</strong> ({P.contexto}), o produto opera no prejuízo e o serviço paga a conta — e esconde o rombo.
      </p>
      
      <div className="chartbox sans">
        <div className="wf">
          <div className="baseline" style={{ top: `${zeroY}px` }}>
            <span className="zero">R$ 0</span>
          </div>
          
          <div className="col" style={{ left: '6%' }}>
            <div className="bar" style={{ top: `${prodTop}px`, height: `${prodH}px`, background: 'var(--red)' }}></div>
            <div className="blab" style={{ top: `${prodTop + prodH + 8}px`, color: 'var(--red)' }}>
              −{brl(P.produto)}
            </div>
            <div className="clab" style={{ top: `${zeroY + prodH + 44}px` }}>
              <b>Produto</b>
              o que a loja vende
            </div>
          </div>
          
          <div className="col" style={{ left: '38%' }}>
            <div className="bar" style={{ top: `${svcTop}px`, height: `${svcH}px`, background: 'var(--green)', opacity: 0.85 }}></div>
            <div className="blab" style={{ top: `${svcTop - 30}px`, color: 'var(--green)' }}>
              +{brl(P.servico)}
            </div>
            <div className="clab" style={{ top: `${zeroY + prodH + 44}px` }}>
              <b>Serviço</b>
              o que paga a conta
            </div>
          </div>
          
          <div className="col" style={{ left: '70%' }}>
            <div className="bar" style={{ 
              top: `${totTop}px`, 
              height: `${totH}px`, 
              background: 'var(--fake-green)',
              backgroundImage: 'repeating-linear-gradient(45deg,transparent,transparent 8px,rgba(255,255,255,.45) 8px,rgba(255,255,255,.45) 12px)'
            }}></div>
            <div className="blab" style={{ top: `${totTop - 30}px`, color: 'var(--ink-soft)' }}>
              +{brl(P.total)}
            </div>
            <div className="clab" style={{ top: `${zeroY + prodH + 44}px` }}>
              <b>Total que você vê</b>
              o “verde” de mentira
            </div>
          </div>
        </div>
        <p className="axis-note" style={{ marginTop: '100px' }}>
          A barra final é hachurada de propósito: o número é verdadeiro, a saúde é falsa — enquanto o total parecer saudável, o produto sangra sem alarme.
        </p>
      </div>
      
      <div className="evidence sans">
        <div className="ev" style={{ borderLeft: '4px solid var(--red)' }}>
          <div className="tag">A prova de controle</div>
          <p>
            <b>{P.controle.loja}</b> {P.controle.frase} (produto {P.controle.produto < 0 ? '−' : ''}{brl(P.controle.produto)})
          </p>
        </div>
        <div className="ev" style={{ borderLeft: '4px solid var(--ink)' }}>
          <div className="tag">O que isso pede</div>
          <p>
            Recompor mix e preço do produto <b>sem enfraquecer o serviço</b> que sustenta a loja — na ordem certa. Esse rebalanceamento é o trabalho de implantação.
          </p>
        </div>
      </div>
      
      <Footerband procedencia={data.procedencia} cta={data.cta} />
    </section>
  );
}

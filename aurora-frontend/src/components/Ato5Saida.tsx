import { AuditDataV4 } from "../types/audit_v4";
import { Masthead, Footerband } from "./Shared";

interface Ato5SaidaProps {
  data: AuditDataV4;
}

export default function Ato5Saida({ data }: Ato5SaidaProps) {
  // Ordena pelo que mais custa. Cenário sempre por último entre iguais.
  const plano = [...data.plano].sort((a, b) => {
    if (a.cenario && !b.cenario) return 1;
    if (!a.cenario && b.cenario) return -1;
    return b.impacto - a.impacto;
  });

  return (
    <section className="act" id="plano" style={{ borderBottom: 'none' }}>
      <Masthead cliente={data.cliente} rodada={data.rodada} sub="Ato 5 · O plano — ordenado pelo que mais custa" />
      
      <p className="kicker sans">A saída</p>
      
      <h2 className="headline">O diagnóstico está feito. A ordem abaixo é a ordem do dinheiro.</h2>
      
      <p className="sub">
        Cada item diz <strong>o quê</strong> corrigir. O <strong>como</strong> — implantação, rotina e acompanhamento — é o trabalho da consultoria.
      </p>
      
      <div className="plan sans">
        {plano.map((p, i) => (
          <div className={`pl${p.cenario ? ' scenario' : ''}`} key={i}>
            <div className="rank">{String(i + 1).padStart(2, '0')}</div>
            <div className="body">
              <b>{p.acao}</b>
              <p>{p.como}</p>
            </div>
            <div className="impact">{p.impacto_display}</div>
          </div>
        ))}
      </div>
      
      <Footerband procedencia={data.procedencia} cta={data.cta} />
    </section>
  );
}

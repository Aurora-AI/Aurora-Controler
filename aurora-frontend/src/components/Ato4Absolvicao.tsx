import { AuditDataV4 } from "../types/audit_v4";
import { Masthead, Footerband } from "./Shared";

interface Ato4AbsolvicaoProps {
  data: AuditDataV4;
}

export default function Ato4Absolvicao({ data }: Ato4AbsolvicaoProps) {
  return (
    <section className="act" id="ato4">
      <Masthead cliente={data.cliente} rodada={data.rodada} sub="Ato 4 · Os alarmes que descartamos" />
      
      <p className="kicker sans" style={{ color: 'var(--green)' }}>O que NÃO é problema</p>
      
      <h2 className="headline">Um sistema que só encontra problemas está vendendo medo.</h2>
      
      <p className="sub">
        O nosso descartou estes alarmes falsos antes de te mostrar qualquer vermelho. É por isso que os vermelhos deste laudo são reais.
      </p>
      
      <div className="honesty-list sans">
        {data.honestidade.map((h, i) => (
          <div className="hn" key={i}>
            <b>{h.alarme}</b> — {h.motivo}
          </div>
        ))}
      </div>
      
      <Footerband procedencia={data.procedencia} cta={data.cta} />
    </section>
  );
}

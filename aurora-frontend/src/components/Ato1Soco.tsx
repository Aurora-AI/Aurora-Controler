import { AuditDataV4 } from "../types/audit_v4";
import { Masthead, Footerband } from "./Shared";

interface Ato1SocoProps {
  data: AuditDataV4;
}

export default function Ato1Soco({ data }: Ato1SocoProps) {
  return (
    <section className="act" id="ato1">
      <Masthead cliente={data.cliente} rodada={data.rodada} sub="dados verificados linha a linha" />
      
      <p className="kicker sans">Sumário executivo</p>
      
      <div className="money-hero sans" style={{ marginTop: '16px' }}>
        <span className="bleed">{data.manchete.total_risco_display}</span>
      </div>
      
      <h2 className="headline">{data.manchete.frase}</h2>
      
      <p className="composition sans">
        <em>Composição do total (fatos medidos):</em> {data.manchete.composicao}
      </p>
      
      <div className="cards sans">
        {data.sangramentos.map((s, i) => (
          <article className="card" key={s.id}>
            <div className="tag">Sangramento 0{i + 1}</div>
            <div className="value">{s.valor_display}</div>
            <p className="cause">{s.soco}</p>
            <div className="fact">Fato medido</div>
            <a href={`#${s.id}`}>Capítulo: {s.titulo}</a>
          </article>
        ))}
      </div>
      
      <Footerband procedencia={data.procedencia} cta={data.cta} />
    </section>
  );
}

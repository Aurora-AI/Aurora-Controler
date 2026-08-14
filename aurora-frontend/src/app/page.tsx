import fs from 'fs';
import path from 'path';
import { AuditDataV4 } from '../types/audit_v4';
import Ato1Soco from '../components/Ato1Soco';
import Ato2Paradoxo from '../components/Ato2Paradoxo';
import Ato3Sangramentos from '../components/Ato3Sangramentos';
import Ato4Absolvicao from '../components/Ato4Absolvicao';
import Ato5Saida from '../components/Ato5Saida';

// Lendo estaticamente o arquivo de dados da "Última Milha" (gerado pelo motor Python).
// O Next.js funciona como o renderizador puro e seguro do JSON narrativo congelado.
function getAuditData(): AuditDataV4 {
  const filePath = path.join(process.cwd(), '..', 'laudo_executivo', 'rodadas', 'audit_data_v3.json');
  try {
    const fileContents = fs.readFileSync(filePath, 'utf8');
    return JSON.parse(fileContents) as AuditDataV4;
  } catch (err) {
    console.error("Falha ao ler audit_data_v3.json", err);
    throw new Error("Arquivo de dados do laudo não encontrado na raiz canônica.");
  }
}

export default function Home() {
  const data = getAuditData();

  return (
    <div id="app" className="wrap">
      <Ato1Soco data={data} />
      <Ato2Paradoxo data={data} />
      <Ato3Sangramentos data={data} />
      <Ato4Absolvicao data={data} />
      <Ato5Saida data={data} />
    </div>
  );
}

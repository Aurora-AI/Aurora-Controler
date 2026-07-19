import fs from 'fs';
import path from 'path';
import { ExecutiveAuditReport } from '@/types/audit';
import InsightBoard from '@/components/InsightBoard';

// Função para ler o JSON mockado (Server Component)
async function getAuditReport(): Promise<ExecutiveAuditReport> {
  const filePath = path.join(process.cwd(), 'src/data/mock_audit_report.json');
  const fileContents = fs.readFileSync(filePath, 'utf8');
  return JSON.parse(fileContents);
}

export default async function Home() {
  const report = await getAuditReport();

  return (
    <main className="container" style={{ paddingTop: '4rem', paddingBottom: '4rem' }}>
      <header style={{ marginBottom: '4rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '2rem' }}>
        <h1 className="text-4xl">Laudo Executivo de Operação</h1>
        <p className="text-muted text-lg" style={{ marginTop: '0.5rem' }}>
          Período auditado: {report.period_start} a {report.period_end}
        </p>
      </header>

      <InsightBoard report={report} />


      
      <footer style={{ marginTop: '4rem', paddingTop: '2rem', borderTop: '1px solid var(--border-subtle)', textAlign: 'center' }}>
        <p className="text-sm text-muted">Selo de Imutabilidade — Gerado em {report.generated_at}</p>
        <p className="text-xs text-muted" style={{ marginTop: '0.5rem' }}>
          {report.cleaning.rows_accepted.toLocaleString('pt-BR')} linhas aceitas de {report.cleaning.rows_read.toLocaleString('pt-BR')} totais auditadas.
        </p>
      </footer>
    </main>
  );
}

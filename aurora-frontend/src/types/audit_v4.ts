export interface Manchete {
  total_risco_display: string;
  frase: string;
  composicao: string;
}

export interface ControleParadoxo {
  loja: string;
  produto: number;
  frase: string;
}

export interface Paradoxo {
  loja: string;
  produto: number;
  servico: number;
  total: number;
  contexto: string;
  controle: ControleParadoxo;
}

export interface SerieMensal {
  mes: string;
  valor: number;
}

export interface TreemapItem {
  nome: string;
  valor: number;
}

export interface Sangramento {
  id: string;
  titulo: string;
  valor_display: string;
  soco: string;
  serie_mensal?: SerieMensal[];
  treemap_itens?: TreemapItem[];
  treemap_total_itens?: number;
  evidencias: string[];
  custo_mensal: string;
  gancho: string;
}

export interface AlarmeDescartado {
  alarme: string;
  motivo: string;
}

export interface AcaoPlano {
  acao: string;
  impacto: number;
  impacto_display: string;
  cenario: boolean;
  como: string;
}

export interface AuditDataV4 {
  rodada: string;
  cliente: string;
  manchete: Manchete;
  paradoxo: Paradoxo;
  sangramentos: Sangramento[];
  honestidade: AlarmeDescartado[];
  plano: AcaoPlano[];
  cta: string;
  procedencia: string;
}

"use client";

import React, { useState } from 'react';
import { ExecutiveAuditReport } from '@/types/audit';
import SumarioExecutivo from '@/components/sections/SumarioExecutivo';
import RankingDeLojas from '@/components/sections/RankingDeLojas';
import LojaALoja from '@/components/sections/LojaALoja';
import AchadosPorTema from '@/components/sections/AchadosPorTema';
import QualidadeDados from '@/components/sections/QualidadeDados';
import AnexoMetodologia from '@/components/sections/AnexoMetodologia';
import PlanoDeAcao from '@/components/sections/PlanoDeAcao';

interface InsightBoardProps {
  report: ExecutiveAuditReport;
}

export default function InsightBoard({ report }: InsightBoardProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const toggleExpand = (id: string) => setExpandedId((prev) => (prev === id ? null : id));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4rem' }}>
      <SumarioExecutivo report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <RankingDeLojas report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <LojaALoja report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <AchadosPorTema report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <QualidadeDados report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <AnexoMetodologia report={report} expandedId={expandedId} onToggle={toggleExpand} />
      <PlanoDeAcao report={report} />
    </div>
  );
}

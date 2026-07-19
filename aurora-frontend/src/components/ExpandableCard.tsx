"use client";

import React from 'react';

export interface ExpandableCardProps {
  id: string;
  expandedId: string | null;
  onToggle: (id: string) => void;
  title: string;
  highlight: React.ReactNode;
  highlightClassName?: string;
  summary: React.ReactNode;
  mechanism: React.ReactNode;
  evidence: React.ReactNode;
  footnote?: React.ReactNode;
}

export default function ExpandableCard({
  id,
  expandedId,
  onToggle,
  title,
  highlight,
  highlightClassName,
  summary,
  mechanism,
  evidence,
  footnote,
}: ExpandableCardProps) {
  const isExpanded = expandedId === id;

  return (
    <div
      className={`aurora-card clickable ${isExpanded ? 'expanded' : ''}`}
      onClick={() => onToggle(id)}
      style={{ cursor: 'pointer', border: isExpanded ? '2px solid var(--accent)' : '' }}
    >
      <h3 className="text-lg font-semibold" style={{ marginBottom: '0.5rem' }}>{title}</h3>
      <div className={`number-highlight ${highlightClassName ?? ''}`}>{highlight}</div>
      <p className="text-sm" style={{ marginTop: '0.5rem' }}>{summary}</p>

      {isExpanded && (
        <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--border-subtle)' }}>
          <h4 className="text-md font-semibold text-accent">O Mecanismo (N1)</h4>
          <div style={{ marginTop: '0.5rem' }}>{mechanism}</div>

          <h4 className="text-md font-semibold text-accent" style={{ marginTop: '1.5rem' }}>Evidência (N2)</h4>
          <div style={{ marginTop: '0.5rem' }}>{evidence}</div>

          {footnote && (
            <p className="text-xs text-muted" style={{ marginTop: '1rem', fontStyle: 'italic' }}>{footnote}</p>
          )}
        </div>
      )}
    </div>
  );
}

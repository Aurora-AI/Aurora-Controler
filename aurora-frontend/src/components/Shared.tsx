import React from 'react';

interface MastheadProps {
  cliente: string;
  rodada: string;
  sub: string;
}

export function Masthead({ cliente, rodada, sub }: MastheadProps) {
  return (
    <header className="masthead sans">
      <h1>EXRS Data Oracle · Executive Audit Report</h1>
      <div className="meta">{cliente} — Rodada {rodada} · {sub}</div>
    </header>
  );
}

interface FooterbandProps {
  procedencia: string;
  cta: string;
}

export function Footerband({ procedencia, cta }: FooterbandProps) {
  return (
    <footer className="footerband sans">
      <p className="prov">{procedencia}</p>
      <a className="cta" href="#plano">{cta}</a>
    </footer>
  );
}

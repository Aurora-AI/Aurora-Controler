"""
EXRS CLI — Relatório executivo do Data Oracle (`exrs audit`).

Este HTML é para consumo ESTRITAMENTE LOCAL do CSO/consultor: cruza o
ExecutiveAuditReport (já pseudo-anonimizado — "Client_A", "Client_B"...) com o
identity_map local para exibir os nomes REAIS de cliente na tela. O JSON que
eventualmente viajar à nuvem (OS 2, sintetizador LLM) continua usando só os pseudônimos —
a tradução de volta acontece apenas aqui, no artefato de leitura local.
"""
import datetime

from product_b.oracle.forensic_contracts import ExecutiveAuditReport

_SEVERITY_COLORS = {"low": "#64748B", "medium": "#D97706", "high": "#DC2626"}
_MONTH_NAMES = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}


def _esc(v: object) -> str:
    return (
        str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")


def _build_cleaning_section(report: ExecutiveAuditReport) -> str:
    c = report.cleaning
    reasons = "".join(
        f"<li>{_esc(reason)}: {count}</li>"
        for reason, count in c.rows_discarded_by_reason.items()
    ) or "<li>nenhuma linha descartada</li>"
    skipped = "".join(
        f"<li>{_esc(f['file'])} — {_esc(f['reason'])}</li>" for f in c.files_skipped
    ) or "<li>nenhum arquivo pulado</li>"
    
    discard_rate = (c.rows_read - c.rows_accepted) / c.rows_read if c.rows_read > 0 else 0
    discard_alert = ""
    if discard_rate > 0.05:
        discard_alert = f"<div class='alert-red'>⚠️ ALERTA FORENSE: Taxa de descarte abusiva ({discard_rate:.1%}). A integridade estatística do relatório está comprometida.</div>"

    raw_rev = c.raw_declared_revenue or 0.0
    gap = c.reconciliation_gap or 0.0
    gap_pct = (abs(gap) / raw_rev * 100) if raw_rev else 0.0
    
    gap_alert = ""
    if gap != 0:
        gap_alert = f"<div class='alert-red'>⚠️ RECONCILIAÇÃO FALHOU: O Faturamento Declarado ({_fmt_brl(raw_rev)}) difere do Grid Transacional Aceito ({_fmt_brl(raw_rev - gap)}). Gap: {_fmt_brl(gap)} ({gap_pct:.2f}%).</div>"
    else:
        gap_alert = f"<div class='alert-green'>✅ Reconciliação de Grid: Sucedida ({_fmt_brl(raw_rev)} bate com grid transacional).</div>"

    return f"""
    {gap_alert}
    {discard_alert}
    <div class="kpi-row">
      <div class="kpi"><span class="kpi-value">{c.rows_read}</span><span class="kpi-label">linhas lidas</span></div>
      <div class="kpi"><span class="kpi-value">{c.rows_accepted}</span><span class="kpi-label">linhas aceitas</span></div>
      <div class="kpi"><span class="kpi-value">{c.rows_read - c.rows_accepted}</span><span class="kpi-label">linhas descartadas ({discard_rate:.1%})</span></div>
    </div>
    <details>
      <summary>Motivos de descarte / arquivos pulados</summary>
      <ul>{reasons}</ul>
      <ul>{skipped}</ul>
    </details>
    """


def _build_revenue_leaks_table(report: ExecutiveAuditReport) -> str:
    c = report.cleaning
    gap = c.reconciliation_gap or 0.0
    
    if gap != 0:
        header_msg = "<div class='alert-red'>🚨 SELO DE SEGURANÇA DESATIVADO: Gap de reconciliação detectado. A ausência de anomalias listadas abaixo NÃO garante ausência de vazamentos, pois o total financeiro está mascarado/corrompido.</div>"
    elif not report.revenue_leaks:
        header_msg = "<p class='clean'>✅ Nenhum vazamento de receita detectado. (Grid de dados validado financeiramente)</p>"
    else:
        header_msg = ""
        
    if not report.revenue_leaks:
        return header_msg

    rows = "\n".join(
        f"<tr><td>{_esc(a.scope)}</td><td>{_esc(a.entity_id)}</td><td>{_esc(a.period)}</td>"
        f"<td>{_fmt_brl(a.expected_value)}</td><td>{_fmt_brl(a.actual_value)}</td>"
        f"<td>{a.drop_sigma:.2f}σ</td>"
        f"<td><span class='badge' style='background:{_SEVERITY_COLORS.get(a.severity, '#64748B')}'>{_esc(a.severity)}</span></td></tr>"
        for a in report.revenue_leaks
    )
    return f"""
    {header_msg}
    <table>
      <thead><tr><th>Escopo</th><th>Entidade</th><th>Período</th><th>Esperado</th>
      <th>Realizado</th><th>Desvio</th><th>Severidade</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _build_churn_table(report: ExecutiveAuditReport, identity_map: dict[str, str]) -> str:
    if not report.churn_findings:
        return "<p class='clean'>✅ Nenhum cliente em churn invisível detectado.</p>"
    pseudonym_to_real = {pseudonym: real for real, pseudonym in identity_map.items()}
    rows = "\n".join(
        f"<tr><td>{_esc(pseudonym_to_real.get(f.customer_id, f.customer_id))}</td>"
        f"<td>{f.purchase_count}</td><td>{f.avg_cadence_days:.0f} dias</td>"
        f"<td>{_esc(f.last_purchase)}</td><td>{f.months_silent} mês(es)</td>"
        f"<td>{_fmt_brl(f.historical_annual_value)}</td></tr>"
        for f in report.churn_findings
    )
    return f"""
    <table>
      <thead><tr><th>Cliente</th><th>Compras</th><th>Cadência média</th>
      <th>Última compra</th><th>Meses em silêncio</th><th>Valor histórico anual</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _build_product_trends_table(report: ExecutiveAuditReport) -> str:
    if not report.product_trends:
        return "<p class='clean'>Nenhum produto analisado.</p>"
    
    rows = []
    for t in report.product_trends:
        trend = "⚠️ descolado" if t.decoupled else "✅ acompanha"
        margin = f"{t.short_term_margin:.1f}%" if t.short_term_margin is not None else "—"
        if t.has_formula_errors:
            trend += " <span class='badge' style='background:#DC2626'>ERRO DE FÓRMULA</span>"
            
        rows.append(
            f"<tr><td>{_esc(t.product)}</td><td>{t.company_growth_pct:+.1f}%</td>"
            f"<td>{t.product_growth_pct:+.1f}%</td>"
            f"<td>{trend}</td>"
            f"<td>{margin}</td>"
            f"<td>{_esc(t.last_sale_month or '—')}</td></tr>"
        )
        
    rows_html = "\n".join(rows)
    return f"""
    <table>
      <thead><tr><th>Produto</th><th>Crescimento empresa</th><th>Crescimento produto</th>
      <th>Tendência</th><th>Margem Curto-Prazo</th><th>Última venda</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    """


def _build_seasonality_section(report: ExecutiveAuditReport) -> str:
    parts = []
    for curve in report.seasonality:
        if curve.insufficient_data:
            parts.append(
                f"<p class='clean'>ℹ️ Sazonalidade ({_esc(curve.entity)}): dados "
                f"insuficientes ({curve.months_available} mês(es) de histórico).</p>"
            )
            continue
        cells = "".join(
            f"<td>{_MONTH_NAMES.get(m, m)}<br><b>{idx:.2f}</b></td>"
            for m, idx in sorted(curve.monthly_index.items())
        )
        parts.append(f"<table class='seasonality'><tbody><tr>{cells}</tr></tbody></table>")
    return "\n".join(parts)


def render_audit_report(
    report: ExecutiveAuditReport, identity_map: dict[str, str], source_label: str,
) -> str:
    """Retorna o HTML completo do relatório executivo (nomes reais de cliente,
    cruzados via identity_map — consumo estritamente local)."""
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    css = """
    body { font-family: -apple-system, "Segoe UI", sans-serif; background:#F8FAFC;
           color:#0F172A; margin:0; }
    .page { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
    h1 { font-weight:600; color:#0F172A; margin-bottom:4px; }
    h2 { font-size:16px; font-weight:600; color:#334155; margin-top:32px; text-transform:uppercase; letter-spacing:0.04em; }
    .sub { color:#64748B; font-size:13px; margin-bottom:24px; }
    .kpi-row { display:flex; gap:16px; margin-bottom:12px; }
    .kpi { background:#fff; border:1px solid #E2E8F0; border-radius:8px; padding:16px 20px; flex:1; }
    .kpi-value { display:block; font-size:24px; font-weight:700; color:#0F172A; }
    .kpi-label { display:block; font-size:12px; color:#64748B; margin-top:4px; }
    table { width:100%; border-collapse:collapse; background:#fff; border:1px solid #E2E8F0; border-radius:8px; overflow:hidden; }
    th, td { text-align:left; padding:10px 14px; border-bottom:1px solid #F1F5F9; font-size:13px; }
    th { color:#64748B; font-weight:600; background:#F8FAFC; }
    table.seasonality td { text-align:center; }
    .badge { color:#fff; padding:2px 10px; border-radius:4px; font-size:11px; }
    .clean { color:#16A34A; font-size:14px; }
    details { margin-top:8px; font-size:13px; color:#475569; }
    .alert-red { background: #FEF2F2; color: #991B1B; border-left: 4px solid #DC2626; padding: 12px; margin-bottom: 16px; font-size: 14px; border-radius: 4px; font-weight: 500; line-height: 1.4; }
    .alert-green { background: #F0FDF4; color: #166534; border-left: 4px solid #16A34A; padding: 12px; margin-bottom: 16px; font-size: 14px; border-radius: 4px; font-weight: 500; line-height: 1.4; }
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <title>EXRS — Auditoria Comercial de {_esc(source_label)}</title>
  <style>{css}</style>
</head>
<body>
<div class="page">
  <h1>📊 Auditoria Forense Comercial — {_esc(source_label)}</h1>
  <div class="sub">Gerado em {now} · Período: {_esc(report.period_start)} a
    {_esc(report.period_end)} · Uso estritamente local — este relatório contém
    identidades reais de clientes.</div>

  <h2>Ingestão e Limpeza</h2>
  {_build_cleaning_section(report)}

  <h2>Vazamento de Receita</h2>
  {_build_revenue_leaks_table(report)}

  <h2>Churn Invisível</h2>
  {_build_churn_table(report, identity_map)}

  <h2>Tendência de Produto</h2>
  {_build_product_trends_table(report)}

  <h2>Sazonalidade</h2>
  {_build_seasonality_section(report)}
</div>
</body>
</html>"""

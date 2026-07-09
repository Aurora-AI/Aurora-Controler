"""
EXRS Data Oracle — Motor determinístico de auditoria comercial.

Ingestão pandas (pasta/arquivo) → limpeza rastreável → 4 detectores matemáticos puros
(vazamento de receita, churn invisível, tendência de produto, sazonalidade) →
pseudo-anonimização de identidades de cliente antes de montar o artefato final. Nenhum
LLM aqui — toda decisão é determinística e reproduzível (thresholds registrados no
report).
"""
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from oracle.column_mapper import (
    ColumnMappingError, DateAmbiguityError, coerce_currency_series, coerce_date_series,
    infer_column_roles,
)
from oracle.forensic_contracts import (
    AuditThresholdsConfig, ChurnFinding, CleaningSummary, ExecutiveAuditReport,
    ProductTrendEntry, RevenueLeakAnomaly, SalesRecord, SeasonalityCurve,
)

_SUPPORTED_SUFFIXES = {".xlsx", ".csv"}


def _read_raw(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str)
    return pd.read_excel(path, dtype=str, engine="openpyxl")


def load_sales_records(
    path: Path, mapping_override: dict[str, str] | None = None,
) -> tuple[list[SalesRecord], CleaningSummary]:
    """Ingere um arquivo (.xlsx/.csv) OU uma pasta inteira, higieniza e retorna os
    SalesRecord aceitos + a contabilidade completa da limpeza. Arquivo cujo esquema não
    produz os 4 papéis mínimos é pulado e reportado — nunca mesclado errado."""
    path = Path(path)
    files = (
        sorted(f for f in path.iterdir() if f.suffix.lower() in _SUPPORTED_SUFFIXES)
        if path.is_dir() else [path]
    )

    records: list[SalesRecord] = []
    rows_read = 0
    discarded_by_reason: dict[str, int] = {}
    files_skipped: list[dict] = []

    for file_path in files:
        raw = _read_raw(file_path)
        rows_read += len(raw)
        try:
            roles = infer_column_roles(raw, override=mapping_override)
            dates = coerce_date_series(raw[roles["date"]])
            values = coerce_currency_series(raw[roles["value"]])
            products = raw[roles["product"]].astype(str)
            customers = raw[roles["customer"]].astype(str)
            quantities = (
                coerce_currency_series(raw[roles["quantity"]])
                if "quantity" in roles else pd.Series([None] * len(raw))
            )
        except (ColumnMappingError, DateAmbiguityError) as e:
            # Arquivo com esquema incompatível ou mistura de formato de data: pulado e
            # reportado — nunca mesclado errado, nunca derruba a auditoria inteira.
            files_skipped.append({"file": file_path.name, "reason": str(e)})
            continue

        for i in range(len(raw)):
            if pd.isna(dates.iloc[i]):
                discarded_by_reason["data_invalida"] = discarded_by_reason.get("data_invalida", 0) + 1
                continue
            if pd.isna(values.iloc[i]):
                discarded_by_reason["valor_nao_numerico"] = discarded_by_reason.get("valor_nao_numerico", 0) + 1
                continue
            qty = quantities.iloc[i]
            records.append(SalesRecord(
                date=dates.iloc[i].to_pydatetime(),
                product=products.iloc[i],
                customer=customers.iloc[i],
                value=float(values.iloc[i]),
                quantity=None if qty is None or pd.isna(qty) else float(qty),
                source_file=file_path.name,
                source_row=i + 2,  # +1 para 1-indexado, +1 para o cabeçalho
            ))

    summary = CleaningSummary(
        rows_read=rows_read, rows_accepted=len(records),
        rows_discarded_by_reason=discarded_by_reason, files_skipped=files_skipped,
    )
    return records, summary


def _records_to_frame(records: list[SalesRecord]) -> pd.DataFrame:
    return pd.DataFrame([{
        "date": pd.Timestamp(r.date), "product": r.product,
        "customer": r.customer, "value": r.value,
    } for r in records])


def detect_revenue_leaks(df: pd.DataFrame, thresholds: AuditThresholdsConfig) -> list[RevenueLeakAnomaly]:
    """Queda mês-a-mês além de `revenue_drop_sigma` desvios-padrão da variação
    histórica da própria série (total e por produto)."""
    anomalies: list[RevenueLeakAnomaly] = []
    df = df.copy()
    df["period"] = df["date"].dt.to_period("M")

    def _scan(series: pd.Series, scope: str, entity_id: str) -> None:
        series = series.sort_index()
        if len(series) < 3:
            return
        diffs = series.diff().dropna()
        std = diffs.std()
        if not std or std == 0:
            return
        for period, value in series.items():
            prev = series.get(period - 1)
            if prev is None:
                continue
            diff = value - prev
            sigma = -diff / std
            if sigma >= thresholds.revenue_drop_sigma:
                severity = "high" if sigma >= thresholds.revenue_drop_sigma * 1.5 else "medium"
                anomalies.append(RevenueLeakAnomaly(
                    scope=scope, entity_id=entity_id, period=str(period),
                    expected_value=float(prev), actual_value=float(value),
                    drop_sigma=float(sigma), severity=severity,
                ))

    total_series = df.groupby("period")["value"].sum()
    _scan(total_series, "total", "total")

    for product, group in df.groupby("product"):
        product_series = group.groupby("period")["value"].sum()
        _scan(product_series, "product", product)

    return anomalies


def detect_churn(df: pd.DataFrame, thresholds: AuditThresholdsConfig) -> list[ChurnFinding]:
    """Cliente com >= churn_min_purchases compras e cadência média M; sem comprar há
    mais que churn_cadence_multiplier x M -> churn invisível (nunca cancelou formalmente)."""
    findings: list[ChurnFinding] = []
    global_max_date = df["date"].max()

    for customer, group in df.groupby("customer"):
        purchase_dates = sorted(group["date"].dt.normalize().unique())
        purchase_count = len(purchase_dates)
        if purchase_count < thresholds.churn_min_purchases:
            continue

        diffs_days = [
            (purchase_dates[i + 1] - purchase_dates[i]).days
            for i in range(len(purchase_dates) - 1)
        ]
        if not diffs_days:
            continue
        avg_cadence_days = sum(diffs_days) / len(diffs_days)

        last_purchase = pd.Timestamp(purchase_dates[-1])
        days_since_last = (global_max_date - last_purchase).days

        if days_since_last > thresholds.churn_cadence_multiplier * avg_cadence_days:
            last_period = last_purchase.to_period("M")
            global_period = global_max_date.to_period("M")
            months_silent = (
                (global_period.year * 12 + global_period.month)
                - (last_period.year * 12 + last_period.month)
            )
            findings.append(ChurnFinding(
                customer_id=customer, purchase_count=purchase_count,
                avg_cadence_days=float(avg_cadence_days),
                last_purchase=last_purchase.strftime("%Y-%m-%d"),
                months_silent=int(months_silent),
                historical_annual_value=float(group["value"].sum()),
            ))

    return findings


def detect_product_trends(df: pd.DataFrame, thresholds: AuditThresholdsConfig) -> list[ProductTrendEntry]:
    """Produto cuja curva de crescimento (1a vs 2a metade do período) descolou da
    empresa como um todo."""
    df = df.copy()
    df["period"] = df["date"].dt.to_period("M")
    periods = sorted(df["period"].unique())
    midpoint = periods[len(periods) // 2]

    def _growth_pct(values_before: float, values_after: float) -> float:
        if values_before == 0:
            return 0.0
        return (values_after - values_before) / values_before * 100.0

    company_before = df[df["period"] < midpoint]["value"].sum()
    company_after = df[df["period"] >= midpoint]["value"].sum()
    company_growth_pct = _growth_pct(company_before, company_after)

    entries: list[ProductTrendEntry] = []
    for product, group in df.groupby("product"):
        before = group[group["period"] < midpoint]["value"].sum()
        after = group[group["period"] >= midpoint]["value"].sum()
        product_growth_pct = _growth_pct(before, after)

        decoupled = product_growth_pct <= thresholds.trend_decoupling_pct and company_growth_pct > 0

        last_sale_period = group["period"].max() if len(group) else None
        entries.append(ProductTrendEntry(
            product=product, company_growth_pct=float(company_growth_pct),
            product_growth_pct=float(product_growth_pct), decoupled=bool(decoupled),
            last_sale_month=str(last_sale_period) if last_sale_period is not None else None,
        ))

    return entries


def detect_seasonality(df: pd.DataFrame, thresholds: AuditThresholdsConfig) -> list[SeasonalityCurve]:
    """Índice de sazonalidade mensal (total). Com histórico < seasonality_min_months,
    reporta insuficiência explícita — nunca inventa curva."""
    df = df.copy()
    df["period"] = df["date"].dt.to_period("M")
    months_available = df["period"].nunique()

    if months_available < thresholds.seasonality_min_months:
        return [SeasonalityCurve(
            scope="total", entity="total", monthly_index=None,
            insufficient_data=True, months_available=int(months_available),
        )]

    monthly_totals = df.groupby("period")["value"].sum()
    overall_mean = monthly_totals.mean()
    by_month_of_year = monthly_totals.groupby(monthly_totals.index.month).mean()
    monthly_index = {
        int(month): float(value / overall_mean) if overall_mean else 0.0
        for month, value in by_month_of_year.items()
    }

    return [SeasonalityCurve(
        scope="total", entity="total", monthly_index=monthly_index,
        insufficient_data=False, months_available=int(months_available),
    )]


def _pseudonym_code(index: int) -> str:
    """Índice 0-based → código estilo coluna de Excel: A, B, ..., Z, AA, AB, ...
    Escala para qualquer número de clientes (o antigo string.ascii_uppercase[i] estourava
    IndexError acima de 26 — bug exposto pela fixture de ótica com 200 clientes)."""
    letters = ""
    n = index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def anonymize_customers(records: list[SalesRecord]) -> tuple[list[SalesRecord], dict[str, str]]:
    """Pseudo-anonimização determinística: Client_A, Client_B... Client_Z, Client_AA...
    ordenados por valor histórico decrescente (reprodutível — mesma entrada sempre gera o
    mesmo mapa)."""
    totals: dict[str, float] = {}
    for r in records:
        totals[r.customer] = totals.get(r.customer, 0.0) + r.value

    ordered = sorted(totals.keys(), key=lambda name: (-totals[name], name))
    identity_map = {name: f"Client_{_pseudonym_code(i)}" for i, name in enumerate(ordered)}

    anonymized = [r.model_copy(update={"customer": identity_map[r.customer]}) for r in records]
    return anonymized, identity_map


def run_audit(
    path: Path,
    thresholds: AuditThresholdsConfig | None = None,
    mapping_override: dict[str, str] | None = None,
    return_identity_map: bool = False,
) -> ExecutiveAuditReport | tuple[ExecutiveAuditReport, dict[str, str]]:
    """Ponto de entrada do motor: ingestão + limpeza + 4 detectores + anonimização."""
    thresholds = thresholds or AuditThresholdsConfig()
    records, cleaning = load_sales_records(path, mapping_override=mapping_override)

    df = _records_to_frame(records)

    revenue_leaks = detect_revenue_leaks(df, thresholds)
    churn_findings = detect_churn(df, thresholds)
    product_trends = detect_product_trends(df, thresholds)
    seasonality = detect_seasonality(df, thresholds)

    _, identity_map = anonymize_customers(records)

    for finding in churn_findings:
        finding.customer_id = identity_map.get(finding.customer_id, finding.customer_id)
    for leak in revenue_leaks:
        if leak.scope == "customer":
            leak.entity_id = identity_map.get(leak.entity_id, leak.entity_id)

    period_start = str(df["date"].min().to_period("M")) if len(df) else ""
    period_end = str(df["date"].max().to_period("M")) if len(df) else ""

    report = ExecutiveAuditReport(
        period_start=period_start, period_end=period_end, cleaning=cleaning,
        thresholds=thresholds, revenue_leaks=revenue_leaks, churn_findings=churn_findings,
        product_trends=product_trends, seasonality=seasonality,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    if return_identity_map:
        return report, identity_map
    return report

"""
EXRS Data Oracle — Motor determinístico de auditoria comercial.

Ingestão pandas (pasta/arquivo) → limpeza rastreável → 4 detectores matemáticos puros
(vazamento de receita, churn invisível, tendência de produto, sazonalidade) →
pseudo-anonimização de identidades de cliente antes de montar o artefato final. Nenhum
LLM aqui — toda decisão é determinística e reproduzível (thresholds registrados no
report).
"""
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from oracle.column_mapper import (
    _CLIENTES_REQUIRED_ROLES, _CLIENTES_ROLE_KEYWORDS, _ESTOQUE_REQUIRED_ROLES,
    _ESTOQUE_ROLE_KEYWORDS, ColumnMappingError, DateAmbiguityError, coerce_currency_series,
    coerce_date_series, infer_column_roles,
)
from oracle.forensic_contracts import (
    AuditThresholdsConfig, ChurnFinding, CleaningSummary, ContributionMarginAlert,
    DataCompletenessFinding, DeadStockFinding, ExecutiveAuditReport, GmroiEntry,
    LatentRevenueFinding, ProductTrendEntry, RevenueLeakAnomaly, RFMChampion, SalesRecord,
    SeasonalityCurve, StoreMacroSummary, StorePerformance, WinsorizedValue,
)

_SUPPORTED_SUFFIXES = {".xlsx", ".csv"}
_ANONYMOUS_CUSTOMER = "SEM_CADASTRO"
# Venda com coluna de loja mapeada mas valor ausente NA linha (dado real messy) — não
# é descartada nem some da agregação, vira um pseudo-grupo estável (mesmo padrão de
# _ANONYMOUS_CUSTOMER para cliente ausente). Nunca cravado como nome de loja real.
_UNKNOWN_STORE = "LOJA_NAO_IDENTIFICADA"
# D3 — conversão dias -> "meses corridos" para medir a janela de histórico PRÓPRIA de
# uma loja (aproximação documentada: média de dias por mês do calendário gregoriano,
# não uma contagem de meses-calendário exata — suficiente para comparar contra
# `cold_start_min_months`, que é ele mesmo um limiar de referência, não uma fronteira
# de precisão de dia).
_AVG_DAYS_PER_MONTH = 30.44


def _read_raw(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str)
    return pd.read_excel(path, dtype=str, engine="openpyxl")


_SERIES_B_SHEETS = ("Estoque", "Clientes")


def load_named_sheets(path: Path) -> dict[str, pd.DataFrame]:
    """Lê as abas nomeadas da série B (Estoque, Clientes) quando existem — Vendas
    continua vindo de `load_sales_records`. Arquivo sem essas abas (CSV, pasta, ou
    .xlsx de aba única) simplesmente não alimenta os detectores de estoque/completude
    — nunca inventa dado ausente, nunca derruba a auditoria."""
    path = Path(path)
    if path.is_dir() or path.suffix.lower() != ".xlsx":
        return {}
    workbook = pd.ExcelFile(path, engine="openpyxl")
    return {
        name: pd.read_excel(path, sheet_name=name, dtype=str, engine="openpyxl")
        for name in _SERIES_B_SHEETS if name in workbook.sheet_names
    }


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
            entry_costs = (
                coerce_currency_series(raw[roles["cost"]])
                if "cost" in roles else pd.Series([None] * len(raw))
            )
            # Sem .astype(str): NaN de célula vazia precisa sobreviver como NaN (não
            # "nan" string) até o pd.isna() por linha abaixo — mesma armadilha do bug
            # real de cliente ausente.
            categories = raw[roles["category"]] if "category" in roles else pd.Series([None] * len(raw))
            stores = raw[roles["store"]] if "store" in roles else pd.Series([None] * len(raw))
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
            if pd.isna(products.iloc[i]):
                discarded_by_reason["produto_ausente"] = discarded_by_reason.get("produto_ausente", 0) + 1
                continue
            # Venda sem cliente identificado (walk-in) é dado real, não sujeira — a
            # venda existe e conta na receita. Vira um pseudo-cliente estável em vez de
            # descartada, para não perder receita real do produto/período.
            customer = _ANONYMOUS_CUSTOMER if pd.isna(customers.iloc[i]) else customers.iloc[i]
            qty = quantities.iloc[i]
            cost = entry_costs.iloc[i]
            cat = categories.iloc[i]
            store = stores.iloc[i]
            # Unidade econômica correta da linha é preço × quantidade — não só o
            # preço unitário (bug real: uma devolução com qtd=-1 entrava como venda
            # POSITIVA de mesmo valor, porque quantity nunca era usada). Quantidade
            # ausente/não mapeada assume 1 (preserva o comportamento de todo arquivo
            # sem coluna de quantidade — nada muda pra eles). Isso também expõe erro
            # de digitação de quantidade (ex. qtd=99) para a poda de outlier abaixo —
            # nunca escala o erro em silêncio, só deixa visível pra ser podado.
            effective_qty = 1.0 if qty is None or pd.isna(qty) else float(qty)
            line_value = float(values.iloc[i]) * effective_qty
            records.append(SalesRecord(
                date=dates.iloc[i].to_pydatetime(),
                product=products.iloc[i],
                customer=customer,
                value=line_value,
                quantity=None if qty is None or pd.isna(qty) else float(qty),
                entry_cost=None if cost is None or pd.isna(cost) else float(cost),
                category=None if cat is None or pd.isna(cat) else str(cat),
                store=None if store is None or pd.isna(store) else str(store),
                source_file=file_path.name,
                source_row=i + 2,  # +1 para 1-indexado, +1 para o cabeçalho
            ))

    summary = CleaningSummary(
        rows_read=rows_read, rows_accepted=len(records),
        rows_discarded_by_reason=discarded_by_reason, files_skipped=files_skipped,
    )
    return records, summary


def winsorize_outliers(
    records: list[SalesRecord], thresholds: AuditThresholdsConfig,
) -> tuple[list[SalesRecord], list[WinsorizedValue]]:
    """Poda estatística de outlier de valor — valor > `outlier_median_ratio`× a
    MEDIANA do PRÓPRIO produto = erro clássico de digitação (dígito a mais no preço,
    ou quantidade errada que infla o total da linha); não pode inflar faturamento nem
    contaminar médias/medianas a jusante.

    Razão-para-a-própria-mediana, não cerca de Tukey (Q3+k×IQR): testado contra o
    dado real, IQR por produto — mesmo com cerca "extrema" (3×) e amostra mínima alta
    — gerava dezenas de falsos positivos, porque produtos de ótica legitimamente têm
    preço BIMODAL sob o mesmo SKU (armação básica vs. premium no mesmo código,
    variação de ~2-11x observada) — Q1/Q3 fica instável com poucas vendas por
    produto. Mediana é robusta mesmo com poucas amostras (n=2 já basta) e a separação
    real é gigante: variância legítima máxima observada ~11x a mediana; os 2 erros de
    digitação reais da planilha estão a ~148x. `outlier_median_ratio=20` (default)
    fica confortavelmente no meio, sem colar na borda de nenhum dos dois lados.

    A razão é POR PRODUTO, nunca sobre a rede inteira: um produto legitimamente mais
    caro que a média da rede (categoria premium/sazonal) não é outlier de si mesmo —
    só é outlier relativo à sua PRÓPRIA distribuição de preço (bug pego pela própria
    fixture sintética: SOLAR-SEASONAL, ticket ~3x a mediana da rede, foi podado por
    engano quando a cerca era calculada globalmente).

    Nunca deleta a transação: produto, cliente e data continuam contando para
    frequência/recência; só a contribuição monetária é limitada ao teto estatístico.
    Poda só o teto superior — retorno negativo (estorno) é sinal válido, não erro de
    digitação. Toda poda é registrada para procedência (nunca silenciosa)."""
    by_product: dict[str, list[int]] = {}
    for idx, r in enumerate(records):
        by_product.setdefault(r.product, []).append(idx)

    winsorized: list[WinsorizedValue] = []
    adjusted = list(records)
    for product, indices in by_product.items():
        positive_values = pd.Series([records[i].value for i in indices if records[i].value > 0])
        if len(positive_values) < 2:
            continue
        median = positive_values.median()
        if median <= 0:
            continue
        upper_bound = float(median * thresholds.outlier_median_ratio)
        for i in indices:
            r = records[i]
            if r.value > upper_bound:
                winsorized.append(WinsorizedValue(
                    source_file=r.source_file, source_row=r.source_row, product=r.product,
                    original_value=r.value, capped_value=upper_bound,
                ))
                adjusted[i] = r.model_copy(update={"value": upper_bound})
    return adjusted, winsorized


def _records_to_frame(records: list[SalesRecord]) -> pd.DataFrame:
    return pd.DataFrame([{
        "date": pd.Timestamp(r.date), "product": r.product,
        "customer": r.customer, "value": r.value, "entry_cost": r.entry_cost,
        "category": r.category, "store": r.store,
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

    def _scan_yoy(series: pd.Series, scope: str, entity_id: str) -> None:
        """Desvio sobre o resíduo YoY (leave-one-out sobre todos os anos), não sobre a
        série crua — mata sazonalidade regular sem suprimir quedas reais. Mês-do-ano com
        menos de 2 outros-ano vira, no máximo, low_confidence/"medium" (nunca hard-flag
        sem base)."""
        series = series.sort_index()
        if len(series) < 3:
            return
        months = series.index.map(lambda p: p.month)
        residuals: dict = {}
        others_count: dict = {}
        for period, value in series.items():
            others = series[(months == period.month) & (series.index != period)]
            if len(others) == 0:
                continue
            residuals[period] = value - others.mean()
            others_count[period] = len(others)
        if len(residuals) < 2:
            return
        std_res = pd.Series(list(residuals.values())).std()
        if not std_res or std_res == 0 or pd.isna(std_res):
            return
        for period, residual in residuals.items():
            sigma = -residual / std_res
            if sigma >= thresholds.revenue_drop_sigma:
                n_others = others_count[period]
                low_confidence = n_others < 2
                severity = (
                    "medium" if low_confidence
                    else "high" if sigma >= thresholds.revenue_drop_sigma * 1.5 else "medium"
                )
                anomalies.append(RevenueLeakAnomaly(
                    scope=scope, entity_id=entity_id, period=str(period),
                    expected_value=float(series[period] - residual), actual_value=float(series[period]),
                    drop_sigma=float(sigma), severity=severity, low_confidence=low_confidence,
                ))

    total_series = df.groupby("period")["value"].sum()
    _scan(total_series, "total", "total")

    total_revenue = df["value"].sum()
    floor = total_revenue * thresholds.materiality_revenue_pct / 100.0
    for product, group in df.groupby("product"):
        if group["value"].sum() < floor:
            continue
        product_series = group.groupby("period")["value"].sum()
        _scan_yoy(product_series, "product", product)

    return anomalies


def detect_churn(df: pd.DataFrame, thresholds: AuditThresholdsConfig) -> list[ChurnFinding]:
    """Cliente com >= churn_min_purchases compras e cadência média M; sem comprar há
    mais que churn_cadence_multiplier x M -> churn invisível (nunca cancelou formalmente).
    Vendas sem cliente identificado (pseudo-cliente `_ANONYMOUS_CUSTOMER`) não são uma
    pessoa — excluídas, senão o volume agregado de vários clientes anônimos distorce a
    cadência de um cliente que não existe."""
    findings: list[ChurnFinding] = []
    global_max_date = df["date"].max()
    df = df[df["customer"] != _ANONYMOUS_CUSTOMER]

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


def detect_rfm_champions(df: pd.DataFrame, thresholds: AuditThresholdsConfig) -> list[RFMChampion]:
    """RFM adaptado a negócio de compra recorrente regular (ótica): Frequência e Valor
    ranqueiam normalmente em `rfm_bins` quantis — campeão exige topo nos dois. Recência
    crua NÃO discrimina aqui (dias-desde-a-última-compra reflete a fase do ciclo do
    cliente no corte dos dados, não engajamento — um cliente de ciclo longo cai "frio"
    só por ter ciclo longo). Em vez de quantil, recência vira um GATE de "ainda ativo":
    reaproveita o mesmo limiar do detector de churn (A3) sobre a cadência PRÓPRIA do
    cliente — régua vem do cliente, não da rede. Cliente com 1 única compra não tem
    cadência própria (sem base) e fica fora do gate. Pseudo-cliente `_ANONYMOUS_CUSTOMER`
    (vendas sem identificação) é excluído — não é uma pessoa, é a soma de vários
    walk-ins; contá-lo distorceria frequência/valor com volume que não é de ninguém."""
    df = df[df["customer"] != _ANONYMOUS_CUSTOMER]
    if df.empty:
        return []
    bins = thresholds.rfm_bins
    global_max_date = df["date"].max()

    grouped = df.groupby("customer").agg(
        first_purchase=("date", "min"), last_purchase=("date", "max"),
        frequency=("date", "nunique"), monetary=("value", "sum"),
    )
    if len(grouped) < bins:
        # Base de clientes menor que o nº de quantis — segmentar não tem sinal.
        return []
    grouped["recency_days"] = (global_max_date - grouped["last_purchase"]).dt.days

    has_cadence = grouped["frequency"] > 1
    span_days = (grouped["last_purchase"] - grouped["first_purchase"]).dt.days
    avg_cadence_days = pd.Series(float("nan"), index=grouped.index)
    avg_cadence_days[has_cadence] = span_days[has_cadence] / (grouped["frequency"][has_cadence] - 1)
    still_active = has_cadence & (
        grouped["recency_days"] <= avg_cadence_days * thresholds.churn_cadence_multiplier
    )

    def _quantile_score(values: pd.Series) -> pd.Series:
        # rank(method="first") desempata valores iguais -> qcut nunca quebra por bordas
        # de quantil duplicadas. Maior valor = maior score.
        ranks = values.rank(method="first")
        return pd.qcut(ranks, bins, labels=False) + 1

    grouped["recency_score"] = _quantile_score(-grouped["recency_days"])
    grouped["frequency_score"] = _quantile_score(grouped["frequency"])
    grouped["monetary_score"] = _quantile_score(grouped["monetary"])

    champions = grouped[
        still_active & (grouped["frequency_score"] == bins) & (grouped["monetary_score"] == bins)
    ]
    return [
        RFMChampion(
            customer_id=str(customer_id), recency_days=float(row["recency_days"]),
            frequency=int(row["frequency"]), monetary=float(row["monetary"]),
            recency_score=int(row["recency_score"]), frequency_score=int(row["frequency_score"]),
            monetary_score=int(row["monetary_score"]),
        )
        for customer_id, row in champions.iterrows()
    ]


def detect_contribution_margin(
    df: pd.DataFrame, thresholds: AuditThresholdsConfig,
) -> list[ContributionMarginAlert]:
    """Margem de contribuição por produto = preço médio − custo de entrada médio −
    variáveis (imposto+comissão+taxa, % configurável do preço). Produto com margem
    negativa dá prejuízo em cada venda, antes até de despesa fixa. Sem coluna de custo
    de entrada no arquivo de origem, não há como calcular — retorna vazio (nunca
    inventa custo). Estorno (valor <= 0, ver winsorize_outliers/sinal de quantidade)
    não é uma venda a um "preço" — é reversão de caixa; entrar na média de preço
    arrastaria o "preço médio" pra baixo por um motivo que não é preço."""
    if "entry_cost" not in df.columns:
        return []
    valid = df.dropna(subset=["entry_cost"])
    valid = valid[valid["value"] > 0]
    if valid.empty:
        return []

    grouped = valid.groupby("product").agg(
        avg_price=("value", "mean"), avg_entry_cost=("entry_cost", "mean"),
        sample_size=("value", "count"),
    )
    grouped["variable_cost"] = grouped["avg_price"] * thresholds.variable_cost_pct / 100.0
    grouped["contribution_margin"] = (
        grouped["avg_price"] - grouped["avg_entry_cost"] - grouped["variable_cost"]
    )
    negative = grouped[grouped["contribution_margin"] < 0]
    return [
        ContributionMarginAlert(
            product=str(product), avg_price=float(row["avg_price"]),
            avg_entry_cost=float(row["avg_entry_cost"]),
            variable_cost_pct=float(thresholds.variable_cost_pct),
            contribution_margin=float(row["contribution_margin"]),
            sample_size=int(row["sample_size"]),
        )
        for product, row in negative.iterrows()
    ]


def detect_store_performance(
    df: pd.DataFrame, thresholds: AuditThresholdsConfig,
) -> list[StorePerformance]:
    """D1 — P&L por loja: agrega a MESMA lógica de margem de contribuição de
    `detect_contribution_margin` (preço médio − custo de entrada médio −
    `variable_cost_pct`% do preço), agrupando por LOJA em vez de por produto — o
    groupby é sobre o que existir dinamicamente no dado, nunca uma lista fixa de
    lojas. `gross_revenue` soma TODO o valor de venda da loja (inclui estornos
    negativos — mesmo critério de `detect_revenue_leaks`); a margem de contribuição
    real só considera vendas com custo de entrada conhecido e valor > 0 (estorno não
    tem "preço", ver A1) — as duas métricas medem coisas diferentes de propósito, uma
    loja pode ter faturamento alto e margem real negativa ao mesmo tempo. Sem coluna
    de loja identificada no arquivo de origem, não há como segmentar — retorna vazio
    (nunca inventa loja).

    D3 — cold-start: `months_of_history` é calculado DINAMICAMENTE por loja
    (`max(date) − min(date)` das vendas DAQUELA loja, groupby, nunca um nome cravado)
    e comparado contra `thresholds.cold_start_min_months`. Loja com histórico curto
    demais recebe `has_sufficient_history=False` — continua no relatório com seus
    números reais (nunca removida, nunca escondida), só marcada para que o consumidor
    do relatório a trate como cenário assumido / dado insuficiente, não como fato tão
    confiável quanto uma loja madura."""
    if "store" not in df.columns or df["store"].isna().all():
        return []
    df = df.copy()
    df["store"] = df["store"].fillna(_UNKNOWN_STORE)

    revenue_by_store = df.groupby("store")["value"].sum()
    count_by_store = df.groupby("store").size()
    history_span_by_store = df.groupby("store")["date"].agg(["min", "max"])

    valid = df.dropna(subset=["entry_cost"]) if "entry_cost" in df.columns else df.iloc[0:0]
    valid = valid[valid["value"] > 0]

    entries: list[StorePerformance] = []
    for store in sorted(revenue_by_store.index):
        store_valid = valid[valid["store"] == store]
        margin_sample_size = len(store_valid)
        if margin_sample_size == 0:
            avg_price = 0.0
            avg_entry_cost = 0.0
            contribution_margin_avg = 0.0
        else:
            avg_price = float(store_valid["value"].mean())
            avg_entry_cost = float(store_valid["entry_cost"].mean())
            variable_cost = avg_price * thresholds.variable_cost_pct / 100.0
            contribution_margin_avg = avg_price - avg_entry_cost - variable_cost
        contribution_margin_total = contribution_margin_avg * margin_sample_size

        span_days = (history_span_by_store.loc[store, "max"] - history_span_by_store.loc[store, "min"]).days
        months_of_history = float(span_days) / _AVG_DAYS_PER_MONTH
        has_sufficient_history = months_of_history >= thresholds.cold_start_min_months

        entries.append(StorePerformance(
            store=str(store), gross_revenue=float(revenue_by_store[store]),
            revenue_sample_size=int(count_by_store[store]),
            avg_price=float(avg_price), avg_entry_cost=float(avg_entry_cost),
            variable_cost_pct=float(thresholds.variable_cost_pct),
            contribution_margin_avg=float(contribution_margin_avg),
            contribution_margin_total=float(contribution_margin_total),
            margin_sample_size=margin_sample_size,
            months_of_history=months_of_history,
            has_sufficient_history=has_sufficient_history,
        ))
    return entries


def build_store_macro_summary(
    store_performance: list[StorePerformance],
) -> StoreMacroSummary | None:
    """D1 — Resumo macro a partir do P&L por loja (dinâmico: nenhuma loja específica
    cravada, opera sobre o que `detect_store_performance` retornou). Ranking por
    faturamento bruto vs. ranking por margem de contribuição real — mesma lista de
    lojas, potencialmente ordens diferentes. `masked_amount` é o que o agregado
    saudável da rede MASCARA: soma, em módulo, da `contribution_margin_total` de cada
    loja com margem negativa — a rede fecha `network_contribution_margin_total`
    positivo somando o resultado de todas as lojas, mas isso já é o líquido depois de
    absorver o prejuízo das lojas negativas; `masked_amount` é quanto maior o
    resultado seria sem elas. Sem loja identificada, retorna None — nunca inventa
    ranking.

    D3 — cold-start: `revenue_rank`/`margin_rank`/`network_contribution_margin_total`
    incluem TODAS as lojas (cold-start inclusive — dinheiro que já entrou/saiu de
    caixa é fato, e não há motivo para esconder a loja do ranking). Mas
    `stores_with_negative_margin`/`masked_amount` são uma alegação interpretativa
    ("estas lojas estruturalmente mascaram o resultado saudável da rede") — rotular
    uma loja cold-start assim, com poucas semanas/meses de dado, confundiria ruído de
    amostra pequena com prejuízo estrutural; por isso essas duas métricas consideram
    só lojas com `has_sufficient_history=True`. Uma loja cold-start com margem
    negativa continua visível em `StorePerformance.contribution_margin_total` (fato
    bruto, nunca escondido) — só não entra nessa narrativa específica de
    "mascaramento estrutural"."""
    if not store_performance:
        return None
    revenue_rank = [s.store for s in sorted(store_performance, key=lambda s: -s.gross_revenue)]
    margin_rank = [
        s.store for s in sorted(store_performance, key=lambda s: -s.contribution_margin_total)
    ]
    negative = [
        s for s in store_performance
        if s.contribution_margin_total < 0 and s.has_sufficient_history
    ]
    masked_amount = float(sum(-s.contribution_margin_total for s in negative))
    network_contribution_margin_total = float(sum(s.contribution_margin_total for s in store_performance))
    return StoreMacroSummary(
        stores_with_negative_margin=sorted(s.store for s in negative),
        masked_amount=masked_amount,
        network_contribution_margin_total=network_contribution_margin_total,
        revenue_rank=revenue_rank, margin_rank=margin_rank,
        rank_differs=revenue_rank != margin_rank,
    )


def detect_latent_revenue(
    df: pd.DataFrame, thresholds: AuditThresholdsConfig,
) -> list[LatentRevenueFinding]:
    """Receita Latente / Attach: separa o FATO medido do CENÁRIO assumido.

    Base elegível = clientes que já compraram a âncora (`latent_revenue_anchor_category`,
    ex. lente de grau). Attach rate e ticket médio do complemento (`..._target_category`,
    ex. solar) são derivados do próprio histórico — régua do cliente. A taxa de conversão
    dos não-compradores NÃO é derivável (a loja nunca trabalhou esses clientes, não há
    histórico do que aconteceria) — é uma premissa de negócio explícita e ajustável
    (`latent_revenue_conversion_pct`), nunca apresentada como fato. Sem coluna de
    categoria no arquivo de origem, não há como segmentar — retorna vazio."""
    if "category" not in df.columns or df["category"].isna().all():
        return []
    df = df[df["customer"] != _ANONYMOUS_CUSTOMER]
    anchor = thresholds.latent_revenue_anchor_category
    target = thresholds.latent_revenue_target_category

    eligible = set(df.loc[df["category"] == anchor, "customer"].unique())
    if not eligible:
        return []
    target_buyers = set(df.loc[df["category"] == target, "customer"].unique())
    non_buyers = sorted(eligible - target_buyers)
    if not non_buyers:
        return []

    attach_rate_pct = 100.0 * len(eligible & target_buyers) / len(eligible)
    target_sales = df[df["category"] == target]
    avg_ticket = float(target_sales["value"].mean()) if len(target_sales) else 0.0
    conversion_pct = thresholds.latent_revenue_conversion_pct
    estimated = len(non_buyers) * conversion_pct / 100.0 * avg_ticket

    return [LatentRevenueFinding(
        anchor_category=anchor, target_category=target,
        eligible_customers=len(eligible), non_buyers_count=len(non_buyers),
        attach_rate_pct=float(attach_rate_pct), avg_ticket_target_category=avg_ticket,
        assumed_conversion_pct=float(conversion_pct),
        estimated_latent_revenue=float(estimated), non_buyer_customers=non_buyers,
    )]


def detect_dead_stock(
    estoque_df: pd.DataFrame | None, thresholds: AuditThresholdsConfig,
) -> list[DeadStockFinding]:
    """B4 — capital preso em SKUs sem movimento há >= `dead_stock_months` (contagem em
    meses-calendário, mesmo estilo do churn) contra a data de movimentação mais recente
    conhecida no PRÓPRIO estoque — nunca a data do sistema. Sem aba Estoque ou colunas
    reconhecíveis, retorna vazio — nunca inventa capital preso."""
    if estoque_df is None or estoque_df.empty:
        return []
    try:
        roles = infer_column_roles(
            estoque_df, role_keywords=_ESTOQUE_ROLE_KEYWORDS, required_roles=_ESTOQUE_REQUIRED_ROLES,
        )
    except ColumnMappingError:
        return []

    frame = pd.DataFrame({
        "sku": estoque_df[roles["sku"]].astype(str),
        "cost": coerce_currency_series(estoque_df[roles["cost"]]),
        "qty": coerce_currency_series(estoque_df[roles["qty_on_hand"]]),
        "last_movement": coerce_date_series(estoque_df[roles["last_movement"]]),
    }).dropna()
    if frame.empty:
        return []

    reference_date = frame["last_movement"].max()
    ref_ordinal = reference_date.year * 12 + reference_date.month
    frame["months_since"] = ref_ordinal - (
        frame["last_movement"].dt.year * 12 + frame["last_movement"].dt.month
    )
    frame["inventory_value"] = frame["qty"] * frame["cost"]

    total_inventory_value = float(frame["inventory_value"].sum())
    dead = frame[frame["months_since"] >= thresholds.dead_stock_months]
    if dead.empty:
        return []
    capital_frozen = float(dead["inventory_value"].sum())
    dead_stock_pct = capital_frozen / total_inventory_value * 100.0 if total_inventory_value else 0.0

    return [DeadStockFinding(
        dead_stock_months=thresholds.dead_stock_months, sku_count=len(dead),
        capital_frozen=capital_frozen, total_inventory_value=total_inventory_value,
        dead_stock_pct=float(dead_stock_pct), skus=sorted(dead["sku"].tolist()),
    )]


def detect_gmroi(
    vendas_df: pd.DataFrame, estoque_df: pd.DataFrame | None, thresholds: AuditThresholdsConfig,
) -> list[GmroiEntry]:
    """B2 — margem bruta realizada (Vendas) ÷ valor de estoque a custo (Estoque), por
    categoria. MEDE E REPORTA o que o dado diz — não há alvo esperado, os números da
    categoria são o que são. `avg_inventory_value` usa o snapshot atual do estoque como
    proxy de médio (sem série temporal de níveis de estoque, não há como calcular uma
    média histórica de verdade) — aproximação, não fingida como exata."""
    if estoque_df is None or estoque_df.empty:
        return []
    if "category" not in vendas_df.columns or vendas_df["category"].isna().all():
        return []
    try:
        roles = infer_column_roles(
            estoque_df, role_keywords=_ESTOQUE_ROLE_KEYWORDS, required_roles=_ESTOQUE_REQUIRED_ROLES,
        )
    except ColumnMappingError:
        return []
    if "category" not in roles:
        return []

    est_frame = pd.DataFrame({
        "category": estoque_df[roles["category"]].astype(str),
        "cost": coerce_currency_series(estoque_df[roles["cost"]]),
        "qty": coerce_currency_series(estoque_df[roles["qty_on_hand"]]),
    }).dropna()
    if est_frame.empty:
        return []
    inventory_by_category = (est_frame["qty"] * est_frame["cost"]).groupby(est_frame["category"]).sum()

    sales = vendas_df.dropna(subset=["category", "entry_cost"])
    margin_by_category = (sales["value"] - sales["entry_cost"]).groupby(sales["category"]).sum()
    count_by_category = sales.groupby("category").size()

    entries: list[GmroiEntry] = []
    for category, avg_inventory_value in sorted(inventory_by_category.items()):
        gross_margin = float(margin_by_category.get(category, 0.0))
        avg_inventory_value = float(avg_inventory_value)
        gmroi = gross_margin / avg_inventory_value if avg_inventory_value else None
        entries.append(GmroiEntry(
            category=category, gross_margin=gross_margin, avg_inventory_value=avg_inventory_value,
            gmroi=gmroi, sample_size=int(count_by_category.get(category, 0)),
        ))
    return entries


def build_cpf_canonical_map(clientes_df: pd.DataFrame | None) -> dict[str, str]:
    """D2 — Dedupe por CPF: dois cadastros `cliente_id` DIFERENTES (possivelmente em
    lojas diferentes) que compartilham o MESMO CPF na aba Clientes são a MESMA pessoa
    física — precisam contar como 1 identidade só em qualquer detector por-cliente
    (RFM, churn, receita latente, base de clientes, concentração se existir). O
    agrupamento é DINÂMICO sobre o que existir na aba Clientes — nunca um cliente_id
    específico cravado no código; funciona para qualquer par/trio que compartilhe CPF.

    CPF é normalizado (só dígitos) antes de agrupar, para que "123.456.789-00" e
    "12345678900" — mesmo documento, formatação diferente — colidam. Cliente sem CPF
    (vazio/ausente) ou sem cadastro na aba Clientes NUNCA é mesclado — preserva
    identidade própria (regra inegociável: um CPF vazio não é uma chave de
    agrupamento, é a ausência de uma).

    ID canônico do grupo = o menor `cliente_id` em ordem lexicográfica — escolha
    arbitrária mas determinística e estável (mesma entrada sempre produz o mesmo
    canônico), documentada aqui por não haver "certo" entre os membros do grupo.

    Retorna um dict {cliente_id_bruto -> cliente_id_canônico} contendo só os
    cliente_id que de fato pertencem a um grupo de >= 2 identidades (grupos
    singulares não entram no mapa — `dict.get(id, id)` já resolve identidade pra
    quem não está aqui). Sem aba Clientes ou sem coluna de documento identificável,
    retorna {} — nunca inventa dedupe."""
    if clientes_df is None or clientes_df.empty:
        return {}
    try:
        roles = infer_column_roles(
            clientes_df, role_keywords=_CLIENTES_ROLE_KEYWORDS, required_roles=_CLIENTES_REQUIRED_ROLES,
        )
    except ColumnMappingError:
        return {}
    if "document" not in roles:
        return {}

    ids_raw = clientes_df[roles["customer_id"]]
    docs_raw = clientes_df[roles["document"]]

    groups: dict[str, list[str]] = {}
    for cid_val, doc_val in zip(ids_raw, docs_raw):
        # pd.isna antes de qualquer .astype(str): célula vazia tem que continuar NaN
        # (nunca virar a string literal "nan") até esta checagem — mesma armadilha já
        # documentada em load_sales_records/build_cpf_canonical_map's siblings.
        if pd.isna(cid_val) or pd.isna(doc_val):
            continue
        cid = str(cid_val).strip()
        doc_digits = re.sub(r"\D", "", str(doc_val))
        if not cid or not doc_digits:
            continue
        groups.setdefault(doc_digits, []).append(cid)

    canonical_map: dict[str, str] = {}
    for members in groups.values():
        unique_members = sorted(set(members))
        if len(unique_members) < 2:
            continue
        canonical = unique_members[0]
        for member in unique_members:
            canonical_map[member] = canonical
    return canonical_map


def detect_data_completeness(
    clientes_df: pd.DataFrame | None, thresholds: AuditThresholdsConfig,
) -> list[DataCompletenessFinding]:
    """A1 — Completude de cadastro (telefone + CPF), aba Clientes. Métrica POR CAMPO
    (não por cliente E): telefone e CPF podem faltar independentemente por cliente
    (dado real messy, cada campo com sua própria taxa de preenchimento) — média dos 2
    campos é mais honesta que exigir os 2 juntos, que penalizaria um cliente com só 1
    dado faltando tanto quanto um sem nenhum. Sem as 2 colunas de contato, não há como
    medir — retorna vazio."""
    if clientes_df is None or clientes_df.empty:
        return []
    try:
        roles = infer_column_roles(
            clientes_df, role_keywords=_CLIENTES_ROLE_KEYWORDS, required_roles=_CLIENTES_REQUIRED_ROLES,
        )
    except ColumnMappingError:
        return []
    if "phone" not in roles or "document" not in roles:
        return []

    total = len(clientes_df)

    def _filled_pct(series: pd.Series) -> float:
        filled = series.notna() & (series.astype(str).str.strip() != "")
        return 100.0 * filled.sum() / total

    phone_pct = _filled_pct(clientes_df[roles["phone"]])
    document_pct = _filled_pct(clientes_df[roles["document"]])
    completeness_pct = (phone_pct + document_pct) / 2.0

    return [DataCompletenessFinding(
        total_customers=total, phone_filled_pct=float(phone_pct),
        document_filled_pct=float(document_pct), completeness_pct=float(completeness_pct),
        contingency_triggered=completeness_pct < thresholds.contingency_completeness_pct,
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
    records, winsorized = winsorize_outliers(records, thresholds)
    if winsorized:
        cleaning = cleaning.model_copy(update={"values_winsorized": winsorized})

    named_sheets = load_named_sheets(path)

    # D2 — Dedupe por CPF: dois cliente_id que compartilham o mesmo CPF na aba
    # Clientes viram UMA identidade canônica ANTES de qualquer detector por-cliente
    # (RFM, churn, receita latente) rodar e antes da pseudonimização — assim
    # frequência/recência/valor agregam pela pessoa física real, não pelo cadastro
    # duplicado. Sem aba Clientes ou sem CPF, o mapa vem vazio e nada muda.
    customer_canonical_map = build_cpf_canonical_map(named_sheets.get("Clientes"))
    if customer_canonical_map:
        records = [
            r.model_copy(update={"customer": customer_canonical_map.get(r.customer, r.customer)})
            for r in records
        ]

    df = _records_to_frame(records)

    revenue_leaks = detect_revenue_leaks(df, thresholds)
    churn_findings = detect_churn(df, thresholds)
    product_trends = detect_product_trends(df, thresholds)
    seasonality = detect_seasonality(df, thresholds)
    rfm_champions = detect_rfm_champions(df, thresholds)
    contribution_margin_alerts = detect_contribution_margin(df, thresholds)
    latent_revenue = detect_latent_revenue(df, thresholds)
    store_performance = detect_store_performance(df, thresholds)
    store_macro_summary = build_store_macro_summary(store_performance)

    dead_stock = detect_dead_stock(named_sheets.get("Estoque"), thresholds)
    gmroi = detect_gmroi(df, named_sheets.get("Estoque"), thresholds)
    data_completeness = detect_data_completeness(named_sheets.get("Clientes"), thresholds)

    _, identity_map = anonymize_customers(records)

    for finding in churn_findings:
        finding.customer_id = identity_map.get(finding.customer_id, finding.customer_id)
    for leak in revenue_leaks:
        if leak.scope == "customer":
            leak.entity_id = identity_map.get(leak.entity_id, leak.entity_id)
    for champion in rfm_champions:
        champion.customer_id = identity_map.get(champion.customer_id, champion.customer_id)
    for finding in latent_revenue:
        finding.non_buyer_customers = [
            identity_map.get(c, c) for c in finding.non_buyer_customers
        ]

    period_start = str(df["date"].min().to_period("M")) if len(df) else ""
    period_end = str(df["date"].max().to_period("M")) if len(df) else ""

    report = ExecutiveAuditReport(
        period_start=period_start, period_end=period_end, cleaning=cleaning,
        thresholds=thresholds, revenue_leaks=revenue_leaks, churn_findings=churn_findings,
        product_trends=product_trends, seasonality=seasonality,
        rfm_champions=rfm_champions, contribution_margin_alerts=contribution_margin_alerts,
        latent_revenue=latent_revenue, dead_stock=dead_stock, gmroi=gmroi,
        data_completeness=data_completeness,
        store_performance=store_performance, store_macro_summary=store_macro_summary,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    if return_identity_map:
        return report, identity_map
    return report

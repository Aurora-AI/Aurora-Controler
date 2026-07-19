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

from kernel.robustness import benchmark_population as _benchmark_population_generic
from kernel.robustness import dedup_by_key
from kernel.tabular import records_to_frame as _records_to_frame_generic
from product_b.oracle.column_mapper import (
    _CLIENTES_REQUIRED_ROLES, _CLIENTES_ROLE_KEYWORDS, _ESTOQUE_REQUIRED_ROLES,
    _ESTOQUE_ROLE_KEYWORDS, _FINANCEIRO_REQUIRED_ROLES, _FINANCEIRO_ROLE_KEYWORDS,
    ColumnMappingError, DateAmbiguityError, coerce_currency_series, coerce_date_series,
    infer_column_roles,
)
from product_b.oracle.forensic_contracts import (
    ActionPlanItem, AuditThresholdsConfig, ChurnFinding, CleaningSummary,
    ContributionMarginAlert, CustomerConcentrationFinding, DataCompletenessFinding,
    DeadStockFinding, DiscardedAlarm, ExecutiveAuditReport, ExecutiveSummary, GmroiEntry,
    LatentRevenueFinding, ProductTrendEntry, RevenueLeakAnomaly, RFMChampion, SalesRecord,
    SalespersonPerformance, ServiceDecomposition, ServiceReconciliation, SeasonalityCurve,
    StoreMacroSummary, StorePerformance, WinsorizedValue,
)

_SUPPORTED_SUFFIXES = {".xlsx", ".csv"}
_ANONYMOUS_CUSTOMER = "SEM_CADASTRO"
# Venda com coluna de loja mapeada mas valor ausente NA linha (dado real messy) — não
# é descartada nem some da agregação, vira um pseudo-grupo estável (mesmo padrão de
# _ANONYMOUS_CUSTOMER para cliente ausente). Nunca cravado como nome de loja real.
_UNKNOWN_STORE = "LOJA_NAO_IDENTIFICADA"
# D4 — mesmo padrão de _UNKNOWN_STORE: venda com coluna de vendedor mapeada mas valor
# ausente NA linha vira um pseudo-grupo estável em vez de sumir da agregação. Nunca
# cravado como um vendedor_id real.
_UNKNOWN_SALESPERSON = "VENDEDOR_NAO_IDENTIFICADO"

# Registro ÚNICO de identidades sintéticas — nunca uma pessoa/loja/vendedor real,
# sempre um agregado de "não identificado" (walk-in sem cadastro, loja/vendedor sem
# valor mapeado na linha). Achado 3x nesta sessão ANTES de virar registro único
# (RFM e churn excluíam _ANONYMOUS_CUSTOMER cada um com seu próprio filtro inline; o
# SEV esqueceu de excluir _UNKNOWN_SALESPERSON da mediana de referência de volume) —
# a partir daqui, todo detector novo que precisar filtrar pseudo-entidade usa isto,
# nunca reinventa o filtro.
#
# Usado em dois papéis DIFERENTES, nunca confundidos:
#   (1) Alguns detectores excluem a pseudo-entidade da ANÁLISE INTEIRA — ela não é uma
#       unidade de análise válida (cliente anônimo não tem "comportamento de
#       cliente"). Ver detect_churn, detect_rfm_champions, detect_latent_revenue.
#   (2) Outros a mantêm VISÍVEL no relatório (fato bruto — a venda/receita é real) mas
#       a excluem de qualquer RÉGUA DE REFERÊNCIA cross-entidade (mediana, percentil,
#       quantil) usada pra avaliar as entidades reais. Ver `benchmark_population`.
_PSEUDO_ENTITY_IDS: frozenset[str] = frozenset({
    _ANONYMOUS_CUSTOMER, _UNKNOWN_STORE, _UNKNOWN_SALESPERSON,
})


def is_pseudo_entity(entity_id: str) -> bool:
    """True se `entity_id` é uma identidade sintética do registro único acima —
    nunca uma pessoa/loja/vendedor real."""
    return entity_id in _PSEUDO_ENTITY_IDS


def benchmark_population(entity_stats: dict[str, dict], predicate=lambda stats: True) -> list[dict]:
    """Filtra `entity_stats` (dict entity_id -> métricas) para uma régua de
    referência cross-entidade (mediana, percentil, quantil, etc.) — SEMPRE exclui
    pseudo-entidades via `is_pseudo_entity`, e aceita um `predicate` extra por cima
    (ex. "só quem tem tenure suficiente"). Uso OBRIGATÓRIO em qualquer detector que
    compute estatística de referência entre entidades reais — nunca um filtro ad-hoc
    inline de novo (é assim que a mesma classe de bug reaparece pela N-ésima vez).
    Mecanismo genérico agora mora no kernel (`kernel.robustness.benchmark_population`)
    — aqui só fornecemos o predicado de pseudo-entidade do domínio (Produto B)."""
    return _benchmark_population_generic(entity_stats, is_pseudo_entity, predicate=predicate)


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


_SERIES_B_SHEETS = ("Estoque", "Clientes", "Financeiro")


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
            salespersons = (
                raw[roles["salesperson"]] if "salesperson" in roles else pd.Series([None] * len(raw))
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
            salesperson = salespersons.iloc[i]
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
                salesperson=None if salesperson is None or pd.isna(salesperson) else str(salesperson),
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


# Schema da linha de venda usada pela guarda de dataset vazio — o mecanismo genérico
# (typed-empty-frame quando `records` está vazio) mora no kernel
# (`kernel.tabular.records_to_frame`); aqui só declaramos o schema do domínio.
_SALES_FRAME_SCHEMA: dict[str, str] = {
    "date": "datetime64[ns]", "product": "object", "customer": "object",
    "value": "float64", "entry_cost": "float64", "category": "object",
    "store": "object", "salesperson": "object",
}


def _records_to_frame(records: list[SalesRecord]) -> pd.DataFrame:
    return _records_to_frame_generic([{
        "date": pd.Timestamp(r.date), "product": r.product,
        "customer": r.customer, "value": r.value, "entry_cost": r.entry_cost,
        "category": r.category, "store": r.store, "salesperson": r.salesperson,
    } for r in records], _SALES_FRAME_SCHEMA)


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
                    seasonality_adjusted=True, confidence="low" if low_confidence else "high"
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
    Pseudo-cliente (ver `is_pseudo_entity`) não é uma pessoa — excluído, senão o volume
    agregado de vários clientes anônimos distorce a cadência de um cliente que não existe."""
    findings: list[ChurnFinding] = []
    global_max_date = df["date"].max()
    df = df[~df["customer"].isin(_PSEUDO_ENTITY_IDS)]

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

        last_period = last_purchase.to_period("M")
        global_period = global_max_date.to_period("M")
        months_silent = (
            (global_period.year * 12 + global_period.month)
            - (last_period.year * 12 + last_period.month)
        )

        if days_since_last > thresholds.churn_cadence_multiplier * avg_cadence_days and months_silent >= 3:
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
    if not periods:
        return []
    midpoint = periods[len(periods) // 2]

    def _growth_pct(values_before: float, values_after: float) -> float:
        if values_before == 0:
            return 0.0
        return (values_after - values_before) / values_before * 100.0

    stores_before = set(df[df["period"] < midpoint]["store"].unique())
    stores_after = set(df[df["period"] >= midpoint]["store"].unique())
    same_stores = list(stores_before.intersection(stores_after))
    same_stores_df = df[df["store"].isin(same_stores)]

    company_before = same_stores_df[same_stores_df["period"] < midpoint]["value"].sum()
    company_after = same_stores_df[same_stores_df["period"] >= midpoint]["value"].sum()
    company_growth_pct = _growth_pct(company_before, company_after)

    entries: list[ProductTrendEntry] = []
    for product, group in df.groupby("product"):
        before = group[group["period"] < midpoint]["value"].sum()
        after = group[group["period"] >= midpoint]["value"].sum()
        product_growth_pct = _growth_pct(before, after)

        decoupled = (company_growth_pct - product_growth_pct) > thresholds.trend_decoupling_pct and thresholds.trend_decoupling_pct > 0

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
    cadência própria (sem base) e fica fora do gate. Pseudo-cliente (ver
    `is_pseudo_entity`, vendas sem identificação) é excluído — não é uma pessoa, é a
    soma de vários walk-ins; contá-lo distorceria frequência/valor com volume que não
    é de ninguém.

    SVC — venda de serviço (`thresholds.service_category_label`) NÃO conta pra
    frequência/valor: RFM aqui é sobre comportamento de compra de PRODUTO. Cliente que
    só vem pra ajuste/reparo não vira "campeão" por isso — mistura duas coisas
    diferentes (relacionamento de manutenção vs. relacionamento de compra)."""
    df = df[~df["customer"].isin(_PSEUDO_ENTITY_IDS)]
    if "category" in df.columns and not df["category"].isna().all():
        df = df[df["category"] != thresholds.service_category_label]
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
    arrastaria o "preço médio" pra baixo por um motivo que não é preço.

    SVC — venda de serviço (`thresholds.service_category_label`) fica de fora: essa
    margem é sobre "ticket de PRODUTO"; serviço tem estrutura de custo diferente
    (mão de obra, não estoque) e já tem sua própria vista em
    `detect_service_decomposition` — misturar aqui poluiria o preço médio do produto
    de verdade com uma dimensão de negócio diferente."""
    if "entry_cost" not in df.columns:
        return []
    valid = df.dropna(subset=["entry_cost"])
    valid = valid[valid["value"] > 0]
    if "category" in valid.columns and not valid["category"].isna().all():
        valid = valid[valid["category"] != thresholds.service_category_label]
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


def detect_customer_concentration(
    df: pd.DataFrame, thresholds: AuditThresholdsConfig,
) -> list[CustomerConcentrationFinding]:
    """B7 — Concentração de cliente (risco de key-account): agrupa DINAMICAMENTE por
    (loja, cliente) — nunca uma lista fixa de lojas ou clientes, funciona para
    qualquer rede. `store_revenue` (denominador) é a MESMA soma de receita bruta usada
    em `detect_store_performance`/`StorePerformance.gross_revenue` — TODA venda da
    loja, estornos negativos inclusos, groupby sobre o que existir no dado (mesmo
    `df["store"].fillna(_UNKNOWN_STORE)` de D1). `customer_revenue` (numerador) é a
    soma de `value` de 1 cliente naquela loja. Sem coluna de loja identificada no
    arquivo de origem, não há como segmentar — retorna vazio, mesmo critério de
    `detect_store_performance`.

    Pseudo-cliente (`is_pseudo_entity`, walk-in sem cadastro — ver `_ANONYMOUS_CUSTOMER`
    no registro único `_PSEUDO_ENTITY_IDS`) NUNCA é contado como "um cliente" aqui: é a
    soma de vários passantes diferentes, não uma pessoa. Sem essa exclusão, ele
    facilmente pareceria concentrar boa parte da receita de uma loja — porque agrega
    MUITOS clientes reais diferentes sob 1 só rótulo — gerando um falso alarme de
    key-account que não é ninguém de verdade (mesma classe de bug já corrigida em
    churn/RFM/receita latente/SEV, agora resolvida na raiz via registro único). O
    pseudo-cliente É excluído do NUMERADOR (nunca aparece como `customer` de um
    achado); a loja pseudo (`_UNKNOWN_STORE`) continua sendo uma unidade de
    agrupamento válida no DENOMINADOR — mesmo tratamento que D1 já dá a ela (fato
    bruto de receita, nunca escondida)."""
    if "store" not in df.columns or df["store"].isna().all():
        return []
    df = df.copy()
    df["store"] = df["store"].fillna(_UNKNOWN_STORE)

    store_revenue = df.groupby("store")["value"].sum()

    customer_df = df[~df["customer"].isin(_PSEUDO_ENTITY_IDS)]
    if customer_df.empty:
        return []
    grouped = customer_df.groupby(["store", "customer"]).agg(
        customer_revenue=("value", "sum"), sample_size=("value", "count"),
    )

    findings: list[CustomerConcentrationFinding] = []
    for (store, customer), row in grouped.iterrows():
        revenue = float(store_revenue.get(store, 0.0))
        if revenue == 0:
            continue
        concentration_pct = 100.0 * float(row["customer_revenue"]) / revenue
        if concentration_pct >= thresholds.concentration_risk_pct:
            findings.append(CustomerConcentrationFinding(
                store=str(store), customer=str(customer),
                customer_revenue=float(row["customer_revenue"]), store_revenue=revenue,
                concentration_pct=float(concentration_pct), sample_size=int(row["sample_size"]),
            ))
    return sorted(findings, key=lambda f: -f.concentration_pct)


def detect_salesperson_performance(
    df: pd.DataFrame, thresholds: AuditThresholdsConfig,
) -> list[SalespersonPerformance]:
    """D4 — SEV (Sistema de Eficiência de Venda): agrupa DINAMICAMENTE por vendedor
    (groupby sobre o que existir no dado — nunca uma lista fixa de `vendedor_id`).
    Sem coluna de vendedor identificada no arquivo de origem, não há como segmentar —
    retorna vazio (nunca inventa vendedor), mesmo critério de
    `detect_store_performance` para loja.

    Duas asserções independentes, calculadas separadamente e nunca uma mascarando a
    outra (ver docstring completa em `SalespersonPerformance`):

    1. Captura de cliente: `capture_rate_pct` = % das vendas do vendedor com cliente
       identificado (exclui pseudo-cliente da contagem de "capturado", mas as vendas
       anônimas continuam em `sample_size`/`total_revenue` — é isso que deixa a
       captura baixa visível mesmo quando o vendedor converte bem). `low_capture_flag`
       é avaliado SEMPRE, sem gate de tenure nem de receita.

    2. Ramp-up: `days_since_first_sale` (primeira venda DAQUELE vendedor até a data
       mais recente conhecida na rede, `global_max_date` — mesmo estilo de
       `months_of_history` em D3, em dias). `has_sufficient_tenure` compara contra
       `thresholds.sev_ramp_min_days`. `low_volume_flag` só pode ser True quando
       `has_sufficient_tenure=True`: o piso de "volume baixo" é a MEDIANA de
       `sample_size` entre os PARES com tenure suficiente, via `benchmark_population`
       — que por sua vez SEMPRE exclui pseudo-entidade (`_UNKNOWN_SALESPERSON`, venda
       sem vendedor mapeado na linha). Bug real pego por QA review: sem essa exclusão,
       um pseudo-grupo volumoso (muitas vendas sem vendedor identificado) puxava a
       mediana pra cima/baixo e penalizava vendedor real por um motivo que não era o
       desempenho dele — mesma classe de bug já corrigida 2x antes para
       `_ANONYMOUS_CUSTOMER` (RFM, churn), agora resolvida na raiz via registro único.
       Sem nenhum par com tenure suficiente, não há benchmark — ninguém é marcado
       (nunca inventa piso sem base)."""
    if "salesperson" not in df.columns or df["salesperson"].isna().all():
        return []
    df = df.copy()
    df["salesperson"] = df["salesperson"].fillna(_UNKNOWN_SALESPERSON)
    global_max_date = df["date"].max()

    revenue_by_sp = df.groupby("salesperson")["value"].sum()
    count_by_sp = df.groupby("salesperson").size()
    captured_by_sp = df[~df["customer"].isin(_PSEUDO_ENTITY_IDS)].groupby("salesperson").size()
    first_sale_by_sp = df.groupby("salesperson")["date"].min()

    raw: dict[str, dict] = {}
    for sp in sorted(count_by_sp.index):
        n = int(count_by_sp[sp])
        captured = int(captured_by_sp.get(sp, 0))
        capture_rate_pct = 100.0 * captured / n if n else 0.0
        days_since_first_sale = int((global_max_date - first_sale_by_sp[sp]).days)
        has_sufficient_tenure = days_since_first_sale >= thresholds.sev_ramp_min_days
        raw[sp] = {
            "total_revenue": float(revenue_by_sp[sp]),
            "sample_size": n,
            "capture_rate_pct": capture_rate_pct,
            "low_capture_flag": capture_rate_pct < thresholds.sev_min_capture_pct,
            "days_since_first_sale": days_since_first_sale,
            "has_sufficient_tenure": has_sufficient_tenure,
        }

    tenured_population = benchmark_population(raw, predicate=lambda v: v["has_sufficient_tenure"])
    tenured_sample_sizes = [v["sample_size"] for v in tenured_population]
    median_sample_size = (
        float(pd.Series(tenured_sample_sizes).median()) if tenured_sample_sizes else None
    )

    entries: list[SalespersonPerformance] = []
    for sp, stats in raw.items():
        low_volume_flag = bool(
            stats["has_sufficient_tenure"]
            and median_sample_size is not None
            and stats["sample_size"] < median_sample_size
        )
        entries.append(SalespersonPerformance(
            salesperson=str(sp), total_revenue=stats["total_revenue"],
            sample_size=stats["sample_size"], capture_rate_pct=float(stats["capture_rate_pct"]),
            low_capture_flag=bool(stats["low_capture_flag"]),
            days_since_first_sale=stats["days_since_first_sale"],
            has_sufficient_tenure=bool(stats["has_sufficient_tenure"]),
            low_volume_flag=low_volume_flag,
        ))
    return entries


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
    df = df[~df["customer"].isin(_PSEUDO_ENTITY_IDS)]
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
    all_below_1 = True
    for category, avg_inventory_value in sorted(inventory_by_category.items()):
        if category.lower() == "servico":
            continue
        gross_margin = float(margin_by_category.get(category, 0.0))
        avg_inventory_value = float(avg_inventory_value)
        gmroi = gross_margin / avg_inventory_value if avg_inventory_value else None
        
        if gmroi is not None and gmroi >= 1.0:
            all_below_1 = False
            
        entries.append(GmroiEntry(
            category=category, gross_margin=gross_margin, avg_inventory_value=avg_inventory_value,
            gmroi=gmroi, sample_size=int(count_by_category.get(category, 0)),
            is_directional_only=False
        ))
        
    if all_below_1 and entries:
        for e in entries:
            e.is_directional_only = True
            
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

    # pd.isna antes de qualquer .astype(str): célula vazia tem que continuar NaN
    # (nunca virar a string literal "nan") até esta checagem — mesma armadilha já
    # documentada em load_sales_records/build_cpf_canonical_map's siblings. Kernel
    # não sabe de pandas/NaN, então o filtro fica aqui; o agrupamento em si (mesmo
    # documento normalizado = mesma pessoa) é o mecanismo genérico
    # `kernel.robustness.dedup_by_key`, com CPF como a chave e o domínio (Produto B)
    # fornecendo só o normalizador (só dígitos).
    pairs = [
        (str(cid_val).strip(), str(doc_val))
        for cid_val, doc_val in zip(ids_raw, docs_raw)
        if not pd.isna(cid_val) and not pd.isna(doc_val)
    ]
    ids = [cid for cid, _ in pairs]
    docs = [doc for _, doc in pairs]
    return dedup_by_key(ids, docs, key_normalizer=lambda d: re.sub(r"\D", "", d))


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


def detect_service_decomposition(
    df: pd.DataFrame, thresholds: AuditThresholdsConfig,
) -> list[ServiceDecomposition]:
    """SVC — decompõe cada loja em produto × serviço, usando a MESMA fórmula de
    margem de contribuição de `detect_store_performance`/`detect_contribution_margin`
    (preço médio − custo médio − `variable_cost_pct`% do preço, só sobre vendas com
    custo de entrada CONHECIDO e valor > 0 — nunca inventa custo de linha sem
    entry_cost, mesmo critério de todo o resto do motor). Sem essa consistência de
    fórmula, `product_margin + service_margin` não bateria com o
    `contribution_margin_total` blendado de D1 pra mesma loja — dois números
    diferentes de "a mesma coisa" sem explicação é exatamente o tipo de furo que essa
    auditoria existe pra fechar, não pra abrir.

    Categoria de serviço (`thresholds.service_category_label`) fica de fora do GMROI/
    ticket de produto/RFM de produto (ver `detect_gmroi`, `detect_contribution_margin`,
    `detect_rfm_champions`) — aqui é onde ela finalmente ganha voz própria.

    `masks_negative_product_margin` = margem de produto NEGATIVA mas margem total
    (produto+serviço) POSITIVA — serviço mascarando produto quebrado. Uma loja assim
    não deve ser declarada saudável só porque o total fechou no azul.

    `follow_on_cac_effect` = receita de PRODUTO (não-serviço) de clientes cuja
    PRIMEIRA venda NAQUELA loja foi um serviço — efeito de aquisição via serviço que
    depois converteu em produto. Pseudo-cliente (`is_pseudo_entity`) nunca conta: não
    é uma pessoa, não tem uma "primeira venda" que signifique alguma coisa."""
    if "store" not in df.columns or df["store"].isna().all():
        return []
    if "category" not in df.columns or df["category"].isna().all():
        return []
    df = df.copy()
    df["store"] = df["store"].fillna(_UNKNOWN_STORE)
    service_label = thresholds.service_category_label
    # Sem coluna de custo de entrada no arquivo de origem, não há como calcular margem
    # (nunca inventa custo) — mesmo guard que `detect_store_performance` já aplica via
    # `"entry_cost" in df.columns else df.iloc[0:0]`. Sem isso, `.dropna(subset=[...])`
    # sobre uma coluna inexistente estoura KeyError em vez de degradar pra 0.0.
    has_entry_cost = "entry_cost" in df.columns

    def _margin_total(rows: pd.DataFrame) -> float:
        if not has_entry_cost:
            return 0.0
        valid = rows.dropna(subset=["entry_cost"])
        valid = valid[valid["value"] > 0]
        if valid.empty:
            return 0.0
        avg_price = valid["value"].mean()
        avg_cost = valid["entry_cost"].mean()
        variable_cost = avg_price * thresholds.variable_cost_pct / 100.0
        return float((avg_price - avg_cost - variable_cost) * len(valid))

    entries: list[ServiceDecomposition] = []
    for store, group in df.groupby("store"):
        is_service = group["category"] == service_label
        product_margin = _margin_total(group[~is_service])
        service_margin = _margin_total(group[is_service])
        total_margin = product_margin + service_margin
        masks = product_margin < 0 and total_margin > 0

        real_customers = group[~group["customer"].isin(_PSEUDO_ENTITY_IDS)]
        follow_on_cac_effect = 0.0
        if not real_customers.empty:
            # kind="stable" preserva a ordem original da linha em empates de mesma
            # data (sem granularidade de horário, duas vendas no mesmo dia não têm
            # uma ordem real conhecida) — sem isso, o quicksort default do pandas não
            # é estável e "primeira categoria" viraria não-determinístico em empate,
            # violando a reprodutibilidade que todo o motor promete.
            first_category = (
                real_customers.sort_values("date", kind="stable")
                .groupby("customer")["category"].first()
            )
            service_first = set(first_category[first_category == service_label].index)
            if service_first:
                follow_on_rows = real_customers[
                    real_customers["customer"].isin(service_first)
                    & (real_customers["category"] != service_label)
                ]
                follow_on_cac_effect = float(follow_on_rows["value"].sum())

        entries.append(ServiceDecomposition(
            store=str(store), product_margin=product_margin, service_margin=service_margin,
            total_margin=total_margin, masks_negative_product_margin=masks,
            follow_on_cac_effect=follow_on_cac_effect,
        ))
    return entries


def detect_service_reconciliation(
    vendas_df: pd.DataFrame, financeiro_df: pd.DataFrame | None, thresholds: AuditThresholdsConfig,
) -> list[ServiceReconciliation]:
    """SVC5 — Reconciliação Financeiro × Vendas de serviço: a aba Financeiro declara
    `receita_servicos` por (loja, mês); comparado contra a soma transacional real de
    linhas de serviço em Vendas no MESMO (loja, mês). Gap acima de
    `thresholds.service_reconciliation_gap_tolerance` vira achado — quando as duas
    fontes batem (mesma origem, registradas em 2 lugares diferentes), batem ao
    CENTAVO; não existe "quase bateu" genuíno, então a tolerância só cobre
    arredondamento, nunca disfarça um gap real. Sem aba Financeiro, sem coluna de
    loja em Vendas, ou sem categoria, não há como reconciliar — retorna vazio."""
    if financeiro_df is None or financeiro_df.empty:
        return []
    if "store" not in vendas_df.columns or vendas_df["store"].isna().all():
        return []
    if "category" not in vendas_df.columns or vendas_df["category"].isna().all():
        return []
    try:
        roles = infer_column_roles(
            financeiro_df, role_keywords=_FINANCEIRO_ROLE_KEYWORDS,
            required_roles=_FINANCEIRO_REQUIRED_ROLES,
        )
    except ColumnMappingError:
        return []

    service_label = thresholds.service_category_label
    df = vendas_df.copy()
    df["store"] = df["store"].fillna(_UNKNOWN_STORE)
    df["period"] = df["date"].dt.to_period("M").astype(str)
    transactional = df[df["category"] == service_label].groupby(["store", "period"])["value"].sum()

    fin = pd.DataFrame({
        "store": financeiro_df[roles["store"]].astype(str),
        "period": financeiro_df[roles["period"]].astype(str).str.strip(),
        "declared": coerce_currency_series(financeiro_df[roles["service_revenue"]]),
    }).dropna(subset=["declared"])

    entries: list[ServiceReconciliation] = []
    for _, row in fin.iterrows():
        store, period = row["store"], row["period"]
        declared = float(row["declared"])
        actual = float(transactional.get((store, period), 0.0))
        gap = declared - actual
        entries.append(ServiceReconciliation(
            store=store, period=period, financial_declared_revenue=declared,
            sales_transactional_revenue=actual, gap=gap,
            has_gap=abs(gap) > thresholds.service_reconciliation_gap_tolerance,
        ))
    return sorted(entries, key=lambda e: -abs(e.gap))


def build_executive_summary(
    contribution_margin_alerts: list[ContributionMarginAlert],
    dead_stock: list[DeadStockFinding],
    churn_findings: list[ChurnFinding],
    salesperson_performance: list[SalespersonPerformance],
    store_performance: list[StorePerformance],
    thresholds: AuditThresholdsConfig,
) -> ExecutiveSummary:
    """ES — Sumário executivo: agrega os outputs JÁ CALCULADOS pelos detectores acima
    em três totais de natureza contábil diferente (nunca somados entre si), mais os
    alarmes descartados e o plano de ação. Função pura, sem novo acesso a `df` — só
    recombina o que os detectores já retornaram, mesma filosofia de
    `build_store_macro_summary`.

    `total_operational_loss`: soma de |contribution_margin| de todo item em
    `contribution_margin_alerts` (a lista já só contém margem < 0, ver
    `detect_contribution_margin`). Não soma com `service_decomposition` (evitaria
    dupla contagem). Não exclui promoção (sem sinal no dado) — rotular como "a
    confirmar" é responsabilidade de quem exibe este campo, não deste cálculo.

    `total_capital_frozen`: `dead_stock[0].capital_frozen` se houver achado —
    `detect_dead_stock` estruturalmente nunca retorna mais que 1 item (sempre soma a
    rede inteira), então não há double-count possível aqui.

    `total_ltv_risk`: soma de `historical_annual_value` de todo `churn_findings`.

    `discarded_alarms`: só as duas categorias que o motor genuinamente checa hoje —
    vendedor em rampa (`has_sufficient_tenure=False`) e loja cold-start
    (`has_sufficient_history=False`). "Queda sazonal descartada" fica de fora: o
    motor de vazamento de receita não expõe candidatos que ficaram abaixo do limiar
    de sazonalidade, só os que viraram anomalia — ver
    docs/superpowers/specs/2026-07-17-laudo-executive-summary-e-frontend-drilldown-design.md,
    seção 4.3.

    `action_plan`: até 3 itens fixos (operacional/capital/LTV), cada um só aparece se
    o total correspondente for > 0, ordenados por tier ascendente e R$ descendente
    dentro do tier. Receita latente nunca entra aqui (é cenário, não fato) — por
    isso esta função nem recebe `latent_revenue` como parâmetro."""
    total_operational_loss = float(
        sum(abs(a.contribution_margin) for a in contribution_margin_alerts)
    )
    total_capital_frozen = float(dead_stock[0].capital_frozen) if dead_stock else 0.0
    # Piso em 0 por cliente antes de somar: um cliente com valor histórico líquido
    # negativo (estornos pesados) nunca deve cancelar o risco real de outro cliente
    # churnado com valor positivo — cada achado é avaliado isoladamente, nunca
    # mascarado por outro (mesmo princípio de SEV/D3/D4 no resto do arquivo).
    total_ltv_risk = float(sum(max(0.0, c.historical_annual_value) for c in churn_findings))

    discarded_alarms: list[DiscardedAlarm] = []
    for sp in salesperson_performance:
        if not sp.has_sufficient_tenure:
            discarded_alarms.append(DiscardedAlarm(
                category="salesperson_ramp", entity_id=sp.salesperson,
                reason=(
                    f"Vendedor em rampa há {sp.days_since_first_sale} dias "
                    f"(mínimo de maturidade: {thresholds.sev_ramp_min_days:.1f} dias) — "
                    "volume baixo não é penalizado."
                ),
            ))
    for s in store_performance:
        if not s.has_sufficient_history:
            discarded_alarms.append(DiscardedAlarm(
                category="store_cold_start", entity_id=s.store,
                reason=(
                    f"Loja com {s.months_of_history:.1f} meses de histórico "
                    f"(mínimo: {thresholds.cold_start_min_months:.1f} meses) — dado "
                    "insuficiente para tratar suas métricas com a mesma confiança de "
                    "uma loja madura."
                ),
            ))

    action_plan: list[ActionPlanItem] = []
    if total_operational_loss > 0:
        action_plan.append(ActionPlanItem(
            id="act-operational", category="margem_produto",
            title="Estancar Sangria Operacional",
            description=(
                "SKUs vendendo abaixo da margem de contribuição — ajustar "
                "precificação ou descontinuar. Pode incluir promoção intencional, "
                "a confirmar."
            ),
            impact_brl=total_operational_loss, nature="operational", tier=1,
        ))
    if total_capital_frozen > 0:
        action_plan.append(ActionPlanItem(
            id="act-capital", category="estoque",
            title="Liquidar Dinheiro Parado",
            description=(
                "Capital travado em estoque sem movimento — requer outlet ou "
                "transferência entre lojas."
            ),
            impact_brl=total_capital_frozen, nature="capital", tier=2,
        ))
    if total_ltv_risk > 0:
        action_plan.append(ActionPlanItem(
            id="act-ltv", category="churn",
            title="Mitigar Evasão Silenciosa (Churn)",
            description=(
                "Clientes recorrentes que sumiram além do ciclo de compra esperado — "
                "ativação via CRM prioritária."
            ),
            impact_brl=total_ltv_risk, nature="ltv_risk", tier=3,
        ))
    # Nota: com o mapeamento fixo atual (no máximo 1 item por tier), o desempate por
    # -impact_brl nunca é exercitado — o sort existe como salvaguarda caso um tier
    # futuro passe a ter mais de um item, não é código morto.
    action_plan.sort(key=lambda item: (item.tier, -item.impact_brl))

    return ExecutiveSummary(
        total_operational_loss=total_operational_loss,
        total_capital_frozen=total_capital_frozen,
        total_ltv_risk=total_ltv_risk,
        discarded_alarms=discarded_alarms,
        action_plan=action_plan,
    )


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
    customer_concentration = detect_customer_concentration(df, thresholds)
    salesperson_performance = detect_salesperson_performance(df, thresholds)

    dead_stock = detect_dead_stock(named_sheets.get("Estoque"), thresholds)
    gmroi = detect_gmroi(df, named_sheets.get("Estoque"), thresholds)
    data_completeness = detect_data_completeness(named_sheets.get("Clientes"), thresholds)

    service_decomposition = detect_service_decomposition(df, thresholds)
    service_reconciliation = detect_service_reconciliation(df, named_sheets.get("Financeiro"), thresholds)

    executive_summary = build_executive_summary(
        contribution_margin_alerts=contribution_margin_alerts,
        dead_stock=dead_stock,
        churn_findings=churn_findings,
        salesperson_performance=salesperson_performance,
        store_performance=store_performance,
        thresholds=thresholds,
    )

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
    for finding in customer_concentration:
        finding.customer = identity_map.get(finding.customer, finding.customer)

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
        customer_concentration=customer_concentration, salesperson_performance=salesperson_performance,
        service_decomposition=service_decomposition, service_reconciliation=service_reconciliation,
        executive_summary=executive_summary,
        generated_at=datetime.now(timezone.utc).isoformat()
    )

    if return_identity_map:
        return report, identity_map
    return report

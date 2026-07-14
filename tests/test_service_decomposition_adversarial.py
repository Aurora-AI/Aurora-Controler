"""
Verificação adversarial — Bloco SVC, `detect_service_decomposition`.

Escopo: os 4 pontos do pedido de revisão crítica.

1. `product_margin + service_margin` tem que bater com `contribution_margin_total`
   que `detect_store_performance` já calcula pra MESMA loja/df/thresholds (mesma
   fórmula: preço médio − custo médio − variable_cost_pct% do preço, só sobre vendas
   com entry_cost conhecido e valor > 0). Comparado contra loja(s) real(is) do fixture
   E contra um dataset sintético com mix produto/serviço (pra provar que a igualdade
   não é um acidente do dado real ter pouco serviço).
2. `masks_negative_product_margin` == (product_margin < 0 AND total_margin > 0),
   nem mais solto nem mais restrito — testado com caso sintético construído (o dado
   real não tem nenhuma loja "total positivo, produto negativo" hoje — a mais
   próxima, L7-Oeste, tem total NEGATIVO; ver teste de regressão dedicado abaixo) e
   com os limites exatos da condição (total == 0 não conta, produto == 0 não conta).
3. `follow_on_cac_effect` = receita de linhas NÃO-serviço de clientes cuja PRIMEIRA
   venda NAQUELA loja foi serviço; pseudo-cliente nunca conta como cliente aqui.
4. `thresholds.service_category_label` e `thresholds.variable_cost_pct` — nenhum
   literal mágico dentro da função (verificado trocando os dois por valores não-
   default e confirmando que o resultado muda de acordo).

Regras seguidas: nenhum nome de loja específico vira caso especial na lógica de
produção (as fixtures sintéticas abaixo usam nomes de loja arbitrários, o motor
opera sobre o que existir dinamicamente no df); nenhum código de produção lê a aba
Gabarito (não aplicável aqui — este arquivo não abre o .xlsx via Gabarito em nenhum
teste).
"""
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from oracle.commercial_auditor import (
    _ANONYMOUS_CUSTOMER, _records_to_frame, detect_service_decomposition,
    detect_store_performance, run_audit,
)
from oracle.forensic_contracts import AuditThresholdsConfig, SalesRecord

_FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


def _rec(date, customer, category, value, entry_cost, store, product="P1"):
    return SalesRecord(
        date=date, product=product, customer=customer, value=value,
        entry_cost=entry_cost, category=category, store=store, salesperson=None,
        source_file="synthetic", source_row=1,
    )


# ---------------------------------------------------------------------------
# 1. Consistência de fórmula: product_margin + service_margin == contribution_margin_total
# ---------------------------------------------------------------------------

def test_margin_sum_matches_store_performance_on_real_fixture_for_every_store():
    """Regressão contra o dado real: para TODAS as lojas do fixture (não uma loja
    escolhida a dedo), product_margin + service_margin bate com
    contribution_margin_total de detect_store_performance, mesmo df, mesmos
    thresholds."""
    th = AuditThresholdsConfig()
    records, _cleaning = __import__(
        "oracle.commercial_auditor", fromlist=["load_sales_records"]
    ).load_sales_records(_FIXTURE)
    df = _records_to_frame(records)

    store_perf = {s.store: s for s in detect_store_performance(df, th)}
    decomposition = detect_service_decomposition(df, th)
    assert len(decomposition) == len(store_perf) and len(decomposition) > 0

    for entry in decomposition:
        expected = store_perf[entry.store].contribution_margin_total
        actual = entry.product_margin + entry.service_margin
        assert actual == pytest.approx(expected, abs=0.01), (
            f"{entry.store}: contribution_margin_total={expected} != "
            f"product_margin+service_margin={actual}"
        )
        # total_margin é literalmente a mesma soma — não um terceiro cálculo
        # independente que poderia divergir dos outros dois.
        assert entry.total_margin == pytest.approx(
            entry.product_margin + entry.service_margin, abs=1e-9
        )


def test_margin_sum_matches_store_performance_on_synthetic_mixed_store():
    """Mesma checagem, mas num dataset sintético onde produto e serviço têm peso
    comparável (o fixture real tem pouquíssima venda de serviço) — prova que a
    igualdade é uma propriedade da fórmula, não um acidente de proporção de dado."""
    th = AuditThresholdsConfig()
    records = []
    base = dt.datetime(2024, 1, 1)
    # 12 vendas de produto, preço/custo variados.
    for i in range(12):
        records.append(_rec(
            base + dt.timedelta(days=i), f"PC{i}", "produto",
            value=300.0 + i * 10, entry_cost=150.0 + i * 3, store="LOJA-MIX",
        ))
    # 12 vendas de serviço, preço/custo variados — massa comparável ao produto.
    for i in range(12):
        records.append(_rec(
            base + dt.timedelta(days=100 + i), f"SC{i}", "servico",
            value=250.0 + i * 7, entry_cost=80.0 + i * 2, store="LOJA-MIX",
        ))
    df = _records_to_frame(records)

    store_perf = {s.store: s for s in detect_store_performance(df, th)}
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-MIX"]
    expected = store_perf["LOJA-MIX"].contribution_margin_total
    actual = entry.product_margin + entry.service_margin
    assert actual == pytest.approx(expected, abs=0.01)
    # ambos os lados têm massa real — não é uma igualdade trivial 0 == 0.
    assert entry.product_margin != 0.0
    assert entry.service_margin != 0.0


def test_margin_sum_matches_even_with_rows_missing_entry_cost_or_nonpositive_value():
    """A mesma igualdade precisa sobreviver a linhas "sujas" (sem custo de entrada,
    ou estorno com valor <= 0) — ambos os detectores devem excluí-las do MESMO jeito
    (dropna(entry_cost) então value > 0), não só quando o dado já está limpo."""
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 2, 1)
    records = [
        _rec(base, "P1", "produto", value=400.0, entry_cost=200.0, store="LOJA-SUJA"),
        _rec(base + dt.timedelta(days=1), "P2", "produto", value=350.0, entry_cost=None, store="LOJA-SUJA"),
        _rec(base + dt.timedelta(days=2), "P3", "produto", value=-80.0, entry_cost=40.0, store="LOJA-SUJA"),
        _rec(base + dt.timedelta(days=3), "S1", "servico", value=500.0, entry_cost=100.0, store="LOJA-SUJA"),
        _rec(base + dt.timedelta(days=4), "S2", "servico", value=450.0, entry_cost=None, store="LOJA-SUJA"),
    ]
    df = _records_to_frame(records)
    store_perf = {s.store: s for s in detect_store_performance(df, th)}
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-SUJA"]
    expected = store_perf["LOJA-SUJA"].contribution_margin_total
    actual = entry.product_margin + entry.service_margin
    assert actual == pytest.approx(expected, abs=0.01)
    # confirma que a linha suja realmente foi excluída (2 vendas válidas de produto:
    # P1 tem custo e valor > 0, P2 sem custo, P3 valor <= 0 -> só P1 conta).
    assert store_perf["LOJA-SUJA"].margin_sample_size == 2  # P1 (produto) + S1 (serviço)


# ---------------------------------------------------------------------------
# 2. masks_negative_product_margin — caso sintético mascarado + contraste saudável
# ---------------------------------------------------------------------------

def test_masks_negative_product_margin_true_when_service_covers_product_loss():
    """Caso SINTÉTICO central deste item: produto com margem clara e substancialmente
    negativa; serviço com margem positiva grande o bastante para virar o total da
    loja positivo. O dado real (consultoria_real_test.xlsx) não tem nenhuma loja
    assim hoje — por isso este caso é construído aqui, não extraído do fixture."""
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    records = []
    # Produto: preço médio 100, custo médio 250 -> margem por venda bem negativa
    # (100 - 250 - 15%*100 = -165/venda), 10 vendas -> produto ~ -1650.
    for i in range(10):
        records.append(_rec(
            base + dt.timedelta(days=i), f"PRODCUST{i}", "produto",
            value=100.0, entry_cost=250.0, store="LOJA-MASCARADA",
        ))
    # Serviço: preço médio 600, custo médio 50 -> margem por venda bem positiva
    # (600 - 50 - 15%*600 = 460/venda), 10 vendas -> serviço ~ +4600, cobre o
    # buraco do produto com folga e vira o total positivo.
    for i in range(10):
        records.append(_rec(
            base + dt.timedelta(days=i), f"SVCCUST{i}", "servico",
            value=600.0, entry_cost=50.0, store="LOJA-MASCARADA",
        ))
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-MASCARADA"]

    assert entry.product_margin < 0
    assert entry.service_margin > 0
    assert entry.total_margin > 0
    assert entry.total_margin == pytest.approx(entry.product_margin + entry.service_margin)
    assert entry.masks_negative_product_margin is True


def test_healthy_store_with_both_margins_positive_is_never_masked():
    """Contraste: loja saudável — produto E serviço ambos com margem positiva.
    Nunca deve ser marcada, mesmo com massa de dado comparável ao caso mascarado."""
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    records = []
    for i in range(10):
        records.append(_rec(
            base + dt.timedelta(days=i), f"PRODCUST{i}", "produto",
            value=400.0, entry_cost=150.0, store="LOJA-SAUDAVEL",
        ))
    for i in range(10):
        records.append(_rec(
            base + dt.timedelta(days=i), f"SVCCUST{i}", "servico",
            value=300.0, entry_cost=80.0, store="LOJA-SAUDAVEL",
        ))
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-SAUDAVEL"]

    assert entry.product_margin > 0
    assert entry.service_margin > 0
    assert entry.total_margin > 0
    assert entry.masks_negative_product_margin is False


def test_masks_flag_false_when_service_partially_offsets_but_total_stays_negative():
    """Fronteira realista (espelha o padrão observado em L7-Oeste no dado real, mas
    construído aqui como caso sintético, não extraído do fixture): produto negativo,
    serviço positivo, mas insuficiente para virar o total — total continua negativo.
    masks_negative_product_margin tem que ficar False (a condição é total > 0, não
    "serviço ajudou")."""
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    records = []
    for i in range(10):
        records.append(_rec(
            base + dt.timedelta(days=i), f"PRODCUST{i}", "produto",
            value=100.0, entry_cost=250.0, store="LOJA-QUASE",
        ))  # ~ -165/venda * 10 = -1650
    for i in range(3):
        records.append(_rec(
            base + dt.timedelta(days=i), f"SVCCUST{i}", "servico",
            value=300.0, entry_cost=100.0, store="LOJA-QUASE",
        ))  # (300-100-45)/venda = 155/venda * 3 = 465, insuficiente
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-QUASE"]

    assert entry.product_margin < 0
    assert entry.service_margin > 0
    assert entry.total_margin < 0
    assert entry.masks_negative_product_margin is False


def test_masks_flag_false_when_total_margin_is_exactly_zero():
    """Limite exato: product_margin < 0 mas total_margin == 0 (não > 0) — a condição
    pede estritamente > 0, então não pode mascarar."""
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    records = [
        # produto: (100 - 150 - 15) = -65/venda * 4 = -260
        *[_rec(base + dt.timedelta(days=i), f"P{i}", "produto", value=100.0,
               entry_cost=150.0, store="LOJA-ZERO") for i in range(4)],
    ]
    # serviço: precisa somar exatamente +260 para total = 0.
    # (300 - 100 - 45) = 155/venda -> não fecha redondo; usamos 2 vendas calibradas
    # para fechar em exatamente +260 no total combinado via valor/custo escolhidos.
    # margem por venda de serviço = value - cost - 0.15*value = 0.85*value - cost
    # queremos 2 vendas de serviço somando 260: 0.85*value - cost = 130 cada.
    # value=300, cost=300*0.85-130=125
    records += [
        _rec(base + dt.timedelta(days=10), "S0", "servico", value=300.0,
             entry_cost=125.0, store="LOJA-ZERO"),
        _rec(base + dt.timedelta(days=11), "S1", "servico", value=300.0,
             entry_cost=125.0, store="LOJA-ZERO"),
    ]
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-ZERO"]

    assert entry.product_margin < 0
    assert entry.total_margin == pytest.approx(0.0, abs=0.01)
    assert entry.masks_negative_product_margin is False


def test_masks_flag_false_when_product_margin_is_exactly_zero():
    """Limite exato: product_margin == 0 (não < 0) mesmo com serviço positivo — não
    pode mascarar, a condição pede produto ESTRITAMENTE negativo."""
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    # produto com margem exatamente 0: value=200, cost=200-30=170 -> 200-170-30=0
    records = [
        _rec(base, "P0", "produto", value=200.0, entry_cost=170.0, store="LOJA-PRODZERO"),
        _rec(base + dt.timedelta(days=1), "S0", "servico", value=500.0,
             entry_cost=50.0, store="LOJA-PRODZERO"),
    ]
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-PRODZERO"]

    assert entry.product_margin == pytest.approx(0.0, abs=1e-9)
    assert entry.service_margin > 0
    assert entry.masks_negative_product_margin is False


def test_real_fixture_has_no_store_with_positive_total_and_negative_product_today():
    """Documenta o estado atual do dado real: nenhuma loja hoje bate a condição de
    masks_negative_product_margin (a mais próxima, L7-Oeste, tem TOTAL negativo, não
    positivo) — é por isso que os testes centrais acima são sintéticos. Se esse
    fato do dado mudar, este teste (não a lógica de produção) precisa ser revisto."""
    report = run_audit(_FIXTURE)
    assert not any(s.masks_negative_product_margin for s in report.service_decomposition)
    assert len(report.service_decomposition) > 0


# ---------------------------------------------------------------------------
# 3. follow_on_cac_effect — primeira venda por loja + exclusão de pseudo-cliente
# ---------------------------------------------------------------------------

def test_follow_on_cac_effect_counts_only_product_revenue_of_service_first_customers():
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    records = [
        # Cliente A: primeira venda NAQUELA loja é serviço, depois compra produto
        # duas vezes -> as duas compras de produto entram no efeito.
        _rec(base, "A", "servico", value=500.0, entry_cost=100.0, store="LOJA-CAC"),
        _rec(base + dt.timedelta(days=10), "A", "produto", value=300.0, entry_cost=150.0, store="LOJA-CAC"),
        _rec(base + dt.timedelta(days=20), "A", "produto", value=200.0, entry_cost=100.0, store="LOJA-CAC"),
        # Cliente B: primeira venda é PRODUTO -> nunca entra no efeito, mesmo
        # comprando serviço depois.
        _rec(base + dt.timedelta(days=1), "B", "produto", value=400.0, entry_cost=200.0, store="LOJA-CAC"),
        _rec(base + dt.timedelta(days=15), "B", "servico", value=350.0, entry_cost=80.0, store="LOJA-CAC"),
    ]
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-CAC"]

    # Só as duas compras de PRODUTO do cliente A (300 + 200 = 500); a própria venda
    # de serviço de A não conta (é a linha de serviço, não follow-on de produto);
    # nada do cliente B conta.
    assert entry.follow_on_cac_effect == pytest.approx(500.0)


def test_follow_on_cac_effect_is_zero_when_no_customer_starts_with_service():
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    records = [
        _rec(base, "A", "produto", value=300.0, entry_cost=150.0, store="LOJA-SEMCAC"),
        _rec(base + dt.timedelta(days=5), "A", "servico", value=200.0, entry_cost=50.0, store="LOJA-SEMCAC"),
        _rec(base + dt.timedelta(days=1), "B", "produto", value=250.0, entry_cost=100.0, store="LOJA-SEMCAC"),
    ]
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-SEMCAC"]
    assert entry.follow_on_cac_effect == 0.0


def test_follow_on_cac_effect_excludes_pseudo_customer_even_when_service_first():
    """Pseudo-cliente (walk-in sem cadastro, _ANONYMOUS_CUSTOMER) nunca conta como
    cliente aqui — mesmo que a primeira linha "dele" seja serviço e a segunda
    produto, isso é só coincidência de agregação de várias pessoas diferentes sob 1
    rótulo, não uma pessoa real com uma jornada de aquisição."""
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    records = [
        _rec(base, _ANONYMOUS_CUSTOMER, "servico", value=500.0, entry_cost=100.0, store="LOJA-PSEUDO"),
        _rec(base + dt.timedelta(days=1), _ANONYMOUS_CUSTOMER, "produto", value=900.0, entry_cost=100.0, store="LOJA-PSEUDO"),
        # cliente real de controle para confirmar que o mecanismo em si funciona
        # nessa loja quando é uma pessoa de verdade.
        _rec(base + dt.timedelta(days=2), "REAL1", "servico", value=500.0, entry_cost=100.0, store="LOJA-PSEUDO"),
        _rec(base + dt.timedelta(days=3), "REAL1", "produto", value=120.0, entry_cost=60.0, store="LOJA-PSEUDO"),
    ]
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}
    entry = decomposition["LOJA-PSEUDO"]

    # Só a compra de produto do cliente REAL (120) conta; os 900 do pseudo-cliente
    # não entram, mesmo tendo o padrão "serviço primeiro, produto depois".
    assert entry.follow_on_cac_effect == pytest.approx(120.0)


def test_follow_on_cac_effect_scoped_per_store_not_globally():
    """"Primeira venda NAQUELA loja" — um cliente cuja primeira compra na REDE foi
    produto (em outra loja) mas cuja primeira compra NESTA loja foi serviço ainda
    conta pra follow-on effect desta loja."""
    th = AuditThresholdsConfig()
    base = dt.datetime(2024, 1, 1)
    records = [
        # Cliente X: primeira compra da REDE é produto na LOJA-A.
        _rec(base, "X", "produto", value=300.0, entry_cost=150.0, store="LOJA-A"),
        # Na LOJA-B, a primeira compra de X é serviço, seguida de produto.
        _rec(base + dt.timedelta(days=5), "X", "servico", value=500.0, entry_cost=100.0, store="LOJA-B"),
        _rec(base + dt.timedelta(days=6), "X", "produto", value=250.0, entry_cost=100.0, store="LOJA-B"),
    ]
    df = _records_to_frame(records)
    decomposition = {s.store: s for s in detect_service_decomposition(df, th)}

    assert decomposition["LOJA-A"].follow_on_cac_effect == 0.0
    assert decomposition["LOJA-B"].follow_on_cac_effect == pytest.approx(250.0)


# ---------------------------------------------------------------------------
# 4. thresholds — nenhum literal mágico dentro da função
# ---------------------------------------------------------------------------

def test_service_category_label_is_driven_by_thresholds_not_hardcoded_string():
    """Trocar thresholds.service_category_label por um valor não-default tem que
    mudar o que é tratado como serviço — se a função tivesse "servico" cravado, este
    teste falharia (a linha continuaria classificada como produto)."""
    base = dt.datetime(2024, 1, 1)
    records = [
        _rec(base, "P1", "manutencao", value=100.0, entry_cost=250.0, store="LOJA-LABEL"),  # produto negativo
        _rec(base + dt.timedelta(days=1), "S1", "manutencao", value=600.0, entry_cost=50.0, store="LOJA-LABEL"),
    ]
    df = _records_to_frame(records)

    th_default = AuditThresholdsConfig()
    default_entry = {s.store: s for s in detect_service_decomposition(df, th_default)}["LOJA-LABEL"]
    # Com o label default "servico", nenhuma linha é "manutencao" -> tudo é produto.
    assert default_entry.service_margin == 0.0

    th_custom = AuditThresholdsConfig(service_category_label="manutencao")
    custom_entry = {s.store: s for s in detect_service_decomposition(df, th_custom)}["LOJA-LABEL"]
    # Com o label customizado, a linha "manutencao" de maior margem vira serviço.
    assert custom_entry.service_margin > 0
    assert custom_entry.product_margin < custom_entry.service_margin


def test_variable_cost_pct_is_driven_by_thresholds_not_hardcoded_number():
    """Trocar thresholds.variable_cost_pct tem que mudar o resultado numérico da
    margem — se a função tivesse 15.0 (ou qualquer número) cravado, o resultado
    seria idêntico independente do threshold."""
    base = dt.datetime(2024, 1, 1)
    records = [
        _rec(base + dt.timedelta(days=i), f"P{i}", "produto", value=500.0,
             entry_cost=200.0, store="LOJA-VCP")
        for i in range(5)
    ]
    df = _records_to_frame(records)

    th_low = AuditThresholdsConfig(variable_cost_pct=5.0)
    th_high = AuditThresholdsConfig(variable_cost_pct=40.0)
    entry_low = {s.store: s for s in detect_service_decomposition(df, th_low)}["LOJA-VCP"]
    entry_high = {s.store: s for s in detect_service_decomposition(df, th_high)}["LOJA-VCP"]

    assert entry_low.product_margin != entry_high.product_margin
    # margem por venda esperada: 500 - 200 - vcp%*500, vezes 5 vendas.
    assert entry_low.product_margin == pytest.approx((500 - 200 - 0.05 * 500) * 5)
    assert entry_high.product_margin == pytest.approx((500 - 200 - 0.40 * 500) * 5)


# ---------------------------------------------------------------------------
# Hardening — guards de robustez
# ---------------------------------------------------------------------------

def test_no_crash_when_entry_cost_column_is_entirely_absent():
    """Sem coluna entry_cost no df (nunca deveria acontecer vindo de
    _records_to_frame, mas a função não pode presumir isso silenciosamente) —
    degrada pra margem 0.0 em vez de estourar KeyError, mesmo critério de
    'nunca inventa custo' que o resto do motor segue."""
    th = AuditThresholdsConfig()
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "product": ["P1", "P2"], "customer": ["C1", "C2"],
        "value": [100.0, 200.0], "category": ["produto", "servico"],
        "store": ["LOJA-SEMCOL", "LOJA-SEMCOL"],
    })
    result = detect_service_decomposition(df, th)
    entry = {s.store: s for s in result}["LOJA-SEMCOL"]
    assert entry.product_margin == 0.0
    assert entry.service_margin == 0.0
    assert entry.masks_negative_product_margin is False


def test_returns_empty_without_store_column():
    th = AuditThresholdsConfig()
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"]), "product": ["P1"], "customer": ["C1"],
        "value": [100.0], "entry_cost": [50.0], "category": ["produto"],
    })
    assert detect_service_decomposition(df, th) == []


def test_returns_empty_without_category_column():
    th = AuditThresholdsConfig()
    df = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"]), "product": ["P1"], "customer": ["C1"],
        "value": [100.0], "entry_cost": [50.0], "store": ["LOJA-X"],
    })
    assert detect_service_decomposition(df, th) == []


def test_tie_break_on_same_day_purchases_is_deterministic_and_order_stable():
    """Empate real: cliente compra serviço E produto no MESMO dia, na primeira
    visita àquela loja (sem granularidade de horário no dado, não há como saber qual
    "realmente" veio primeiro). Duas garantias:
    (1) repetir a chamada sobre o MESMO df várias vezes dá sempre o mesmo resultado
        (reprodutibilidade é uma promessa central do motor);
    (2) o desempate segue a ordem original das linhas de entrada (sort_values com
        kind="stable") — inverter a ordem das duas linhas de entrada inverte qual
        categoria "vence" o empate, provando que o critério é a ordem de origem, não
        um artefato arbitrário de algoritmo de sort não-documentado como estável."""
    th = AuditThresholdsConfig()
    same_day = dt.datetime(2024, 3, 1)

    service_row = _rec(same_day, "TIE1", "servico", value=500.0, entry_cost=100.0, store="LOJA-EMPATE")
    product_row = _rec(same_day, "TIE1", "produto", value=300.0, entry_cost=150.0, store="LOJA-EMPATE")

    df_service_first = _records_to_frame([service_row, product_row])
    df_product_first = _records_to_frame([product_row, service_row])

    # (1) reprodutibilidade sobre o mesmo df.
    results = [
        {s.store: s for s in detect_service_decomposition(df_service_first, th)}["LOJA-EMPATE"].follow_on_cac_effect
        for _ in range(10)
    ]
    assert len(set(results)) == 1, f"resultado não-determinístico em empate: {results}"

    # (2) ordem de entrada decide o desempate: serviço primeiro na entrada -> a
    # compra de produto do mesmo dia conta como follow-on; produto primeiro na
    # entrada -> não conta (a "primeira venda" passa a ser produto).
    effect_service_first = {
        s.store: s for s in detect_service_decomposition(df_service_first, th)
    }["LOJA-EMPATE"].follow_on_cac_effect
    effect_product_first = {
        s.store: s for s in detect_service_decomposition(df_product_first, th)
    }["LOJA-EMPATE"].follow_on_cac_effect

    assert effect_service_first == pytest.approx(300.0)
    assert effect_product_first == 0.0

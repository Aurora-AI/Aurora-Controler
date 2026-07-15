"""
Testes de regressão — Bloco D, item D4 da spec de goal-loop v2
(docs/os/exrs-v2-goal-loop/SPEC.md): SEV (Sistema de Eficiência de Venda) — duas
asserções INDEPENDENTES uma da outra.

1. Captura de cliente: vendedor com alta fração de vendas SEM cliente identificado
   (walk-in, `_ANONYMOUS_CUSTOMER`) tem "captura baixa" sinalizada MESMO que converta
   bem (receita/volume altos) — captura baixa não pode ser mascarada por bom
   desempenho de venda.
2. Ramp-up: vendedor cuja primeira venda é recente (tenure curta, em dias, mesmo
   estilo de `months_of_history`/D3) NUNCA é penalizado por volume baixo — volume
   baixo em ramp é esperado, não é sinal de baixo desempenho.

Lógica GERAL, não gabarito: `detect_salesperson_performance` agrupa DINAMICAMENTE por
vendedor (groupby sobre o que existir no dado — nunca uma lista fixa de vendedor_id).
Os testes sintéticos usam nomes de vendedor fabricados só para provar a
aritmética/threshold, isolados de qualquer fixture real. Os testes com
`consultoria_real_test.xlsx` verificam apenas a FORMA da asserção (existe >= 1
vendedor de captura baixa, existe >= 1 vendedor em ramp que não é penalizado por
volume, e um vendedor maduro com boa captura e bom volume não é penalizado em nenhum
dos dois flags) — descobertos rodando o código, nenhum vendedor_id é cravado aqui.
"""
from pathlib import Path

import pandas as pd

from product_b.oracle.commercial_auditor import _ANONYMOUS_CUSTOMER, detect_salesperson_performance, run_audit
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"


# ── Aritmética isolada (sintética, sem depender de nenhuma fixture real) ────────────

def _synthetic_df() -> pd.DataFrame:
    """4 vendedores fabricados:
    - 'Lobo Bom' (V-LOBO): tenure longa, MUITAS vendas SEM cliente identificado, mas
      receita/volume altos — prova que captura baixa não é mascarada por bom
      desempenho.
    - 'Maduro Bom' (V-MADURO): tenure longa, captura alta, volume alto — não deve ser
      flagueado em nada.
    - 'Maduro Fraco' (V-FRACOVOL): tenure longa, captura alta, volume BAIXO
      (comparado aos pares maduros) — deve pegar low_volume_flag, mas não
      low_capture_flag.
    - 'Novato' (V-NOVATO): tenure MUITO curta (poucos dias), volume objetivamente
      baixo — não pode ser penalizado por volume (has_sufficient_tenure=False).
    Os 3 vendedores maduros vendem cedo (dias 0-99 de uma janela-base); o novato vende
    só nos 3 últimos dias da rede (dias 300-302) — a data mais recente CONHECIDA NA
    REDE (`global_max_date`) é fixada pelo novato, dando aos maduros tenure de ~302
    dias (bem acima do limiar padrão de 180) e ao novato tenure de ~2 dias (bem
    abaixo) — margem confortável dos dois lados, sem colar na borda do threshold.
    """
    rows = []
    base = pd.Timestamp("2024-01-01")

    # Lobo Bom: 100 vendas, 70% sem cliente identificado, receita alta (ticket 500).
    for i in range(100):
        customer = _ANONYMOUS_CUSTOMER if i % 10 < 7 else f"C{i}"
        rows.append({
            "date": base + pd.Timedelta(days=i), "product": "P1", "customer": customer,
            "value": 500.0, "salesperson": "V-LOBO",
        })

    # Maduro Bom: 100 vendas, 90% com cliente identificado, receita comparável.
    for i in range(100):
        customer = f"D{i}" if i % 10 < 9 else _ANONYMOUS_CUSTOMER
        rows.append({
            "date": base + pd.Timedelta(days=i), "product": "P1", "customer": customer,
            "value": 500.0, "salesperson": "V-MADURO",
        })

    # Maduro Fraco: tenure longa (mesma janela cedo dos outros maduros), captura alta
    # (90%), mas só 10 vendas (volume baixo frente aos pares maduros de 100 vendas).
    for i in range(10):
        customer = f"E{i}" if i % 10 < 9 else _ANONYMOUS_CUSTOMER
        rows.append({
            "date": base + pd.Timedelta(days=i), "product": "P1", "customer": customer,
            "value": 500.0, "salesperson": "V-FRACOVOL",
        })

    # Novato: vende só nos 3 últimos dias da rede — tenure de ~2 dias, poucas vendas,
    # captura perfeita (não é o ponto do teste, só volume).
    recent_start = base + pd.Timedelta(days=300)
    for i in range(3):
        rows.append({
            "date": recent_start + pd.Timedelta(days=i), "product": "P1",
            "customer": f"F{i}", "value": 500.0, "salesperson": "V-NOVATO",
        })

    return pd.DataFrame(rows)


def test_low_capture_flag_not_masked_by_high_revenue_or_volume():
    """Asserção 1 da SEV: 'Lobo Bom' converte tão bem quanto 'Maduro Bom' (mesma
    receita/volume), mas tem 70% de vendas sem cliente identificado -> captura baixa
    tem que aparecer mesmo com bom desempenho de venda."""
    thresholds = AuditThresholdsConfig()  # sev_min_capture_pct default = 60.0
    entries = detect_salesperson_performance(_synthetic_df(), thresholds)
    by_sp = {e.salesperson: e for e in entries}

    lobo = by_sp["V-LOBO"]
    maduro = by_sp["V-MADURO"]

    # Mesmo desempenho bruto de venda...
    assert lobo.total_revenue == maduro.total_revenue
    assert lobo.sample_size == maduro.sample_size

    # ...mas captura MUITO diferente, e o flag reflete isso sem ser mascarado.
    assert lobo.capture_rate_pct == 30.0
    assert lobo.low_capture_flag is True
    assert maduro.capture_rate_pct == 90.0
    assert maduro.low_capture_flag is False


def test_low_capture_flag_is_never_suppressed_by_sufficient_tenure():
    """low_capture_flag é avaliado SEMPRE — nunca condicionado a has_sufficient_tenure
    (o 'Lobo Bom' tem tenure longa E ainda assim é sinalizado)."""
    thresholds = AuditThresholdsConfig()
    entries = detect_salesperson_performance(_synthetic_df(), thresholds)
    lobo = next(e for e in entries if e.salesperson == "V-LOBO")

    assert lobo.has_sufficient_tenure is True  # tenure longa
    assert lobo.low_capture_flag is True  # mas ainda assim sinalizado


def test_ramp_seller_never_gets_low_volume_flag_even_with_objectively_low_volume():
    """Asserção 2 da SEV: 'Novato' tem volume objetivamente baixíssimo (3 vendas
    contra 100 dos pares maduros) mas tenure curtíssima (~2 dias) -> NUNCA pode ser
    penalizado por volume."""
    thresholds = AuditThresholdsConfig()  # sev_ramp_min_days default = 180.0
    entries = detect_salesperson_performance(_synthetic_df(), thresholds)
    novato = next(e for e in entries if e.salesperson == "V-NOVATO")
    maduro = next(e for e in entries if e.salesperson == "V-MADURO")

    assert novato.sample_size < maduro.sample_size, "fixture não é objetivamente baixo — teste não testa nada"
    assert novato.has_sufficient_tenure is False
    assert novato.low_volume_flag is False


def test_mature_seller_with_below_peer_median_volume_can_be_flagged():
    """'Maduro Fraco' tem tenure suficiente e volume abaixo da mediana dos pares
    maduros -> low_volume_flag pode ser True (a asserção da spec só proíbe penalizar
    quem está em ramp; um vendedor maduro com volume baixo é sinal válido)."""
    thresholds = AuditThresholdsConfig()
    entries = detect_salesperson_performance(_synthetic_df(), thresholds)
    fraco = next(e for e in entries if e.salesperson == "V-FRACOVOL")

    assert fraco.has_sufficient_tenure is True
    assert fraco.low_capture_flag is False  # captura alta — não confundir as 2 dimensões
    assert fraco.low_volume_flag is True


def test_mature_high_capture_high_volume_seller_flagged_in_neither_dimension():
    """Controle: vendedor maduro com boa captura E bom volume não é penalizado em
    nenhum dos dois flags."""
    thresholds = AuditThresholdsConfig()
    entries = detect_salesperson_performance(_synthetic_df(), thresholds)
    maduro = next(e for e in entries if e.salesperson == "V-MADURO")

    assert maduro.low_capture_flag is False
    assert maduro.low_volume_flag is False


def test_thresholds_are_configurable_not_hardcoded():
    """O mesmo dado sintético produz rótulos diferentes conforme os limiares
    injetados — prova que os dois novos limiares vêm de AuditThresholdsConfig, não de
    número cravado dentro da função."""
    df = _synthetic_df()

    permissive = AuditThresholdsConfig(sev_min_capture_pct=0.0, sev_ramp_min_days=0.0)
    entries_permissive = detect_salesperson_performance(df, permissive)
    lobo_permissive = next(e for e in entries_permissive if e.salesperson == "V-LOBO")
    novato_permissive = next(e for e in entries_permissive if e.salesperson == "V-NOVATO")
    assert lobo_permissive.low_capture_flag is False  # piso 0% -> ninguém é "baixo"
    assert novato_permissive.has_sufficient_tenure is True  # piso 0 dias -> qualquer tenure basta

    strict = AuditThresholdsConfig(sev_min_capture_pct=100.0, sev_ramp_min_days=99999.0)
    entries_strict = detect_salesperson_performance(df, strict)
    maduro_strict = next(e for e in entries_strict if e.salesperson == "V-MADURO")
    assert maduro_strict.low_capture_flag is True  # só 90% < piso de 100%
    assert all(not e.has_sufficient_tenure for e in entries_strict)
    assert all(not e.low_volume_flag for e in entries_strict)  # ninguém tem tenure suficiente


def test_no_salesperson_column_returns_empty_never_invents():
    """Sem coluna de vendedor identificada no arquivo de origem, retorna vazio —
    nunca inventa vendedor (mesmo critério de detect_store_performance)."""
    df = _synthetic_df().drop(columns=["salesperson"])
    entries = detect_salesperson_performance(df, AuditThresholdsConfig())
    assert entries == []


def test_groupby_is_dynamic_not_a_fixed_list():
    """Renomear os vendedores sintéticos para nomes arbitrários novos ainda produz o
    número certo de entradas com as métricas certas — prova que o agrupamento é sobre
    o que existe no dado, não uma lista fixa."""
    df = _synthetic_df()
    df["salesperson"] = df["salesperson"].replace({
        "V-LOBO": "ZZZ-1", "V-MADURO": "ZZZ-2", "V-FRACOVOL": "ZZZ-3", "V-NOVATO": "ZZZ-4",
    })
    entries = detect_salesperson_performance(df, AuditThresholdsConfig())
    names = {e.salesperson for e in entries}
    assert names == {"ZZZ-1", "ZZZ-2", "ZZZ-3", "ZZZ-4"}


# ── Dado real (consultoria_real_test.xlsx) — só asserções de FORMA, nada cravado ────

def test_at_least_one_low_capture_salesperson_found_dynamically_in_real_fixture():
    """D4 (asserção 1): no dado real, pelo menos um vendedor tem captura abaixo do
    limiar padrão — descoberto rodando `detect_salesperson_performance`, nunca por
    vendedor_id cravado aqui."""
    report = run_audit(FIXTURE)
    entries = report.salesperson_performance
    assert entries, "fixture não tem coluna de vendedor mapeada — teste não testa nada"

    low_capture = [e for e in entries if e.low_capture_flag]
    assert low_capture, (
        f"esperava >=1 vendedor com captura < {report.thresholds.sev_min_capture_pct}% no dado real"
    )
    for e in low_capture:
        assert e.capture_rate_pct < report.thresholds.sev_min_capture_pct
        # A procedência (sample_size) é real, nunca zerada.
        assert e.sample_size > 0


def test_at_least_one_ramp_salesperson_not_penalized_for_volume_in_real_fixture():
    """D4 (asserção 2): o vendedor de tenure mais curta do dado real (descoberto
    dinamicamente, nunca por vendedor_id cravado) não tem tenure suficiente e por isso
    NUNCA é marcado com low_volume_flag, mesmo que o volume dele seja objetivamente o
    menor da rede."""
    report = run_audit(FIXTURE)
    entries = report.salesperson_performance
    assert entries, "fixture não tem coluna de vendedor mapeada — teste não testa nada"

    newest = min(entries, key=lambda e: e.days_since_first_sale)
    assert newest.days_since_first_sale < report.thresholds.sev_ramp_min_days, (
        "fixture não contém vendedor em ramp sob o limiar padrão — teste não testa nada"
    )
    assert newest.has_sufficient_tenure is False
    assert newest.low_volume_flag is False


def test_mature_high_capture_high_volume_salesperson_not_penalized_in_real_fixture():
    """Controle no dado real: um vendedor maduro (tenure suficiente) com captura acima
    do limiar E volume acima da mediana dos pares maduros não é penalizado em nenhum
    dos dois flags — descoberto dinamicamente, nunca por vendedor_id cravado."""
    report = run_audit(FIXTURE)
    entries = report.salesperson_performance
    assert entries, "fixture não tem coluna de vendedor mapeada — teste não testa nada"

    tenured = [e for e in entries if e.has_sufficient_tenure]
    assert tenured, "teste depende de haver >=1 vendedor com tenure suficiente no dado real"
    median_volume = sorted(e.sample_size for e in tenured)[len(tenured) // 2]

    candidates = [
        e for e in tenured
        if not e.low_capture_flag and e.sample_size >= median_volume
    ]
    assert candidates, (
        "esperava >=1 vendedor maduro com boa captura e bom volume no dado real"
    )
    for e in candidates:
        assert e.low_capture_flag is False
        assert e.low_volume_flag is False


def test_salesperson_stays_in_report_not_removed_or_hidden():
    """Todo vendedor continua no relatório com seus números reais — nunca removido,
    nunca escondido — mesmo padrão de StorePerformance/D3."""
    report = run_audit(FIXTURE)
    entries = report.salesperson_performance
    assert entries, "fixture não tem coluna de vendedor mapeada — teste não testa nada"
    for e in entries:
        assert e.sample_size > 0
        assert e.total_revenue != 0.0 or e.sample_size > 0

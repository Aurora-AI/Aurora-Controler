"""
Teste TRANSVERSAL — registro único de pseudo-entidade (`is_pseudo_entity`) + helper
compartilhado (`benchmark_population`).

Achado 3x nesta sessão antes de virar regra: pseudo-entidade (cliente sem cadastro,
vendedor não identificado) contaminando régua de referência cross-entidade (quantil em
RFM, mediana em SEV). Duas vezes foi corrigido com um filtro inline por detector
(RFM, churn) — a terceira vez (SEV) mostrou que a defesa morava na cabeça de quem
escrevia cada detector, não na estrutura, e reapareceu. Este arquivo varre TODOS os
detectores com padrão de régua de referência e afirma: pseudo-entidade nunca entra na
régua que avalia as entidades reais — nem melhora, nem piora, porque nunca deveria ter
entrado.

Metodologia da varredura: roda cada detector duas vezes sobre o MESMO conjunto de
entidades reais — uma vez sozinho, outra vez com um volume GRANDE de linhas de
pseudo-entidade adicionadas — e afirma que o resultado das entidades reais é idêntico
nas duas rodadas (invariância a ruído de pseudo-entidade).
"""
import datetime as dt

from oracle.commercial_auditor import (
    _ANONYMOUS_CUSTOMER, _PSEUDO_ENTITY_IDS, _UNKNOWN_SALESPERSON, _UNKNOWN_STORE,
    _records_to_frame, benchmark_population, detect_churn, detect_rfm_champions,
    detect_salesperson_performance, is_pseudo_entity,
)
from oracle.forensic_contracts import AuditThresholdsConfig, SalesRecord


# ── Registro único ──────────────────────────────────────────────────────────────────

def test_registry_contains_all_three_known_sentinels():
    assert _PSEUDO_ENTITY_IDS == {_ANONYMOUS_CUSTOMER, _UNKNOWN_STORE, _UNKNOWN_SALESPERSON}


def test_is_pseudo_entity_true_only_for_registered_sentinels():
    assert is_pseudo_entity(_ANONYMOUS_CUSTOMER)
    assert is_pseudo_entity(_UNKNOWN_STORE)
    assert is_pseudo_entity(_UNKNOWN_SALESPERSON)
    assert not is_pseudo_entity("C-001")
    assert not is_pseudo_entity("V-03")
    assert not is_pseudo_entity("L1 - Centro")


def test_benchmark_population_excludes_pseudo_entities():
    raw = {
        "V0": {"sample_size": 10}, _UNKNOWN_SALESPERSON: {"sample_size": 500},
        "V1": {"sample_size": 15},
    }
    population = benchmark_population(raw)
    assert {p["sample_size"] for p in population} == {10, 15}


def test_benchmark_population_applies_predicate_on_top_of_pseudo_exclusion():
    raw = {
        "V0": {"sample_size": 10, "ok": True}, "V1": {"sample_size": 15, "ok": False},
        _UNKNOWN_SALESPERSON: {"sample_size": 999, "ok": True},
    }
    population = benchmark_population(raw, predicate=lambda s: s["ok"])
    assert population == [{"sample_size": 10, "ok": True}]


# ── Varredura: pseudo-entidade volumosa não pode mudar resultado das entidades reais ─

def _real_salesperson_records() -> list[SalesRecord]:
    volumes = {"V0": 10, "V1": 15, "V2": 20, "V3": 25, "V4": 30}
    return [
        SalesRecord(
            date=dt.datetime(2024, 1, 1) + dt.timedelta(days=i * 5), product="P1",
            customer=f"C{v}{i}", value=100.0, entry_cost=50.0, category=None,
            store=None, salesperson=v, source_file="x", source_row=1,
        )
        for v, n in volumes.items() for i in range(n)
    ]


def _pseudo_salesperson_noise(n: int) -> list[SalesRecord]:
    # Datas confinadas à MESMA janela dos registros reais (V4, o mais longo, cobre
    # dias 0-145) — ruído fora dessa janela mudaria global_max_date e alteraria
    # tenure de todo mundo por um motivo diferente do que este teste isola (a
    # contaminação da RÉGUA, não da janela de observação).
    return [
        SalesRecord(
            date=dt.datetime(2024, 1, 1) + dt.timedelta(days=i % 145), product="P1",
            customer=f"CX{i}", value=50.0, entry_cost=25.0, category=None,
            store=None, salesperson=None, source_file="x", source_row=1,
        )
        for i in range(n)
    ]


def test_sweep_salesperson_low_volume_benchmark_invariant_to_pseudo_entity_volume():
    """D4 — regressão do bug achado por QA review: pseudo-vendedor volumoso (500
    linhas sem vendedor identificado) não pode deslocar a mediana de referência que
    decide se um vendedor real tem 'volume baixo'."""
    th = AuditThresholdsConfig()
    real = _real_salesperson_records()

    baseline = {e.salesperson: e for e in detect_salesperson_performance(_records_to_frame(real), th)}
    with_noise_records = real + _pseudo_salesperson_noise(500)
    with_noise = {
        e.salesperson: e
        for e in detect_salesperson_performance(_records_to_frame(with_noise_records), th)
    }

    for salesperson, expected in baseline.items():
        actual = with_noise[salesperson]
        assert actual.low_volume_flag == expected.low_volume_flag, (
            f"{salesperson}: low_volume_flag mudou de {expected.low_volume_flag} para "
            f"{actual.low_volume_flag} só por causa do volume de pseudo-vendedor"
        )
        assert actual.sample_size == expected.sample_size


def test_sweep_salesperson_pseudo_entity_stays_visible_in_report_not_hidden():
    """A régua exclui a pseudo-entidade, mas o relatório NÃO — fato bruto continua
    visível (mesmo princípio já usado em D3 para loja cold-start)."""
    th = AuditThresholdsConfig()
    records = _real_salesperson_records() + _pseudo_salesperson_noise(500)
    entries = detect_salesperson_performance(_records_to_frame(records), th)
    pseudo_entries = [e for e in entries if e.salesperson == _UNKNOWN_SALESPERSON]
    assert len(pseudo_entries) == 1
    assert pseudo_entries[0].sample_size == 500


def test_sweep_churn_and_rfm_never_include_pseudo_customer_regardless_of_volume():
    """Regressão de generalidade: pseudo-cliente nunca aparece em achado por-cliente
    de nenhum detector, não importa quantas linhas anônimas existam ao redor dele."""
    th = AuditThresholdsConfig()
    real_customer_records = [
        SalesRecord(
            date=dt.datetime(2023, 1, 1) + dt.timedelta(days=i * 90), product="P1",
            customer="C-REAL", value=900.0, entry_cost=None, category=None,
            store=None, salesperson=None, source_file="x", source_row=1,
        )
        for i in range(8)
    ]
    anonymous_records = [
        SalesRecord(
            date=dt.datetime(2024, 1, 1) + dt.timedelta(days=i), product="P1",
            customer=_ANONYMOUS_CUSTOMER, value=80.0, entry_cost=None, category=None,
            store=None, salesperson=None, source_file="x", source_row=1,
        )
        for i in range(300)
    ]
    df = _records_to_frame(real_customer_records + anonymous_records)

    churn_findings = detect_churn(df, th)
    assert all(f.customer_id != _ANONYMOUS_CUSTOMER for f in churn_findings)

    champions = detect_rfm_champions(df, th)
    assert all(c.customer_id != _ANONYMOUS_CUSTOMER for c in champions)

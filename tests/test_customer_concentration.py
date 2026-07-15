"""
Testes de regressão — Bloco B, item B7 da spec de goal-loop v2
(docs/os/exrs-v2-goal-loop/SPEC.md): concentração de cliente (risco de key-account).

Lógica GERAL, não gabarito: `detect_customer_concentration` agrupa DINAMICAMENTE por
(loja, cliente) — nenhum store/cliente específico é cravado em src/. Os testes
sintéticos usam nomes fabricados só para provar a ARITMÉTICA e o gate de pseudo-cliente,
isolados de qualquer fixture real. O teste com `consultoria_real_test.xlsx` verifica
apenas a FORMA da asserção (existe >= 1 achado de concentração alta, descoberto rodando
o código) — o cliente/loja é descoberto lendo o resultado do detector, nunca cravado
aqui.

Este é o primeiro uso real do registro único de pseudo-entidade (`_PSEUDO_ENTITY_IDS` /
`is_pseudo_entity`, ver commercial_auditor.py) fora dos detectores que já o usavam
(churn, RFM, receita latente, SEV) — B7 reaproveita o mesmo filtro
`~df["customer"].isin(_PSEUDO_ENTITY_IDS)`, nunca reinventa um literal
`"SEM_CADASTRO"` novo.
"""
from pathlib import Path

import pandas as pd

from product_b.oracle.commercial_auditor import (
    _ANONYMOUS_CUSTOMER, _records_to_frame, detect_customer_concentration,
    load_named_sheets, load_sales_records, run_audit,
)
from product_b.oracle.forensic_contracts import AuditThresholdsConfig

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"
NO_STORE_FIXTURE = Path(__file__).parent / "fixtures" / "sales_history_test.xlsx"


# ── Aritmética isolada (sintética, sem depender de nenhuma fixture real) ────────────

def _synthetic_df() -> pd.DataFrame:
    """2 lojas fabricadas: 'Loja Risco' (1 cliente domina a receita, key-account real)
    e 'Loja Diversificada' (receita espalhada por muitos clientes, ninguém concentra).
    Nomes fabricados só para testar a ARITMÉTICA do detector, nunca aparecem em
    produção."""
    rows = []
    dates = pd.date_range("2025-01-01", periods=12, freq="10D")
    # Loja Risco: KEY-CUSTOMER sozinho responde por 800 de 1000 (80%) — 4 outros
    # clientes dividem os 200 restantes.
    rows.append({
        "date": dates[0], "product": "P1", "customer": "KEY-CUSTOMER", "value": 800.0,
        "entry_cost": None, "category": None, "store": "Loja Risco",
    })
    for i in range(4):
        rows.append({
            "date": dates[i + 1], "product": "P1", "customer": f"OUTRO-{i}", "value": 50.0,
            "entry_cost": None, "category": None, "store": "Loja Risco",
        })
    # Loja Diversificada: 10 clientes, 100 cada — ninguém passa de 10%.
    for i in range(10):
        rows.append({
            "date": dates[i], "product": "P2", "customer": f"DIV-{i}", "value": 100.0,
            "entry_cost": None, "category": None, "store": "Loja Diversificada",
        })
    return pd.DataFrame(rows)


def test_dominant_customer_flagged_above_threshold():
    thresholds = AuditThresholdsConfig(concentration_risk_pct=25.0)
    findings = detect_customer_concentration(_synthetic_df(), thresholds)
    risky = [f for f in findings if f.store == "Loja Risco"]
    assert len(risky) == 1
    finding = risky[0]
    assert finding.customer == "KEY-CUSTOMER"
    assert abs(finding.customer_revenue - 800.0) < 1e-6
    assert abs(finding.store_revenue - 1000.0) < 1e-6
    assert abs(finding.concentration_pct - 80.0) < 1e-6
    assert finding.sample_size == 1


def test_diversified_store_produces_no_finding():
    thresholds = AuditThresholdsConfig(concentration_risk_pct=25.0)
    findings = detect_customer_concentration(_synthetic_df(), thresholds)
    assert not any(f.store == "Loja Diversificada" for f in findings)


def test_threshold_is_configurable_not_a_magic_number():
    """O mesmo dado sintético, com um threshold mais alto que a concentração real
    (80%), não gera achado — prova que o limiar vem de `AuditThresholdsConfig`, não de
    um número cravado dentro da função."""
    thresholds = AuditThresholdsConfig(concentration_risk_pct=90.0)
    findings = detect_customer_concentration(_synthetic_df(), thresholds)
    assert findings == []


def test_returns_empty_without_a_store_column():
    """Sem papel 'loja' identificado no arquivo de origem, o detector não inventa loja
    — retorna vazio, mesmo critério de `detect_store_performance` (D1)."""
    records, _ = load_sales_records(NO_STORE_FIXTURE)
    df = _records_to_frame(records)
    assert detect_customer_concentration(df, AuditThresholdsConfig()) == []


def test_returns_empty_on_empty_dataframe():
    df = _records_to_frame([])
    assert detect_customer_concentration(df, AuditThresholdsConfig()) == []


# ── Pseudo-cliente NUNCA vira falso key-account (primeiro uso real do registro) ─────

def test_pseudo_customer_never_appears_as_a_concentration_finding_even_when_dominant():
    """Cenário explícito: SE o pseudo-cliente (walk-in sem cadastro) não fosse
    excluído do numerador, ele apareceria como 'concentrando' 70% da receita da loja
    (soma de MUITOS passantes diferentes, não uma pessoa) — um falso alarme de
    key-account que não é ninguém de verdade. Com a exclusão via
    `_PSEUDO_ENTITY_IDS`/`is_pseudo_entity`, ele nunca aparece como `customer` de
    nenhum achado, mesmo dominando a receita da loja."""
    thresholds = AuditThresholdsConfig(concentration_risk_pct=25.0)
    dates = pd.date_range("2025-01-01", periods=20, freq="3D")
    rows = []
    # 70 walk-ins diferentes, cada um comprando uma vez, todos rotulados
    # _ANONYMOUS_CUSTOMER na agregação (mesmo pseudo-grupo, pessoas DIFERENTES na vida
    # real) — juntos somam 700 dos 1000 de receita da loja.
    for i in range(70):
        rows.append({
            "date": dates[i % len(dates)], "product": "P1", "customer": _ANONYMOUS_CUSTOMER,
            "value": 10.0, "entry_cost": None, "category": None, "store": "Loja Walk-in",
        })
    # 3 clientes reais cadastrados dividem os outros 300 — nenhum concentra sozinho.
    for i in range(3):
        rows.append({
            "date": dates[i], "product": "P1", "customer": f"REAL-{i}", "value": 100.0,
            "entry_cost": None, "category": None, "store": "Loja Walk-in",
        })
    df = pd.DataFrame(rows)

    store_total = df["value"].sum()
    anon_total = df.loc[df["customer"] == _ANONYMOUS_CUSTOMER, "value"].sum()
    assert 100.0 * anon_total / store_total > 25.0, (
        "cenário mal construído: pseudo-cliente precisa concentrar > threshold para "
        "provar que a exclusão é o que impede o falso alarme, não coincidência"
    )

    findings = detect_customer_concentration(df, thresholds)
    assert all(f.customer != _ANONYMOUS_CUSTOMER for f in findings), (
        "pseudo-cliente (walk-in agregado) apareceu como achado de concentração — "
        "falso alarme de key-account que não é ninguém de verdade"
    )
    # A loja walk-in não desaparece do universo — só ninguém real concentra nela.
    assert not any(f.store == "Loja Walk-in" for f in findings)


def test_pseudo_customer_excluded_end_to_end_through_run_audit(tmp_path):
    """Mesmo cenário acima, mas ponta a ponta via `run_audit` (ingestão real, sem
    cliente na coluna vira `_ANONYMOUS_CUSTOMER` em `load_sales_records`) — garante
    que a exclusão sobrevive ao pipeline completo, não só à chamada direta do
    detector."""
    dates = pd.date_range("2025-01-01", periods=20, freq="3D")
    rows = []
    for i in range(70):
        rows.append({
            "data": dates[i % len(dates)], "produto": "P1", "cliente": None,
            "valor": 10.0, "loja": "Loja Walk-in",
        })
    for i in range(3):
        rows.append({
            "data": dates[i], "produto": "P1", "cliente": f"REAL-{i}", "valor": 100.0,
            "loja": "Loja Walk-in",
        })
    fixture = tmp_path / "walkin_dominant.xlsx"
    pd.DataFrame(rows).to_excel(fixture, index=False, engine="openpyxl")

    report = run_audit(fixture)
    assert all(
        f.customer != _ANONYMOUS_CUSTOMER for f in report.customer_concentration
    )


# ── Dado real (consultoria_real_test.xlsx) — só forma, achado dinamicamente ─────────

def test_real_fixture_flags_at_least_one_dynamically_discovered_key_account():
    """B7: pelo menos 1 achado de concentração alta emerge do dado real, descoberto
    RODANDO o detector — nenhum cliente_id/loja é cravado no teste."""
    report = run_audit(FIXTURE)
    findings = report.customer_concentration
    assert findings, "esperava >= 1 achado de concentração de cliente no dado real"
    top = findings[0]
    assert top.concentration_pct >= AuditThresholdsConfig().concentration_risk_pct
    # Procedência: customer_revenue / store_revenue reproduz concentration_pct.
    recomputed = 100.0 * top.customer_revenue / top.store_revenue
    assert abs(recomputed - top.concentration_pct) < 1e-6


def test_real_fixture_findings_are_sorted_by_concentration_descending():
    findings = run_audit(FIXTURE).customer_concentration
    pcts = [f.concentration_pct for f in findings]
    assert pcts == sorted(pcts, reverse=True)


def test_real_fixture_pseudo_customer_never_appears_despite_large_walkin_volume():
    """Regressão de generalidade contra o dado real: o pseudo-cliente (walk-in) tem
    volume grande em várias lojas reais (centenas de vendas anônimas) — mesmo assim
    nunca aparece como `customer` em nenhum achado de concentração."""
    report = run_audit(FIXTURE)
    assert all(
        f.customer != "Client_" and not f.customer.startswith("SEM_CADASTRO")
        for f in report.customer_concentration
    )
    # Confirma que o pseudo-cliente de fato tem volume relevante no dado (sem isso o
    # teste acima não prova nada) — computado direto do arquivo, via o mesmo caminho
    # de ingestão da produção.
    records, _ = load_sales_records(FIXTURE)
    anon_rows = [r for r in records if r.customer == _ANONYMOUS_CUSTOMER]
    assert len(anon_rows) > 0, "fixture não tem venda anônima — teste não testa nada"


def test_customer_concentration_procedence_sample_size_matches_row_counts():
    """Todo achado tem procedência: `sample_size` bate com o nº real de vendas do
    cliente naquela loja, recontado a partir dos records crus (identidade canônica
    pré-anonimização, via CPF dedupe já aplicado no pipeline)."""
    report, identity_map = run_audit(FIXTURE, return_identity_map=True)
    assert report.customer_concentration, "sem achados — teste não testa nada"
    # Mapa reverso: pseudônimo -> lista de cliente_id brutos que foram mapeados nele
    # (D2 pode mesclar >1 cliente_id bruto no mesmo pseudônimo).
    reverse_map: dict[str, list[str]] = {}
    for raw_id, pseudonym in identity_map.items():
        reverse_map.setdefault(pseudonym, []).append(raw_id)

    named_sheets = load_named_sheets(FIXTURE)
    from product_b.oracle.commercial_auditor import build_cpf_canonical_map
    canonical_map = build_cpf_canonical_map(named_sheets.get("Clientes"))
    records, _ = load_sales_records(FIXTURE)
    records = [
        r.model_copy(update={"customer": canonical_map.get(r.customer, r.customer)})
        for r in records
    ]

    finding = report.customer_concentration[0]
    raw_ids = reverse_map.get(finding.customer, [])
    assert raw_ids, "pseudônimo do achado não encontrado no identity_map"
    actual_sample_size = sum(
        1 for r in records if r.store == finding.store and r.customer in raw_ids
    )
    assert actual_sample_size == finding.sample_size


def test_no_production_code_reads_the_gabarito_sheet_for_concentration():
    """Anti-overfit: o motor (src/product_b/oracle) nunca lê a aba 'Gabarito' — checagem
    indireta: rodar contra a fixture real não exige a aba, e ela não é uma das séries B
    carregadas por `load_named_sheets`."""
    named_sheets = load_named_sheets(FIXTURE)
    assert "Gabarito" not in named_sheets

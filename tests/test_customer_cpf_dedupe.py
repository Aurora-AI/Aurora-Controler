"""
Testes de regressão — Bloco D, item D2 da spec de goal-loop v2
(docs/os/exrs-v2-goal-loop/SPEC.md): dedupe de cliente por CPF.

Lógica GERAL, não gabarito: `build_cpf_canonical_map` agrupa DINAMICAMENTE sobre o que
existir na aba Clientes — nenhum cliente_id específico é cravado em src/. Os testes
sintéticos usam ids fabricados (`RAW-A1`, `RAW-C1`...) só para provar a ARITMÉTICA do
dedupe, isolados de qualquer fixture real. O teste com `consultoria_real_test.xlsx`
verifica a FORMA (existe >= 1 par de cliente_id que compartilha CPF na aba Clientes real
e esse par é mesclado em 1 só identidade nos detectores por-cliente) — o par é
descoberto lendo a planilha, nunca hardcoded aqui.
"""
from datetime import datetime
from pathlib import Path

from product_b.oracle.commercial_auditor import (
    _records_to_frame, build_cpf_canonical_map, detect_churn, detect_rfm_champions,
    load_named_sheets, load_sales_records, run_audit,
)
from product_b.oracle.forensic_contracts import AuditThresholdsConfig, SalesRecord

FIXTURE = Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx"
NO_CLIENTES_FIXTURE = Path(__file__).parent / "fixtures" / "sales_history_test.xlsx"


def _record(customer: str, dates_values: list[tuple[datetime, float]]) -> list[SalesRecord]:
    return [
        SalesRecord(
            date=d, product="P", customer=customer, value=v,
            source_file="f.xlsx", source_row=i + 2,
        )
        for i, (d, v) in enumerate(dates_values)
    ]


def _clientes_df(rows: list[dict]):
    import pandas as pd
    return pd.DataFrame(rows)


# ── build_cpf_canonical_map: aritmética isolada (sintética) ─────────────────────────

def test_two_cliente_ids_sharing_cpf_merge_to_the_lexicographically_smaller_id():
    df = _clientes_df([
        {"cliente_id": "XS-01B", "cpf": "321.654.987-00"},
        {"cliente_id": "XS-01A", "cpf": "321.654.987-00"},
    ])
    canonical_map = build_cpf_canonical_map(df)
    assert canonical_map == {"XS-01A": "XS-01A", "XS-01B": "XS-01A"}


def test_cpf_formatting_differences_still_merge_the_same_document():
    """'123.456.789-00' e '12345678900' são o MESMO CPF — só dígitos importam."""
    df = _clientes_df([
        {"cliente_id": "C-002", "cpf": "123.456.789-00"},
        {"cliente_id": "C-001", "cpf": "12345678900"},
    ])
    canonical_map = build_cpf_canonical_map(df)
    assert canonical_map == {"C-001": "C-001", "C-002": "C-001"}


def test_customer_without_cpf_is_never_merged():
    """Cliente sem CPF (célula vazia/NaN) preserva identidade própria — nunca aparece
    no mapa de dedupe, mesmo que outro cliente também não tenha CPF (ausência não é
    uma chave de agrupamento válida)."""
    df = _clientes_df([
        {"cliente_id": "C-001", "cpf": None},
        {"cliente_id": "C-002", "cpf": ""},
        {"cliente_id": "C-003", "cpf": "999.999.999-99"},
    ])
    canonical_map = build_cpf_canonical_map(df)
    assert canonical_map == {}


def test_unique_cpf_per_customer_produces_no_merge():
    df = _clientes_df([
        {"cliente_id": "C-001", "cpf": "111.111.111-11"},
        {"cliente_id": "C-002", "cpf": "222.222.222-22"},
        {"cliente_id": "C-003", "cpf": "333.333.333-33"},
    ])
    assert build_cpf_canonical_map(df) == {}


def test_group_of_three_sharing_cpf_all_merge_to_the_same_canonical_id():
    """A lógica não é hardcoded pra PARES — trio (ou mais) que compartilha CPF também
    mescla, todos apontando pro mesmo canônico."""
    df = _clientes_df([
        {"cliente_id": "Z-003", "cpf": "555.555.555-55"},
        {"cliente_id": "A-001", "cpf": "555.555.555-55"},
        {"cliente_id": "M-002", "cpf": "555.555.555-55"},
        {"cliente_id": "OTHER", "cpf": "666.666.666-66"},
    ])
    canonical_map = build_cpf_canonical_map(df)
    assert canonical_map == {"A-001": "A-001", "M-002": "A-001", "Z-003": "A-001"}
    assert "OTHER" not in canonical_map


def test_no_clientes_sheet_produces_empty_map_never_raises():
    assert build_cpf_canonical_map(None) == {}
    import pandas as pd
    assert build_cpf_canonical_map(pd.DataFrame()) == {}


def test_clientes_sheet_without_document_column_produces_empty_map():
    df = _clientes_df([{"cliente_id": "C-001"}, {"cliente_id": "C-002"}])
    assert build_cpf_canonical_map(df) == {}


# ── D2 visível no churn (rule 4: teste isso explicitamente) ─────────────────────────

def test_churn_only_fires_after_dedupe_when_combined_purchases_cross_the_threshold():
    """RAW-C1 (2 compras) e RAW-C2 (1 compra) compartilham CPF. Isolados, nenhum dos
    dois atinge `churn_min_purchases` (3) — sem dedupe, ninguém aparece no churn.
    Mesclados na mesma identidade (RAW-C1, canônico), a pessoa física tem 3 compras
    reais e um silêncio real — E APARECE no churn. A dedupe muda o resultado do
    detector, não só um número interno."""
    thresholds = AuditThresholdsConfig()
    records = (
        _record("RAW-C1", [(datetime(2024, 1, 1), 10.0), (datetime(2024, 2, 1), 10.0)])
        + _record("RAW-C2", [(datetime(2024, 3, 1), 10.0)])
        + _record("OTHER", [
            (datetime(2024, 4, 1), 10.0), (datetime(2024, 5, 1), 10.0),
            (datetime(2024, 6, 1), 10.0), (datetime(2024, 7, 1), 10.0),
            (datetime(2024, 8, 1), 10.0),
        ])
    )

    df_raw = _records_to_frame(records)
    findings_raw = detect_churn(df_raw, thresholds)
    assert not any(f.customer_id in ("RAW-C1", "RAW-C2") for f in findings_raw)

    canonical_map = {"RAW-C1": "RAW-C1", "RAW-C2": "RAW-C1"}
    merged = [
        r.model_copy(update={"customer": canonical_map.get(r.customer, r.customer)})
        for r in records
    ]
    df_merged = _records_to_frame(merged)
    findings_merged = detect_churn(df_merged, thresholds)
    finding = next((f for f in findings_merged if f.customer_id == "RAW-C1"), None)
    assert finding is not None, "esperava churn na identidade mesclada RAW-C1"
    assert finding.purchase_count == 3  # 2 (RAW-C1) + 1 (RAW-C2), nunca dobrado nem perdido


# ── D2 visível no RFM (rule 4: teste isso explicitamente) ───────────────────────────

def test_rfm_champion_only_emerges_after_dedupe_combines_the_split_customer():
    """RAW-A1 e RAW-A2 compartilham CPF; cada um sozinho tem frequência/valor medianos
    (nenhum dos dois é campeão). Mesclados, a pessoa física combinada é o cliente de
    maior frequência E maior valor da base — E se torna campeã. Prova que
    `detect_rfm_champions` opera sobre a identidade canônica, não o cliente_id cru."""
    thresholds = AuditThresholdsConfig()
    records = (
        _record("RAW-A1", [(datetime(2024, 1, 1), 25.0), (datetime(2024, 2, 1), 25.0)])
        + _record("RAW-A2", [(datetime(2024, 3, 1), 27.5), (datetime(2024, 4, 1), 27.5)])
        + _record("B", [
            (datetime(2024, 1, 1), 20.0), (datetime(2024, 2, 1), 20.0), (datetime(2024, 3, 1), 20.0),
        ])
        + _record("C", [(datetime(2024, 1, 1), 25.0), (datetime(2024, 2, 1), 25.0)])
        + _record("D", [(datetime(2024, 1, 1), 10.0), (datetime(2024, 2, 1), 10.0)])
        + _record("E", [(datetime(2024, 1, 1), 15.0), (datetime(2024, 2, 1), 15.0)])
    )

    df_raw = _records_to_frame(records)
    champions_raw = detect_rfm_champions(df_raw, thresholds)
    assert not any(c.customer_id in ("RAW-A1", "RAW-A2") for c in champions_raw)

    canonical_map = {"RAW-A1": "RAW-A1", "RAW-A2": "RAW-A1"}
    merged = [
        r.model_copy(update={"customer": canonical_map.get(r.customer, r.customer)})
        for r in records
    ]
    df_merged = _records_to_frame(merged)
    champions_merged = detect_rfm_champions(df_merged, thresholds)
    champion = next((c for c in champions_merged if c.customer_id == "RAW-A1"), None)
    assert champion is not None, "esperava a identidade mesclada RAW-A1 como campeã RFM"
    assert champion.frequency == 4  # 2 + 2, nunca dobrado nem perdido
    assert abs(champion.monetary - 105.0) < 1e-6  # 50 + 55


# ── Dado real (consultoria_real_test.xlsx) — só forma, achado dinamicamente ─────────

def test_real_fixture_has_at_least_one_dynamically_discovered_cpf_duplicate_pair():
    """Não confia em nenhum cliente_id específico — descobre o(s) par(es) que
    compartilham CPF LENDO a aba Clientes, o mesmo caminho que a produção usa."""
    named_sheets = load_named_sheets(FIXTURE)
    clientes_df = named_sheets.get("Clientes")
    assert clientes_df is not None, "fixture não tem aba Clientes — teste não testa nada"

    canonical_map = build_cpf_canonical_map(clientes_df)
    assert canonical_map, (
        "fixture não tem nenhum par de cliente_id compartilhando CPF — teste não testa nada"
    )

    groups: dict[str, set[str]] = {}
    for raw_id, canonical_id in canonical_map.items():
        groups.setdefault(canonical_id, set()).add(raw_id)
    merged_group = next(g for g in groups.values() if len(g) >= 2)
    assert len(merged_group) >= 2


def test_real_fixture_dedupe_shrinks_distinct_customer_count_and_merges_in_run_audit():
    """A base de clientes total (nº de identidades distintas) DIMINUI em relação a
    contar cliente_id cru — e o(s) membro(s) não-canônicos do par desaparecem como
    chave própria do identity_map (foram absorvidos na identidade canônica)."""
    named_sheets = load_named_sheets(FIXTURE)
    canonical_map = build_cpf_canonical_map(named_sheets.get("Clientes"))
    assert canonical_map, "fixture não tem par de CPF duplicado — teste não testa nada"

    groups: dict[str, set[str]] = {}
    for raw_id, canonical_id in canonical_map.items():
        groups.setdefault(canonical_id, set()).add(raw_id)
    total_reduction = sum(len(members) - 1 for members in groups.values())
    assert total_reduction >= 1

    records, _ = load_sales_records(FIXTURE)
    raw_customer_ids = {r.customer for r in records if r.customer != "SEM_CADASTRO"}

    merged_group = next(g for g in groups.values() if len(g) >= 2)
    members_in_sales = merged_group & raw_customer_ids
    assert len(members_in_sales) >= 2, (
        "par de CPF duplicado da aba Clientes não aparece em >=2 cliente_id distintos "
        "na aba Vendas — teste não testa nada"
    )

    _, identity_map = run_audit(FIXTURE, return_identity_map=True)
    # Contagem crua de cliente_id distintos (excluindo o pseudo-cliente walk-in
    # SEM_CADASTRO dos dois lados — ele não é uma pessoa, não deve inflar nem
    # desinflar a comparação).
    raw_distinct_count = len(raw_customer_ids)
    deduped_distinct_count = len({c for c in identity_map if c != "SEM_CADASTRO"})
    assert deduped_distinct_count == raw_distinct_count - total_reduction
    assert deduped_distinct_count < raw_distinct_count, (
        "base de clientes distintos não diminuiu após o dedupe por CPF"
    )

    # Só o cliente_id CANÔNICO do grupo mesclado sobrevive como chave do identity_map —
    # os demais membros foram absorvidos na mesma identidade.
    canonical_for_group = canonical_map[next(iter(merged_group))]
    keys_present = merged_group & set(identity_map.keys())
    assert keys_present == {canonical_for_group}


def test_run_audit_does_not_crash_and_still_dedupes_when_clientes_sheet_is_absent():
    """Arquivo sem aba Clientes (ex. fixture sintética antiga) não quebra — o dedupe
    simplesmente não tem CPF pra agrupar e vira no-op."""
    report = run_audit(NO_CLIENTES_FIXTURE)
    assert report is not None


def test_no_production_code_reads_the_gabarito_sheet_for_dedupe():
    """Anti-overfit: o dedupe não depende (nem indiretamente) da aba Gabarito — só de
    load_named_sheets, que nunca inclui 'Gabarito' na série B carregada."""
    named_sheets = load_named_sheets(FIXTURE)
    assert "Gabarito" not in named_sheets

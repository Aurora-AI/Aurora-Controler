"""
Testes de src/product_b/oracle/commercial_auditor.py — motor determinístico dos 4 detectores +
pseudo-anonimização.

FASE RED (TDD): estes testes devem FALHAR agora (ModuleNotFoundError). Rodam contra
`sales_history_test.xlsx`, que tem 4 anomalias PLANTADAS e conhecidas (ver
tests/fixtures/create_audit_test_workbook.py para o modelo exato):

  1. Vazamento de receita em 2024-08 (mês de índice 19), forçado a 15% do esperado.
  2. Churn crônico: "Cliente Alpha Ltda" compra até 2024-06 e depois some por 6 meses.
  3. Produto descolado: "Adaptador USB" cai enquanto a empresa cresce, última venda em
     2024-08.
  4. Moeda suja: toda a coluna de valor é texto "R$ X.XXX,XX" (testado indiretamente —
     se a coerção falhasse, nenhum detector encontraria nada).

Os valores esperados são computados a partir do MESMO modelo determinístico do gerador
da fixture (importado diretamente), nunca hardcoded em duplicata — se o modelo da fixture
mudar, os testes continuam corretos.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

from datetime import datetime

from product_b.oracle.forensic_contracts import AuditThresholdsConfig, SalesRecord
from product_b.oracle.commercial_auditor import (
    anonymize_customers, load_sales_records, run_audit,
)

from tests.fixtures.create_audit_test_workbook import (  # noqa: E402 — importa o modelo de verdade da fixture
    CHURN_LAST_ACTIVE_MONTH_INDEX, CUSTOMERS, LEAK_MONTH_INDEX, MONTHS,
    _adaptador_usb, _cabo_hdmi, _filtro_ar,
)

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sales_history_test.xlsx"

_LEAK_YEAR, _LEAK_MONTH = MONTHS[LEAK_MONTH_INDEX]
_LEAK_PERIOD = f"{_LEAK_YEAR}-{_LEAK_MONTH:02d}"

_CHURN_YEAR, _CHURN_MONTH = MONTHS[CHURN_LAST_ACTIVE_MONTH_INDEX]
_CHURN_LAST_PURCHASE_PERIOD = f"{_CHURN_YEAR}-{_CHURN_MONTH:02d}"


# ── Ingestão + limpeza ──────────────────────────────────────────────────────────────

def test_load_sales_records_coerces_dirty_currency_and_dates():
    records, summary = load_sales_records(FIXTURE)
    assert len(records) == 258
    assert summary.rows_read == 258
    assert summary.rows_accepted == 258
    # Nenhum valor deve ter sobrado como string — todos os SalesRecord têm .value float.
    assert all(isinstance(r.value, float) for r in records)


def test_load_sales_records_reports_source_traceability():
    records, _ = load_sales_records(FIXTURE)
    assert records[0].source_file == "sales_history_test.xlsx"
    assert records[0].source_row >= 2  # linha 1 é cabeçalho


# ── Detector 1: vazamento de receita ────────────────────────────────────────────────

def test_detect_revenue_leak_finds_the_planted_drop():
    report = run_audit(FIXTURE, thresholds=AuditThresholdsConfig())
    total_leaks = [a for a in report.revenue_leaks if a.scope == "total"]
    assert any(a.period == _LEAK_PERIOD for a in total_leaks), (
        f"esperava um vazamento de receita total em {_LEAK_PERIOD}"
    )
    leak = next(a for a in total_leaks if a.period == _LEAK_PERIOD)
    assert leak.actual_value < leak.expected_value
    assert leak.drop_sigma >= AuditThresholdsConfig().revenue_drop_sigma


def test_revenue_leak_severity_is_high_for_a_dramatic_drop():
    report = run_audit(FIXTURE)
    leak = next(a for a in report.revenue_leaks
                if a.scope == "total" and a.period == _LEAK_PERIOD)
    assert leak.severity == "high"


# ── Detector 2: churn invisível ──────────────────────────────────────────────────────

def test_detect_churn_finds_the_planted_chronic_churn_customer():
    report = run_audit(FIXTURE)
    churned_ids = {f.customer_id for f in report.churn_findings}
    # Neste ponto o resultado já está pseudo-anonimizado — verificamos via identity_map.
    assert len(report.churn_findings) >= 1
    finding = report.churn_findings[0]
    assert finding.last_purchase.startswith(_CHURN_LAST_PURCHASE_PERIOD)
    assert finding.months_silent >= 2 * AuditThresholdsConfig().churn_cadence_multiplier


def test_regular_customers_are_not_flagged_as_churned():
    """Beta/Gama/Delta compram nos 24 meses inteiros — não devem aparecer como churn."""
    report = run_audit(FIXTURE)
    # Exatamente 1 cliente (o Alpha, plantado) deve ser sinalizado.
    assert len(report.churn_findings) == 1


# ── Detector 3: tendência de produto descolado ──────────────────────────────────────

def test_detect_product_trend_flags_the_decoupled_product():
    report = run_audit(FIXTURE)
    usb_entry = next(t for t in report.product_trends if t.product == "Adaptador USB")
    assert usb_entry.decoupled is True
    assert usb_entry.product_growth_pct < 0
    assert usb_entry.company_growth_pct > 0


def test_stable_growing_products_are_not_flagged_as_decoupled():
    report = run_audit(FIXTURE)
    hdmi_entry = next(t for t in report.product_trends if t.product == "Cabo HDMI")
    assert hdmi_entry.decoupled is False


# ── Detector 4: sazonalidade ─────────────────────────────────────────────────────────

def test_seasonality_is_computed_with_24_months_of_history():
    """24 meses > seasonality_min_months (12) — não deve reportar dados insuficientes."""
    report = run_audit(FIXTURE)
    total_curve = next(s for s in report.seasonality if s.scope == "total")
    assert total_curve.insufficient_data is False
    assert total_curve.monthly_index is not None
    assert len(total_curve.monthly_index) == 12  # um índice por mês-do-ano


# ── Pseudo-anonimização (blindagem PII exigida pelo CSO) ────────────────────────────

def test_anonymize_customers_produces_stable_deterministic_pseudonyms():
    records, _ = load_sales_records(FIXTURE)
    _, identity_map = anonymize_customers(records)
    assert set(identity_map.keys()) == set(CUSTOMERS)
    assert all(v.startswith("Client_") for v in identity_map.values())
    # Determinismo: rodar de novo produz o MESMO mapa (reprodutibilidade).
    _, identity_map_2 = anonymize_customers(records)
    assert identity_map == identity_map_2


def test_executive_audit_report_json_never_contains_real_customer_names():
    """Asserção anti-regressão crítica: o artefato que viajará à nuvem (OS 2) NUNCA
    pode conter nomes reais de clientes — só os pseudônimos Client_A, Client_B..."""
    report = run_audit(FIXTURE)
    report_json = report.model_dump_json()
    for real_name in CUSTOMERS:
        assert real_name not in report_json, (
            f"vazamento de PII: '{real_name}' apareceu no ExecutiveAuditReport serializado"
        )


def test_run_audit_returns_identity_map_separately_from_the_report():
    """O identity_map (nomes reais) deve ser um artefato SEPARADO do report — nunca
    embutido nele, para que só o report seja enviado à nuvem na OS 2."""
    result = run_audit(FIXTURE, return_identity_map=True)
    report, identity_map = result
    assert isinstance(identity_map, dict)
    assert "Cliente Alpha Ltda" in identity_map
    assert "Cliente Alpha Ltda" not in report.model_dump_json()


def test_anonymize_scales_beyond_26_customers():
    """Regressão: a fixture de ótica (200 clientes) expôs um IndexError em
    string.ascii_uppercase[i] para i >= 26. Os pseudônimos devem escalar (A..Z, AA, AB...)."""
    records = [
        SalesRecord(
            date=datetime(2024, 1, 1), product="X", customer=f"Cliente {i:03d}",
            value=float(i + 1), quantity=1, source_file="f.xlsx", source_row=i + 2,
        )
        for i in range(30)  # > 26 força o caso que estourava antes
    ]
    _, identity_map = anonymize_customers(records)
    assert len(identity_map) == 30
    assert all(v.startswith("Client_") for v in identity_map.values())
    assert len(set(identity_map.values())) == 30  # pseudônimos únicos
    # O 27º pseudônimo (índice 26) deve ser "Client_AA".
    assert "Client_AA" in identity_map.values()

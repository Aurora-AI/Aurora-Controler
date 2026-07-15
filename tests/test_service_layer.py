"""
Testes de regressão — Bloco SVC (camada de serviço), partes mecânicas implementadas
diretamente nesta sessão: segregação de categoria (RFM/margem de produto não podem
ser poluídas por linha de serviço) e reconciliação Financeiro × Vendas.

A decomposição produto×serviço + flag de mascaramento + efeito follow-on/CAC
(detect_service_decomposition) tem verificação adversarial dedicada — ver
tests/test_service_decomposition_adversarial.py (gerado pelo workflow).
"""
import datetime as dt

from oracle.commercial_auditor import (
    _records_to_frame, detect_contribution_margin, detect_rfm_champions,
    detect_service_reconciliation,
)
from oracle.forensic_contracts import AuditThresholdsConfig, SalesRecord


def _record(date, customer, category, value=200.0, entry_cost=100.0, store="L1"):
    return SalesRecord(
        date=date, product="SERV-001" if category == "servico" else "PROD-1",
        customer=customer, value=value, entry_cost=entry_cost, category=category,
        store=store, salesperson=None, source_file="x", source_row=1,
    )


def test_rfm_ignores_service_only_customer():
    """Cliente que só vem pra serviço não vira campeão de produto — RFM é sobre
    comportamento de compra de produto."""
    th = AuditThresholdsConfig()
    records = []
    # 5 clientes-produto de verdade (pra RFM ter quintil com sinal).
    for i in range(5):
        for j in range(6):
            records.append(_record(
                dt.datetime(2024, 1, 1) + dt.timedelta(days=j * 60), f"PRODC{i}",
                "lente", value=800.0,
            ))
    # 1 cliente que SÓ compra serviço, com frequência/valor altos — não pode aparecer.
    service_only_customer = "SERVICE-ONLY"
    for j in range(20):
        records.append(_record(
            dt.datetime(2024, 1, 1) + dt.timedelta(days=j * 10), service_only_customer,
            "servico", value=5000.0,
        ))
    df = _records_to_frame(records)
    champions = detect_rfm_champions(df, th)
    assert all(c.customer_id != service_only_customer for c in champions)


def test_contribution_margin_excludes_service_category():
    """Serviço com margem negativa não pode aparecer como alerta de margem de
    produto — tem sua própria vista em detect_service_decomposition."""
    th = AuditThresholdsConfig()
    records = [
        _record(dt.datetime(2024, 1, 1) + dt.timedelta(days=i), "C1", "servico",
                value=50.0, entry_cost=100.0)  # margem negativa, é serviço
        for i in range(5)
    ]
    df = _records_to_frame(records)
    alerts = detect_contribution_margin(df, th)
    assert all(a.product != "SERV-001" for a in alerts)


def test_service_reconciliation_flags_gap_when_financeiro_has_no_matching_sales():
    """Loja com receita_servicos declarada no Financeiro mas ZERO venda de serviço
    correspondente naquele mês tem gap sinalizado."""
    import pandas as pd
    th = AuditThresholdsConfig()
    records = [
        _record(dt.datetime(2024, 1, 15), "C1", "lente", store="L1 - Centro"),
    ]
    df = _records_to_frame(records)
    financeiro = pd.DataFrame({
        "mes": ["2024-01"], "loja": ["L1 - Centro"], "receita_servicos": ["9000.00"],
    })
    findings = detect_service_reconciliation(df, financeiro, th)
    assert len(findings) == 1
    assert findings[0].has_gap
    assert findings[0].sales_transactional_revenue == 0.0
    assert abs(findings[0].gap - 9000.0) < 0.01


def test_service_reconciliation_no_gap_when_sales_match_financeiro_exactly():
    """Quando a soma transacional de serviço bate com o declarado, sem gap."""
    import pandas as pd
    th = AuditThresholdsConfig()
    records = [
        _record(dt.datetime(2024, 1, 5), "C1", "servico", value=300.0, store="L1 - Centro"),
        _record(dt.datetime(2024, 1, 20), "C2", "servico", value=200.0, store="L1 - Centro"),
    ]
    df = _records_to_frame(records)
    financeiro = pd.DataFrame({
        "mes": ["2024-01"], "loja": ["L1 - Centro"], "receita_servicos": ["500.00"],
    })
    findings = detect_service_reconciliation(df, financeiro, th)
    assert len(findings) == 1
    assert not findings[0].has_gap
    assert findings[0].sales_transactional_revenue == 500.0


def test_service_reconciliation_empty_without_financeiro_sheet():
    th = AuditThresholdsConfig()
    df = _records_to_frame([_record(dt.datetime(2024, 1, 1), "C1", "lente")])
    assert detect_service_reconciliation(df, None, th) == []


def test_real_fixture_reconciliation_matches_l7_l8_l6_post_2025_08_exactly():
    """Regressão contra o dado real (pós-correção da planilha): L6/L7/L8 reconciliam
    ao centavo a partir de 2025-08 (POS passou a capturar serviço). A correção também
    zerou a receita de serviço fantasma que o Financeiro declarava para as demais 7
    lojas (ex. L1-Centro), então hoje o gap é residual (2 pares em toda a rede) em vez
    de sistêmico — ver test_real_fixture_reconciliation_gap_is_residual_after_correction."""
    from pathlib import Path
    from oracle.commercial_auditor import run_audit

    report = run_audit(Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx")
    by_store_period = {(r.store, r.period): r for r in report.service_reconciliation}

    reconciled = by_store_period.get(("L7 - Oeste", "2025-08"))
    assert reconciled is not None
    assert not reconciled.has_gap
    assert reconciled.sales_transactional_revenue > 0

    non_service_store = by_store_period.get(("L1 - Centro", "2024-06"))
    assert non_service_store is not None
    assert not non_service_store.has_gap
    assert non_service_store.financial_declared_revenue == 0.0


def test_real_fixture_reconciliation_gap_is_residual_after_correction():
    """A correção na planilha fechou o gap sistêmico (era 235 de 267 meses-loja);
    hoje sobra gap residual em só 2 pares de toda a rede."""
    from pathlib import Path
    from oracle.commercial_auditor import run_audit

    report = run_audit(Path(__file__).parent / "fixtures" / "consultoria_real_test.xlsx")
    gapped = [r for r in report.service_reconciliation if r.has_gap]
    assert len(gapped) == 2
    assert {(r.store, r.period) for r in gapped} == {
        ("L7 - Oeste", "2026-06"), ("L8 - Praia", "2026-03"),
    }

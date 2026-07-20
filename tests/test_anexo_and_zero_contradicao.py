# -*- coding: utf-8 -*-
"""
Testes de regressão — Fase D2: D1 (build_anexo, formatador determinístico do
audit_report congelado) e D3 (validador Zero Contradição, Pilar 4).

build_laudo.py não é um pacote instalado — os testes importam por caminho de
arquivo (mesmo padrão que o próprio script usa pra importar o motor sob demanda).
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parent.parent / "laudo_executivo" / "build_laudo.py"
spec = importlib.util.spec_from_file_location("build_laudo", MODULE_PATH)
build_laudo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_laudo)


def _report(**overrides):
    base = {
        "generated_at": "2026-07-20T00:00:00+00:00",
        "thresholds": {"provenance_sample_cap": 10},
        "cleaning": {"rows_read": 100, "rows_accepted": 100, "rows_discarded_by_reason": {},
                     "files_skipped": [], "values_winsorized": []},
        "dead_stock": [{
            "capital_frozen": 5101.24, "sku_count": 2, "dead_stock_months": 8,
            "total_inventory_value": 20000.0, "dead_stock_pct": 25.5,
            "skus": ["SOL-030", "SOL-031"],
            "sku_capital": {"SOL-030": 2532.60, "SOL-031": 2568.64},
            "sku_months_since": {"SOL-030": 9, "SOL-031": 10},
            "sku_descriptions": {"SOL-030": "Óculos Solar Polarizado A", "SOL-031": "Óculos Solar Polarizado B"},
            "sku_source_rows": {"SOL-030": [13], "SOL-031": [14]},
        }],
        "churn_findings": [
            {"customer_id": "Client_A", "purchase_count": 4, "avg_cadence_days": 30.0,
             "last_purchase": "2026-05-01", "months_silent": 3, "historical_annual_value": 1000.0,
             "source_rows": [10, 11], "days_since_last": 70, "silence_to_cycle_ratio": 2.33},
            {"customer_id": "Client_B", "purchase_count": 3, "avg_cadence_days": 100.0,
             "last_purchase": "2026-01-01", "months_silent": 6, "historical_annual_value": 5000.0,
             "source_rows": [20], "days_since_last": 350, "silence_to_cycle_ratio": 3.5},
        ],
        "salesperson_performance": [
            {"salesperson": "V-01", "total_revenue": 10000.0, "sample_size": 50,
             "capture_rate_pct": 90.0, "low_capture_flag": False,
             "days_since_first_sale": 400, "has_sufficient_tenure": True, "low_volume_flag": False},
        ],
        "advanced_metrics": {
            "seller_margin_mix": [{
                "salesperson": "V-01", "store": "L1", "total_revenue": 10000.0,
                "seller_margin_pct": 20.0, "store_margin_pct": 40.0, "margin_gap_pp": 20.0,
                "is_margin_destructive": True, "sample_size": 50,
                "mix": [{"category": "entrada", "seller_revenue": 8000.0, "seller_mix_pct": 80.0,
                          "store_mix_pct": 30.0, "mix_deviation_pp": 50.0, "category_margin_pct": 5.0}],
                "sample_source_rows": [100, 101],
            }],
            "seller_margin_corrosion": [{
                "salesperson": "V-01", "store": "L1", "total_revenue": 10000.0,
                "total_discount": 500.0, "discount_pct": 5.0, "store_mean_discount_pct": 4.0,
                "store_std_discount_pct": 1.0, "sample_size": 50, "is_corrosive": False,
                "tainted_by_triage": False, "sample_source_rows": [100, 101],
            }],
            "discrepancy_triage": {
                "triggered_count": 1, "manual_queue": [],
                "auto_classified": [{
                    "id": "DTQ-0001", "sku": "ARP-013", "sku_description": "Armação Grife Titânio",
                    "store": "L1", "salesperson": "V-01", "source_rows": [189, 526],
                    "practiced_price": 300.0, "list_price": 890.0, "entry_cost": 320.0, "nf_cost": 150.0,
                    "discount_over_list_pct": 66.0,
                    "evidence": {"below_cost": True, "sku_in_dead_stock": False, "is_promo_flagged": False,
                                 "cost_diverges_from_nf": True, "store_systemic_pattern": False},
                    "verdict": "suspected_cadastral_error", "status": "auto_classified",
                }],
            },
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------- build_anexo


def test_build_anexo_estoque_parado_names_the_skus():
    anexo = build_laudo.build_anexo(_report())
    itens = anexo["estoque_parado"]["itens"]
    assert {i["sku"] for i in itens} == {"SOL-030", "SOL-031"}
    sol030 = next(i for i in itens if i["sku"] == "SOL-030")
    assert sol030["descricao"] == "Óculos Solar Polarizado A"
    assert sol030["capital_preso"] == pytest.approx(2532.60)
    assert sol030["meses_parado"] == 9
    assert "13" in sol030["src"]


def test_build_anexo_estoque_total_matches_sum():
    anexo = build_laudo.build_anexo(_report())
    itens = anexo["estoque_parado"]["itens"]
    assert sum(i["capital_preso"] for i in itens) == pytest.approx(anexo["estoque_parado"]["total"])
    assert anexo["estoque_parado"]["total"] == pytest.approx(5101.24)


def test_build_anexo_fila_reativacao_orders_by_heat_not_money():
    anexo = build_laudo.build_anexo(_report())
    itens = anexo["fila_reativacao"]["itens"]
    # Client_A (ratio 2.33, R$1000) mais quente que Client_B (ratio 3.5, R$5000)
    assert [i["cliente"] for i in itens] == ["Client_A", "Client_B"]
    assert anexo["fila_reativacao"]["total"] == pytest.approx(6000.0)
    assert anexo["fila_reativacao"]["clientes"] == 2


def test_build_anexo_vendedores_carries_gap_and_evidence():
    anexo = build_laudo.build_anexo(_report())
    v = anexo["vendedores"]["itens"][0]
    assert v["vendedor"] == "V-01"
    assert "destroi_margem" in v["flags"]
    assert v["gap_pp"] == pytest.approx(20.0)
    assert v["mix_top_desvio"]["categoria"] == "entrada"


def test_build_anexo_vendedores_tainted_gets_absolution_note():
    report = _report()
    report["advanced_metrics"]["seller_margin_corrosion"][0]["tainted_by_triage"] = True
    report["advanced_metrics"]["seller_margin_corrosion"][0]["is_corrosive"] = False
    anexo = build_laudo.build_anexo(report)
    v = anexo["vendedores"]["itens"][0]
    assert any("cadastr" in n for n in v["notas"])
    # duas verdades convivem: continua com o gap de margem visível
    assert v["gap_pp"] == pytest.approx(20.0)


def test_build_anexo_triagem_translates_evidence_to_sentences():
    anexo = build_laudo.build_anexo(_report())
    item = anexo["triagem_discrepancias"]["itens"][0]
    assert item["sku"] == "ARP-013"
    assert item["descricao"] == "Armação Grife Titânio"
    assert item["veredito"] == "suspected_cadastral_error"
    assert any("nota fiscal" in e or "nota" in e for e in item["evidencias"])
    assert "189" in item["src"] and "526" in item["src"]


def test_build_anexo_missing_dead_stock_omits_section():
    anexo = build_laudo.build_anexo(_report(dead_stock=[]))
    assert "estoque_parado" not in anexo


def test_build_anexo_source_sample_is_capped_and_declared():
    report = _report()
    report["churn_findings"][0]["source_rows"] = list(range(2, 30))  # 28 linhas, acima do teto
    anexo = build_laudo.build_anexo(report, cap=10)
    src = next(i for i in anexo["fila_reativacao"]["itens"] if i["cliente"] == "Client_A")["src"]
    assert "+18" in src  # 28 - 10 mostradas


# ------------------------------------------------------------------ D3 sintático


def _audit_data_base():
    return {
        "rodada": "teste", "cliente": "Cliente Teste",
        "manchete": {"total_risco_display": "R$ 6 mil",
                     "frase": "teste", "composicao": "fato medido"},
        "paradoxo": {"loja": "L1", "produto": -100.0, "servico": 200.0, "total": 100.0,
                     "controle": {"loja": "L2", "frase": "controle", "produto": -50.0}},
        "sangramentos": [
            {"id": "cap-a", "titulo": "A", "valor_display": "R$ 1", "soco": "x",
             "evidencias": ["e1"], "custo_mensal": "y", "gancho": "z"},
            {"id": "cap-b", "titulo": "B", "valor_display": "R$ 1", "soco": "x",
             "evidencias": ["e1"], "custo_mensal": "y", "gancho": "z"},
            {"id": "cap-c", "titulo": "C", "valor_display": "R$ 1", "soco": "x",
             "evidencias": ["e1"], "custo_mensal": "y", "gancho": "z"},
        ],
        "honestidade": [{"alarme": "a", "motivo": "m"}],
        "plano": [{"acao": "a", "impacto": 1.0, "impacto_display": "R$1", "cenario": False, "como": "c"}],
        "cta": "falar",
        "procedencia": "fato",
    }


def test_valida_reprova_mencao_a_anexo_sem_report():
    build_laudo.ERROS.clear()
    dados = _audit_data_base()
    dados["sangramentos"][0]["gancho"] = "ver detalhamento no anexo"
    build_laudo.valida(dados)
    build_laudo.valida_anexo_sintatico(dados, anexo_gerado=None)
    assert any("16.1" in e for e in build_laudo.ERROS)


def test_valida_aceita_mencao_a_anexo_com_report_e_ref_valida():
    build_laudo.ERROS.clear()
    dados = _audit_data_base()
    dados["sangramentos"][0]["gancho"] = "ver detalhamento no anexo"
    dados["sangramentos"][0]["anexo_ref"] = "estoque_parado"
    anexo = {"estoque_parado": {"total": 1.0, "itens": []}}
    build_laudo.valida(dados)
    build_laudo.valida_anexo_sintatico(dados, anexo_gerado=anexo)
    assert not any("16.1" in e for e in build_laudo.ERROS)


def test_valida_reprova_anexo_ref_orfao():
    build_laudo.ERROS.clear()
    dados = _audit_data_base()
    dados["sangramentos"][0]["anexo_ref"] = "secao_que_nao_existe"
    anexo = {"estoque_parado": {"total": 1.0, "itens": []}}
    build_laudo.valida(dados)
    build_laudo.valida_anexo_sintatico(dados, anexo_gerado=anexo)
    assert any("16.1" in e for e in build_laudo.ERROS)


def test_valida_sem_mencao_a_anexo_nao_exige_nada():
    build_laudo.ERROS.clear()
    dados = _audit_data_base()
    build_laudo.valida(dados)
    build_laudo.valida_anexo_sintatico(dados, anexo_gerado=None)
    assert not any("16.1" in e for e in build_laudo.ERROS)


# --------------------------------------------------------------- D3 semântico-numérico


def test_z1_estoque_diverge_entre_card_e_anexo_reprova():
    build_laudo.ERROS.clear()
    dados = _audit_data_base()
    dados["sangramentos"][0]["anexo_ref"] = "estoque_parado"
    dados["sangramentos"][0]["valor"] = 999.0  # card diz 999
    anexo = {"estoque_parado": {"total": 500.0, "itens": [
        {"sku": "X", "capital_preso": 500.0},
    ]}}  # anexo diz 500 — diverge
    build_laudo.valida_zero_contradicao(dados, anexo, report=None)
    assert any("Z1" in e for e in build_laudo.ERROS)


def test_z1_itens_do_anexo_nao_somam_o_total_declarado_reprova():
    build_laudo.ERROS.clear()
    anexo = {"estoque_parado": {"total": 500.0, "itens": [
        {"sku": "X", "capital_preso": 100.0}, {"sku": "Y", "capital_preso": 100.0},
    ]}}  # soma 200, total declarado 500
    build_laudo.valida_zero_contradicao({}, anexo, report=None)
    assert any("Z1" in e for e in build_laudo.ERROS)


def test_z1_consistente_nao_reprova():
    build_laudo.ERROS.clear()
    dados = {"sangramentos": [{"anexo_ref": "estoque_parado", "valor": 200.0, "titulo": "X"}]}
    anexo = {"estoque_parado": {"total": 200.0, "itens": [
        {"sku": "X", "capital_preso": 100.0}, {"sku": "Y", "capital_preso": 100.0},
    ]}}
    build_laudo.valida_zero_contradicao(dados, anexo, report=None)
    assert build_laudo.ERROS == []


def test_z4_manchete_nao_bate_soma_dos_sangramentos_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "manchete": {"total_risco": 999.0, "total_risco_display": "R$ 1 mil"},
        "sangramentos": [{"valor": 100.0}, {"valor": 100.0}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert any("Z4" in e for e in build_laudo.ERROS)


def test_z4_manchete_consistente_nao_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "manchete": {"total_risco": 200.0, "total_risco_display": "R$ 200"},
        "sangramentos": [{"valor": 100.0}, {"valor": 100.0}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert build_laudo.ERROS == []


def test_z4_display_inflado_acima_do_fato_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "manchete": {"total_risco": 69038.22, "total_risco_display": "R$ 200 mil"},  # infla
        "sangramentos": [{"valor": 69038.22}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert any("Z4" in e for e in build_laudo.ERROS)


def test_z4_display_truncado_para_baixo_nao_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "manchete": {"total_risco": 69038.22, "total_risco_display": "R$ 69 mil"},  # trunca, não infla
        "sangramentos": [{"valor": 69038.22}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert build_laudo.ERROS == []


def test_z5_plano_desalinhado_do_sangramento_vinculado_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "sangramentos": [{"anexo_ref": "estoque_parado", "valor": 500.0, "titulo": "X"}],
        "plano": [{"impacto": 999.0, "sangramento_ref": "estoque_parado"}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert any("Z5" in e for e in build_laudo.ERROS)


def test_z6_contagem_da_fila_diverge_do_detalhamento_reprova():
    build_laudo.ERROS.clear()
    anexo = {"fila_reativacao": {"total": 100.0, "clientes": 5, "itens": [
        {"cliente": "A", "valor_historico": 100.0},
    ]}}
    build_laudo.valida_zero_contradicao({}, anexo, report=None)
    assert any("Z6" in e for e in build_laudo.ERROS)


def test_zero_contradicao_cruza_com_audit_report_quando_presente():
    build_laudo.ERROS.clear()
    dados = {"sangramentos": [{"anexo_ref": "estoque_parado", "valor": 500.0, "titulo": "X"}]}
    anexo = {"estoque_parado": {"total": 500.0, "itens": [{"sku": "X", "capital_preso": 500.0}]}}
    report = {"dead_stock": [{"capital_frozen": 999.0}]}  # motor diz outra coisa
    build_laudo.valida_zero_contradicao(dados, anexo, report)
    assert any("Z1" in e and "motor" in e.lower() or "dead_stock" in e for e in build_laudo.ERROS)

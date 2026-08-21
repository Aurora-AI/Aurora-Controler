# -*- coding: utf-8 -*-
"""
Testes de regressão — Fase E parte 1, Parte B: Ato 7 (build_team) e a extensão do
validador Zero Contradição (Z7/Z8).

Mesmo padrão de import de `test_anexo_and_zero_contradicao.py` (build_laudo.py não
é pacote instalado).
"""
import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parent.parent / "laudo_executivo" / "build_laudo.py"
spec = importlib.util.spec_from_file_location("build_laudo", MODULE_PATH)
build_laudo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_laudo)


def _team_report(**overrides):
    base = {
        "team_diagnostics": {
            "flight_risk": [{
                "salesperson": "V-01", "store": "L1", "months_evaluated": 9,
                "capture_trend_pct": 60.0, "discount_trend_pp": None, "ticket_trend_pct": 39.8,
                "risk_flags": ["captura_em_queda", "ticket_em_queda"],
                "carteira_em_risco_brl": 5500.0, "sample_source_rows": [10, 11, 12],
            }],
            "incentive_misalignment": [{
                "salesperson": "V-02", "store": "L1", "commission_basis": "gross_revenue",
                "linked_finding_type": "margin_mix", "linked_finding_summary": "gap de 15.0pp",
                "recommended_fix": "revisar base de comissão",
            }],
            "skill_gaps": [{
                "salesperson": "V-03", "store": "L1", "category": "multifocal",
                "mix_deviation_pp": -15.0, "category_margin_pct": 50.0,
                "hypothesis": "possível déficit de treinamento/segurança técnica em multifocal",
                "is_proxy": True, "data_gap": "conversao_real_requer_aba_orcamentos",
            }],
        },
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------- build_team (D1-style)


def test_build_team_evasao_expoe_chave_estavel_e_carteira():
    team = build_laudo.build_team(_team_report())
    item = team["evasao"]["itens"][0]
    assert item["chave"] == "V-01@L1"
    assert item["vendedor"] == "V-01" and item["loja"] == "L1"
    assert item["carteira_em_risco"] == pytest.approx(5500.0)
    assert set(item["sinais"]) == {"captura_em_queda", "ticket_em_queda"}


def test_build_team_comissionamento_e_habilidade():
    team = build_laudo.build_team(_team_report())
    com = team["comissionamento"]["itens"][0]
    assert com["vendedor"] == "V-02" and com["achado_origem"] == "margin_mix"
    hab = team["habilidade"]["itens"][0]
    assert hab["vendedor"] == "V-03" and hab["e_proxy"] is True
    assert "possível" in hab["hipotese"] or "déficit" in hab["hipotese"]


def test_build_team_secao_ausente_quando_lista_vazia():
    report = _team_report()
    report["team_diagnostics"]["incentive_misalignment"] = []
    team = build_laudo.build_team(report)
    assert "comissionamento" not in team
    assert "evasao" in team and "habilidade" in team


def test_build_team_retorna_vazio_sem_team_diagnostics():
    assert build_laudo.build_team({}) == {}


def test_build_team_respeita_teto_de_amostra():
    report = _team_report()
    report["team_diagnostics"]["flight_risk"][0]["sample_source_rows"] = list(range(2, 30))
    team = build_laudo.build_team(report, cap=5)
    assert "+23" in team["evasao"]["itens"][0]["src"]


# --------------------------------------------------------------- Z7


def test_z7_plano_diverge_do_item_de_evasao_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "team": {"evasao": {"itens": [{"chave": "V-01@L1", "carteira_em_risco": 5500.0}]}},
        "plano": [{"impacto": 9999.0, "team_ref": "V-01@L1"}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert any("Z7" in e for e in build_laudo.ERROS)


def test_z7_consistente_nao_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "team": {"evasao": {"itens": [{"chave": "V-01@L1", "carteira_em_risco": 5500.0}]}},
        "plano": [{"impacto": 5500.0, "team_ref": "V-01@L1"}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert build_laudo.ERROS == []


def test_z7_team_ref_orfao_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "team": {"evasao": {"itens": [{"chave": "V-01@L1", "carteira_em_risco": 5500.0}]}},
        "plano": [{"impacto": 100.0, "team_ref": "V-99@L9"}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert any("Z7" in e and "órfã" in e for e in build_laudo.ERROS)


def test_z7_nao_aciona_sem_team_ref():
    build_laudo.ERROS.clear()
    dados = {"plano": [{"impacto": 100.0, "sangramento_ref": "cap-a"}], "sangramentos": []}
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert build_laudo.ERROS == []


def test_z7_impacto_nulo_nao_crasha():
    build_laudo.ERROS.clear()
    dados = {
        "team": {"evasao": {"itens": [{"chave": "V-01@L1", "carteira_em_risco": 5500.0}]}},
        "plano": [{"impacto": None, "team_ref": "V-01@L1"}],
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)  # não deve lançar
    assert not any("Z7" in e for e in build_laudo.ERROS)


# --------------------------------------------------------------- Z8


def test_z8_mencao_evasao_sem_report_reprova():
    build_laudo.ERROS.clear()
    dados = {"sangramentos": [{"id": "cap-a", "titulo": "X", "soco": "risco de evasão detectado"}]}
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert any("Z8" in e for e in build_laudo.ERROS)


def test_z8_mencao_hipotese_sem_report_reprova():
    build_laudo.ERROS.clear()
    dados = {"sangramentos": [{"id": "cap-a", "titulo": "X", "soco": "uma hipótese de déficit técnico"}]}
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert any("Z8" in e for e in build_laudo.ERROS)


def test_z8_mencao_com_team_gerado_nao_reprova():
    build_laudo.ERROS.clear()
    dados = {
        "sangramentos": [{"id": "cap-a", "titulo": "X", "soco": "risco de evasão detectado"}],
        "team": {"evasao": {"itens": []}},
    }
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert not any("Z8" in e for e in build_laudo.ERROS)


def test_z8_sem_mencao_nao_exige_nada():
    build_laudo.ERROS.clear()
    dados = {"sangramentos": [{"id": "cap-a", "titulo": "X", "soco": "nada relacionado aqui"}]}
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert build_laudo.ERROS == []


def test_z8_capacidade_escalonamento_nao_sao_varridos_ainda():
    # E4/E5 fora desta OS — menção a esses termos NUNCA deve reprovar por Z8
    # (nenhum item de ocupação/escala existe em team ainda).
    build_laudo.ERROS.clear()
    dados = {"sangramentos": [{"id": "cap-a", "titulo": "X",
                                "soco": "vendedor sem capacidade e escalonamento ruim"}]}
    build_laudo.valida_zero_contradicao(dados, anexo=None, report=None)
    assert build_laudo.ERROS == []

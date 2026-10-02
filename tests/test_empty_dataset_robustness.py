"""
Testes de regressão — Bloco A (integridade de dado), item novo achado por QA review:
arquivo com zero linhas de venda, ou onde TODA linha é descartada na limpeza, tem que
produzir um laudo vazio válido (0 achados, sem exceção) — não um crash.

Achado real: nenhum teste do repositório cobria esse cenário antes desta revisão.
run_audit() quebrava com KeyError('date') porque _records_to_frame([]) retornava um
DataFrame sem NENHUMA coluna, e detect_product_trends quebrava com IndexError logo
depois (lista de períodos vazia). cli/main.py:147 já tinha o tratamento amigável
escrito ("Nenhuma linha de venda válida após a limpeza") — mas nunca era alcançado,
porque o crash acontecia uma camada abaixo, dentro do próprio run_audit().

Testa ponta a ponta (run_audit + CLI), não só _records_to_frame isoladamente — o
crash real estava em detect_product_trends, uma camada além da função óbvia.
"""
import subprocess
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

from product_b.oracle.commercial_auditor import run_audit

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_xlsx(tmp_path: Path, df: pd.DataFrame, name: str) -> Path:
    path = tmp_path / name
    df.to_excel(path, index=False, engine="openpyxl")
    return path


def test_zero_rows_produces_empty_report_not_a_crash(tmp_path):
    fixture = _write_xlsx(
        tmp_path, pd.DataFrame(columns=["data", "produto", "cliente", "valor"]), "zero_rows.xlsx",
    )
    report = run_audit(fixture)
    assert report.cleaning.rows_read == 0
    assert report.cleaning.rows_accepted == 0
    assert report.revenue_leaks == []
    assert report.churn_findings == []
    assert report.product_trends == []
    assert report.rfm_champions == []
    assert report.contribution_margin_alerts == []
    assert report.store_performance == []
    assert report.store_macro_summary is None
    assert report.customer_concentration == []


def test_all_rows_discarded_produces_empty_report_not_a_crash(tmp_path):
    fixture = _write_xlsx(
        tmp_path,
        pd.DataFrame({
            "data": ["nao-e-data", "tambem-invalida", ""],
            "produto": ["P1", "P2", "P3"],
            "cliente": ["C1", "C2", "C3"],
            "valor": [100, 200, 300],
        }),
        "all_discarded.xlsx",
    )
    report = run_audit(fixture)
    assert report.cleaning.rows_read == 3
    assert report.cleaning.rows_accepted == 0
    assert report.cleaning.rows_discarded_by_reason.get("data_invalida", 0) == 3
    assert report.revenue_leaks == []
    assert report.product_trends == []


def test_cli_prints_friendly_message_for_zero_rows_not_a_traceback(tmp_path):
    fixture = _write_xlsx(
        tmp_path, pd.DataFrame(columns=["data", "produto", "cliente", "valor"]), "zero_rows.xlsx",
    )
    result = subprocess.run(
        [sys.executable, "-m", "cli.main", "audit", str(fixture), "--out", str(tmp_path / "out")],
        cwd=REPO_ROOT / "src", env={**os.environ, "PYTHONPATH": str(REPO_ROOT), "PYTHONIOENCODING": "utf-8"}, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 1
    assert "Nenhuma linha de venda" in result.stderr
    assert "Traceback" not in result.stderr

"""
ME-6 (OS-EXRS-CRYPTO-SEAL) — Gate: job nunca fica órfão por causa de selagem, no caminho
REAL do worker (não só no orquestrador síncrono testado na ME-5).

A ME-5 já garante que orchestrate_pipeline nunca propaga exceção de selagem (chave ausente
ou erro inesperado): ambas viram evento + trace + `seal=None`, sem levantar. Este teste prova
que essa garantia se sustenta através do `run_compile` do worker — o job transiciona a um
status TERMINAL real (não fica preso em RUNNING, não vira ERROR por causa do selo).
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (
    REPO_ROOT / "src" / "product_a" / "trustware", REPO_ROOT / "src" / "orchestrator",
    REPO_ROOT / "src" / "api", REPO_ROOT / "src" / "worker",
    REPO_ROOT / "src" / "product_a" / "phase_a4",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def test_worker_run_compile_reaches_terminal_status_without_signing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("EXRS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))

    import celery_app
    from jobs import JobStore

    fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"
    store = JobStore()  # usa EXRS_DATA_DIR (tmp_path) por default
    job_id = "worker-seal-no-orphan-1"
    store.create(job_id, "coverage_test.xlsx")

    status = celery_app.run_compile(job_id, str(fixture))

    # Terminal real do orquestrador (PASSED/PARTIAL/FAILED) — nunca RUNNING, nunca ERROR
    # espúrio causado pela ausência de chave de assinatura.
    assert status in {"PASSED", "PARTIAL", "FAILED"}
    persisted = store.get(job_id)
    assert persisted["status"] == status

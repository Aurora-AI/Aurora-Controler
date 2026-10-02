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


def test_worker_run_compile_reaches_terminal_status_without_signing_key(tmp_path, monkeypatch):
    import shutil
    monkeypatch.delenv("EXRS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))

    from worker import celery_app
    from api.jobs import JobStore

    fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"
    store = JobStore()  # usa EXRS_DATA_DIR (tmp_path) por default
    job_id = "worker-seal-no-orphan-1"
    tenant_id = "tenant_seal"
    store.create(job_id, "coverage_test.xlsx", tenant_id=tenant_id)

    upload_dir = tmp_path / tenant_id / job_id / "upload"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target_file = upload_dir / "coverage_test.xlsx"
    shutil.copyfile(fixture, target_file)

    status = celery_app.run_compile(job_id, str(target_file), tenant_id=tenant_id)

    # Terminal real do orquestrador (PASSED/PARTIAL/FAILED) — nunca RUNNING, nunca ERROR
    # espúrio causado pela ausência de chave de assinatura.
    assert status in {"PASSED", "PARTIAL", "FAILED"}
    persisted = store.get(job_id, tenant_id=tenant_id)
    assert persisted["status"] == status

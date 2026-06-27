"""
Gate de broker REAL (ME-6) — roda só em CI/Linux com Redis + worker Celery ativos.

Localmente no Windows este gate é pulado: o caminho host↔Redis-Docker-Desktop sofre reset
10054 e o engine é intermitente. No Linux o worker Celery como processo é estável.

Ativação (no job de broker do CI):
    EXRS_BROKER_E2E=1  EXRS_CELERY_EAGER=0  EXRS_REDIS_URL=redis://localhost:6379/0
(com um worker `celery -A celery_app worker -Q exrs_compile` já rodando)
"""
import os
import sys
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "libs" / "trustware", REPO_ROOT / "src" / "api", REPO_ROOT / "src" / "worker"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

pytestmark = pytest.mark.skipif(
    os.getenv("EXRS_BROKER_E2E") != "1",
    reason="Gate de broker real — requer Redis + worker (EXRS_BROKER_E2E=1, EXRS_CELERY_EAGER=0).",
)


@pytest.mark.broker
def test_compile_via_real_broker():
    """Enfileira via broker real e confirma a transição PENDING→RUNNING→terminal."""
    from jobs import JobStore, TERMINAL_STATUSES
    from celery_app import compile_job, celery_app

    assert celery_app.conf.task_always_eager is False, \
        "broker gate exige EXRS_CELERY_EAGER=0 (modo eager mascararia o broker)"

    store = JobStore()
    job_id = uuid.uuid4().hex
    store.create(job_id, "coverage_test.xlsx")
    fixture = str(REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx")
    compile_job.delay(job_id, fixture)

    seen: list[str] = []
    deadline = time.time() + 60
    while time.time() < deadline:
        status = store.get(job_id)["status"]
        if status not in seen:
            seen.append(status)
        if status in TERMINAL_STATUSES:
            assert "RUNNING" in seen, f"job não passou por RUNNING (broker suspeito): {seen}"
            return
        time.sleep(0.5)
    pytest.fail(f"job não atingiu status terminal via broker em 60s; transições={seen}")

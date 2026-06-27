"""
EXRS — Plano de Execução (ME-6): worker Celery + Redis.

Substitui o agendamento interim por BackgroundTasks. O broker é um Redis DEDICADO do EXRS
(isolado da infra compartilhada dos demais produtos — Regras de Fronteira do CLAUDE.md).

Broker default: redis://localhost:6399/0 (container `exrs-redis`). Override por EXRS_REDIS_URL.
Modo eager (execução inline, sem broker) para testes: EXRS_CELERY_EAGER=1.

Rodar um worker real:
    EXRS_REDIS_URL=redis://localhost:6399/0 \
    uv run celery -A celery_app worker --loglevel=info -Q exrs_compile
(a partir de src/worker/, ou com src/worker no PYTHONPATH)
"""
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for _p in [
    _ROOT / "libs" / "trustware",
    _ROOT / "src" / "orchestrator",
    _ROOT / "src" / "api",
    *[_ROOT / "src" / f"phase_{x}" for x in
      ("a0", "a1", "a1_5", "a2", "a2_5", "a3", "a4", "c0", "c1", "c2", "c3")],
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from celery import Celery

from jobs import JobStore
from storage_manager import StorageManager
from pipeline_orchestrator import orchestrate_pipeline

REDIS_URL = os.getenv("EXRS_REDIS_URL", "redis://localhost:6399/0")

celery_app = Celery("exrs", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.task_default_queue = "exrs_compile"
celery_app.conf.task_always_eager = os.getenv("EXRS_CELERY_EAGER", "0") == "1"
celery_app.conf.task_eager_propagates = True
# Resiliência de conexão (necessário com Redis publicado via Docker no host Windows, onde
# conexões bloqueantes longas sofrem reset 10054). Keepalive + retry no startup.
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.broker_transport_options = {
    "socket_keepalive": True,
    "visibility_timeout": 3600,
}
celery_app.conf.redis_socket_keepalive = True


def run_compile(job_id: str, file_path: str) -> str:
    """
    Corpo do processamento de um job. Independente de Celery — reaproveitável.
    Transiciona o job no store: RUNNING → status terminal do orquestrador.
    """
    from factory_events import emit_event, trace, set_job
    set_job(job_id)  # correlaciona eventos emitidos lá no fundo (ex.: sandbox sem Docker)
    store = JobStore()
    store.update_status(job_id, "RUNNING")
    try:
        storage = StorageManager(job_id)
        result = orchestrate_pipeline(Path(file_path), storage)
        status = result.get("status", "ERROR")
        store.update_status(job_id, status, track=result.get("track"),
                            detail=result.get("reason"))
        return status
    except Exception as e:  # noqa: BLE001 — falha do job NUNCA é silenciosa
        # Proibida falha silenciosa de ferramenta de fábrica: emite evento + trace terminal
        # antes de persistir ERROR. Cobre o caso de um passo (Docker/Redis/IO) LEVANTAR
        # exceção em vez de retornar sentinela.
        detail = f"{type(e).__name__}: {e}"
        emit_event("JOB_EXECUTION_FAILED", job_id=job_id, error=detail)
        trace(job_id, "terminal", status="ERROR", error=detail)
        store.update_status(job_id, "ERROR", detail=detail)
        return "ERROR"


@celery_app.task(name="exrs.compile_job")
def compile_job(job_id: str, file_path: str) -> str:
    return run_compile(job_id, file_path)

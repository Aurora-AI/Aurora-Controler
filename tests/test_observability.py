import json
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_sandbox_unavailable_emits_factory_event(tmp_path, monkeypatch):
    """Docker indisponível → FACTORY_TOOL_UNAVAILABLE (proibida falha silenciosa)."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    from product_a.phase_a4 import runner
    monkeypatch.setattr(runner, "_docker_available", lambda: False)

    result = runner.execute_in_sandbox("def f():\n    return 1\n", "f", {})
    assert "SANDBOX_UNAVAILABLE" in result

    events = _read_jsonl(tmp_path / "factory_events.jsonl")
    assert any(e["event"] == "FACTORY_TOOL_UNAVAILABLE" and e["tool"] == "docker-sandbox"
               for e in events)
    # Evento precisa carregar fallback explícito.
    evt = next(e for e in events if e["event"] == "FACTORY_TOOL_UNAVAILABLE")
    assert evt["fallback"]


def test_orchestrate_emits_per_phase_trace(tmp_path, monkeypatch):
    """O pipeline registra trace por micro-etapa em {job_id}/trace.jsonl."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    from orchestrator.storage_manager import StorageManager
    from orchestrator.pipeline_orchestrator import orchestrate_pipeline

    job_id = uuid.uuid4().hex
    storage = StorageManager(job_id)  # usa EXRS_DATA_DIR
    fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"
    orchestrate_pipeline(fixture, storage)

    trace = _read_jsonl(tmp_path / job_id / "trace.jsonl")
    phases = [t["phase"] for t in trace]
    assert "a0_classify" in phases
    assert "route" in phases
    assert any(t["phase"] == "terminal" for t in trace)  # toda execução fecha com terminal


def test_worker_exception_is_not_silent(tmp_path, monkeypatch):
    """Se um passo do pipeline LEVANTAR, o worker emite evento + trace terminal (não mudo)."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    from worker import celery_app

    def _boom(*a, **k):
        raise RuntimeError("docker socket explodiu")
    monkeypatch.setattr(celery_app, "orchestrate_pipeline", _boom)

    job_id = uuid.uuid4().hex
    from api.jobs import JobStore
    JobStore().create(job_id, "x.xlsx")
    status = celery_app.run_compile(job_id, "/tmp/x.xlsx")
    assert status == "ERROR"

    events = _read_jsonl(tmp_path / "factory_events.jsonl")
    assert any(e["event"] == "JOB_EXECUTION_FAILED" and e["job_id"] == job_id for e in events)
    trace = _read_jsonl(tmp_path / job_id / "trace.jsonl")
    assert any(t["phase"] == "terminal" and t["status"] == "ERROR" for t in trace)


def test_observability_failure_never_orphans_job(tmp_path, monkeypatch):
    """Se a própria escrita de evento falhar, o job ainda é persistido ERROR (nunca RUNNING)."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    from worker import celery_app

    def _boom(*a, **k):
        raise RuntimeError("pipeline quebrou")
    monkeypatch.setattr(celery_app, "orchestrate_pipeline", _boom)
    # observabilidade indisponível (ex.: disco cheio) — run_compile importa emit_event de
    # factory_events em tempo de chamada, então o patch é no módulo de origem.
    from libs.trustware import factory_events
    monkeypatch.setattr(factory_events, "emit_event",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))

    job_id = uuid.uuid4().hex
    from api.jobs import JobStore
    store = JobStore()
    store.create(job_id, "x.xlsx")
    status = celery_app.run_compile(job_id, "/tmp/x.xlsx")
    assert status == "ERROR"
    # O ponto: status terminal persistido apesar da observabilidade ter explodido.
    assert store.get(job_id)["status"] == "ERROR"


def test_sandbox_event_correlates_job_id_via_context(tmp_path, monkeypatch):
    """O evento de sandbox herda o job_id corrente (contextvar), não None."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    from product_a.phase_a4 import runner
    from libs.trustware.factory_events import set_job
    monkeypatch.setattr(runner, "_docker_available", lambda: False)

    set_job("job-corr-123")
    runner.execute_in_sandbox("def f():\n    return 1\n", "f", {})
    set_job(None)

    events = _read_jsonl(tmp_path / "factory_events.jsonl")
    evt = next(e for e in events if e["tool"] == "docker-sandbox")
    assert evt["job_id"] == "job-corr-123"


def test_compile_broker_failure_emits_event_and_503(tmp_path, monkeypatch):
    """Enqueue falho (broker down) → evento + HTTP 503, nunca silencioso."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    from api import main

    def _boom(*a, **k):
        raise ConnectionError("redis down")
    monkeypatch.setattr(main.compile_job, "delay", _boom)

    client = TestClient(main.app)
    fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"
    resp = client.post("/api/v1/compile", files={"file": ("coverage_test.xlsx",
                       fixture.read_bytes(),
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert resp.status_code == 503

    events = _read_jsonl(tmp_path / "factory_events.jsonl")
    assert any(e["event"] == "FACTORY_TOOL_UNAVAILABLE" and e["tool"] == "redis-broker"
               for e in events)

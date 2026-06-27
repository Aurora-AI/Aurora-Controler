import json
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "libs" / "trustware", REPO_ROOT / "src" / "orchestrator",
           REPO_ROOT / "src" / "api", REPO_ROOT / "src" / "phase_a4", REPO_ROOT / "src" / "worker"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_sandbox_unavailable_emits_factory_event(tmp_path, monkeypatch):
    """Docker indisponível → FACTORY_TOOL_UNAVAILABLE (proibida falha silenciosa)."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    import runner
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
    from storage_manager import StorageManager
    from pipeline_orchestrator import orchestrate_pipeline

    job_id = uuid.uuid4().hex
    storage = StorageManager(job_id)  # usa EXRS_DATA_DIR
    fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"
    orchestrate_pipeline(fixture, storage)

    trace = _read_jsonl(tmp_path / job_id / "trace.jsonl")
    phases = [t["phase"] for t in trace]
    assert "a0_classify" in phases
    assert "route" in phases
    assert any(t["phase"] == "terminal" for t in trace)  # toda execução fecha com terminal


def test_compile_broker_failure_emits_event_and_503(tmp_path, monkeypatch):
    """Enqueue falho (broker down) → evento + HTTP 503, nunca silencioso."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    import main

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

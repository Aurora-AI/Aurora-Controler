"""
EXRS — Observabilidade de fábrica (ME-7).

Emissão determinística (não-LLM) de eventos e traces. Dois destinos:
- factory_events.jsonl (nível fábrica): eventos como FACTORY_TOOL_UNAVAILABLE.
- {job_id}/trace.jsonl (nível job): trace por micro-etapa (A0→A4 / track).

Princípio (CLAUDE.md): nenhuma indisponibilidade de ferramenta de fábrica é silenciosa —
toda falha de Docker/broker gera evento + fallback explícito. Append-only, sem dependências
externas. O destino respeita EXRS_DATA_DIR (compartilhado entre host e worker).
"""
import contextvars
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Job corrente da execução — permite correlacionar eventos emitidos no fundo da cadeia
# (ex.: sandbox sem Docker em runner.py) sem threadar job_id por toda a assinatura.
_current_job: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "exrs_current_job", default=None
)


def set_job(job_id: str | None) -> None:
    _current_job.set(job_id)


def _data_dir() -> Path:
    return Path(os.getenv("EXRS_DATA_DIR", "output"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def emit_event(event_type: str, **fields) -> dict:
    """Registra um evento de nível fábrica em factory_events.jsonl."""
    record = {"ts": _now(), "event": event_type, **fields}
    _append(_data_dir() / "factory_events.jsonl", record)
    return record


def factory_tool_unavailable(tool: str, detail: str, fallback: str,
                             job_id: str | None = None) -> dict:
    """Evento canônico de indisponibilidade de ferramenta de fábrica (com fallback explícito)."""
    return emit_event(
        "FACTORY_TOOL_UNAVAILABLE",
        tool=tool, detail=detail, fallback=fallback,
        job_id=job_id if job_id is not None else _current_job.get(),
    )


def trace(job_id: str, phase: str, status: str = "ok", **extra) -> dict:
    """Registra uma micro-etapa do job em {job_id}/trace.jsonl."""
    record = {"ts": _now(), "job_id": job_id, "phase": phase, "status": status, **extra}
    _append(_data_dir() / job_id / "trace.jsonl", record)
    return record

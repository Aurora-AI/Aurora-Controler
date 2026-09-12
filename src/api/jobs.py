"""
EXRS API — Job Store (Plano de Controle, ME-5)

Persistência durável do estado dos jobs de compilação em SQLite. Sobrevive a restart do
processo (diferente de um dict em memória). O worker (ME-6 — Celery) e o endpoint de status
leem/escrevem aqui.

Estados: PENDING → RUNNING → {PASSED | PARTIAL | FAILED | GATE_REJECTED | NOT_IMPLEMENTED
| ESCALATED | SKIPPED_NO_CACHE | ERROR}
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TERMINAL_STATUSES = {
    "PASSED", "PARTIAL", "FAILED", "GATE_REJECTED",
    "NOT_IMPLEMENTED", "ESCALATED", "SKIPPED_NO_CACHE", "ERROR",
}

_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path(os.getenv("EXRS_DATA_DIR", "output")) / "jobs.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        # check_same_thread=False: FastAPI BackgroundTasks/worker podem usar outra thread.
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id     TEXT PRIMARY KEY,
                    filename   TEXT NOT NULL,
                    status     TEXT NOT NULL,
                    track      TEXT,
                    detail     TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    tenant_id  TEXT NOT NULL DEFAULT 'unassigned_quarantine'
                )
                """
            )
            # Migração de esquema: garante presença da coluna tenant_id se a tabela já existia
            cols = [row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]
            if "tenant_id" not in cols:
                conn.execute("ALTER TABLE jobs ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'unassigned_quarantine'")

    def create(self, job_id: str, filename: str, tenant_id: str) -> None:
        if not _ID_PATTERN.match(job_id):
            raise ValueError(f"Identificador job_id inválido: {job_id}")
        if not _ID_PATTERN.match(tenant_id):
            raise ValueError(f"Identificador tenant_id inválido: {tenant_id}")

        ts = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, filename, status, created_at, updated_at, tenant_id) "
                "VALUES (?, ?, 'PENDING', ?, ?, ?)",
                (job_id, filename, ts, ts, tenant_id),
            )

    def update_status(
        self,
        job_id: str,
        status: str,
        tenant_id: str,
        track: str | None = None,
        detail: Any = None,
    ) -> None:
        if not _ID_PATTERN.match(job_id):
            raise ValueError(f"Identificador job_id inválido: {job_id}")
        if not _ID_PATTERN.match(tenant_id):
            raise ValueError(f"Identificador tenant_id inválido: {tenant_id}")

        with self._connect() as conn:
            row = conn.execute("SELECT tenant_id FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise ValueError(f"Job '{job_id}' não encontrado para atualização.")
            row_tenant = row["tenant_id"]
            if row_tenant != tenant_id:
                raise ValueError(
                    f"Tenant mismatch: job '{job_id}' pertence a '{row_tenant}', "
                    f"tentativa de atualização rejeitada para tenant '{tenant_id}'."
                )

            detail_str = json.dumps(detail, ensure_ascii=False) if detail is not None else None
            conn.execute(
                "UPDATE jobs SET status = ?, track = COALESCE(?, track), "
                "detail = COALESCE(?, detail), updated_at = ? WHERE job_id = ?",
                (status, track, detail_str, _now(), job_id),
            )

    def get(self, job_id: str, tenant_id: str) -> dict | None:
        if not _ID_PATTERN.match(job_id):
            return None
        if not _ID_PATTERN.match(tenant_id):
            return None

        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None

        record = dict(row)
        job_tenant = record.get("tenant_id")

        # Isolamento estrito de tenant (inclui quarentena)
        if job_tenant != tenant_id:
            return None

        if record.get("detail"):
            try:
                record["detail"] = json.loads(record["detail"])
            except json.JSONDecodeError:
                pass
        return record



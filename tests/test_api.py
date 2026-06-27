import sys
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "api",
    REPO_ROOT / "src" / "phase_c1",
    REPO_ROOT / "src" / "phase_c2",
    REPO_ROOT / "src" / "phase_c3",
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dashboard_contracts import (
    C0Dataset, IngestionStrategy, DetectedStructure, ValidationSummary,
)
from main import generate_dashboard, DashboardRequest, health_check

def _c0_fixture() -> C0Dataset:
    return C0Dataset(
        source_file="test_data.csv",
        ingestion_strategy=IngestionStrategy(
            primary="structured_model",
            fallback="grid_scraping",
            used="structured_model",
            reason="flat"
        ),
        detected_structure=DetectedStructure(table_kind="flat"),
        dataset=[
            {"row_id": 1, "cnpj": "00.1/0001-01", "status": "Aprovado", "quantidade": 10.0},
            {"row_id": 2, "cnpj": "00.2/0001-02", "status": "Reprovado", "quantidade": 20.0},
        ],
        source_map=[],
        discarded_rows=[],
        validation_summary=ValidationSummary(
            total_rows_read=2,
            source_rows_emitted=2,
            source_rows_context=0,
            source_rows_discarded=0,
            dataset_rows_emitted=2
        ),
    )

@pytest.mark.anyio
async def test_health_check():
    res = await health_check()
    assert res == {"status": "ok", "service": "Aurora Controler EXRS"}

@pytest.mark.anyio
async def test_generate_dashboard_endpoint():
    req = DashboardRequest(dataset=_c0_fixture(), use_llm=False)
    spec = await generate_dashboard(req)
    
    assert spec.schema_version == "dashboard_spec.v1"
    assert spec.dashboard_id == "dashboard_executivo"
    assert spec.title == "Dashboard - test_data"
    assert len(spec.components) > 0
    assert "summary_kpis" in spec.data_views

def test_upload_and_generate_endpoint():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    csv_data = "cnpj,status,quantidade\n00.1/0001-01,Aprovado,10.0\n00.2/0001-02,Reprovado,20.0\n"
    response = client.post(
        "/api/v1/dashboard/upload-and-generate",
        files={"file": ("test_file.csv", csv_data, "text/csv")}
    )
    assert response.status_code == 200
    res_json = response.json()
    assert "c0_dataset" in res_json
    assert "spec" in res_json

    spec = res_json["spec"]
    assert spec["schema_version"] == "dashboard_spec.v1"
    assert spec["title"] == "Dashboard Executivo - test_file"
    assert len(spec["components"]) > 0


# ─── ME-5: Plano de Controle (compile + jobs) ───────────────────────────────

def _client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_compile_xlsx_reaches_terminal_status():
    from jobs import TERMINAL_STATUSES
    fixture = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"
    client = _client()
    with open(fixture, "rb") as f:
        resp = client.post("/api/v1/compile", files={"file": ("coverage_test.xlsx", f.read(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    assert resp.json()["status"] == "PENDING"

    # BackgroundTasks do TestClient executam antes do retorno → status já terminal.
    status_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert status_resp.status_code == 200
    rec = status_resp.json()
    assert rec["status"] in TERMINAL_STATUSES, f"job preso em {rec['status']}"


def test_compile_csv_routes_to_not_implemented():
    client = _client()
    csv_data = "a,b\n1,2\n"
    resp = client.post("/api/v1/compile", files={"file": ("x.csv", csv_data, "text/csv")})
    job_id = resp.json()["job_id"]
    rec = client.get(f"/api/v1/jobs/{job_id}").json()
    # CSV → track_c → honestamente NÃO implementado (sem PASSED falso).
    assert rec["status"] == "NOT_IMPLEMENTED"


def test_compile_rejects_bad_extension():
    client = _client()
    resp = client.post("/api/v1/compile", files={"file": ("evil.txt", b"hello", "text/plain")})
    assert resp.status_code == 400


def test_compile_rejects_oversize():
    client = _client()
    big = b"a" * (26 * 1024 * 1024)  # > 25 MiB
    resp = client.post("/api/v1/compile", files={"file": ("big.csv", big, "text/csv")})
    assert resp.status_code == 413


def test_compile_rejects_zip_bomb():
    """Bomb com assinatura OOXML válida → barrado pela razão de compressão (413)."""
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")          # assinatura OOXML presente
        zf.writestr("xl/payload.bin", b"\x00" * (5 * 1024 * 1024))  # 5 MiB → comprime ínfimo
    bomb = buf.getvalue()
    client = _client()
    resp = client.post("/api/v1/compile", files={"file": ("bomb.xlsx", bomb,
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert resp.status_code == 413  # razão de compressão acima do limite


def test_compile_rejects_non_ooxml_zip():
    """ZIP genérico / aninhado disfarçado de .xlsx (sem [Content_Types].xml) → 400."""
    import io
    import zipfile
    # zip-bomb aninhado clássico: zip pequeno dentro de zip — sem assinatura OOXML.
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.bin", b"\x00" * (2 * 1024 * 1024))
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(4):
            zf.writestr(f"nested_{i}.zip", inner.getvalue())
    client = _client()
    resp = client.post("/api/v1/compile", files={"file": ("nested.xlsx", outer.getvalue(),
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert resp.status_code == 400  # assinatura OOXML ausente


def test_get_unknown_job_returns_404():
    client = _client()
    resp = client.get("/api/v1/jobs/nonexistent_job_id")
    assert resp.status_code == 404


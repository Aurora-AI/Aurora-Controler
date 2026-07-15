"""Testes de src/cli/web_app.py — interface web local."""
import io
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "src" / "product_a" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    from fastapi.testclient import TestClient
    from cli.web_app import create_app
    return TestClient(create_app())


def test_upload_page_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_upload_and_poll_reaches_done(client):
    with open(FIXTURE, "rb") as fh:
        resp = client.post("/upload", files={"file": ("coverage_test.xlsx", fh, "application/octet-stream")})
    assert resp.status_code == 200
    token = resp.json()["token"]

    deadline = time.time() + 30
    status = None
    while time.time() < deadline:
        status_resp = client.get(f"/status/{token}")
        assert status_resp.status_code == 200
        status = status_resp.json()["status"]
        if status in {"DONE", "ERROR"}:
            break
        time.sleep(0.2)

    assert status == "DONE"


def test_result_page_serves_report_and_download_links(client):
    with open(FIXTURE, "rb") as fh:
        resp = client.post("/upload", files={"file": ("coverage_test.xlsx", fh, "application/octet-stream")})
    token = resp.json()["token"]

    deadline = time.time() + 30
    while time.time() < deadline:
        if client.get(f"/status/{token}").json()["status"] in {"DONE", "ERROR"}:
            break
        time.sleep(0.2)

    result_resp = client.get(f"/result/{token}")
    assert result_resp.status_code == 200
    assert "coverage_test.py" in result_resp.text
    assert "coverage_test_report.html" in result_resp.text


def test_unknown_token_returns_404(client):
    resp = client.get("/status/token-que-nao-existe")
    assert resp.status_code == 404


def test_upload_input_file_deleted_after_processing_output_kept(client):
    # TestClient executa BackgroundTasks de forma síncrona antes de devolver a
    # resposta de /upload, então ao retornar aqui o job já terminou (DONE/ERROR).
    from cli.web_app import _JOBS

    with open(FIXTURE, "rb") as fh:
        resp = client.post("/upload", files={"file": ("coverage_test.xlsx", fh, "application/octet-stream")})
    token = resp.json()["token"]
    xlsx_path = Path(_JOBS[token]["xlsx_path"])
    dest_dir = Path(_JOBS[token]["dest_dir"])

    status_resp = client.get(f"/status/{token}")
    status = status_resp.json()["status"]
    assert status in {"DONE", "ERROR"}

    assert not xlsx_path.exists()  # input foi removido após o processamento
    if status == "DONE":
        assert dest_dir.exists()  # output permanece para GET /result/{token}

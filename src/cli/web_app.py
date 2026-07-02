"""
EXRS CLI — Interface web local (`exrs ui`).

Servidor FastAPI 100% local, sem Celery/Redis: execução em BackgroundTasks, status em
memória (dict). Adequado a uso single-user local — não é a infraestrutura multi-tenant
do SaaS (OS-EXRS-SAAS), que continua existindo separadamente em src/api/main.py.
"""
import tempfile
import uuid
import webbrowser
from pathlib import Path
from threading import Lock

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse

from cli.main import run_compile_cli

_JOBS: dict[str, dict] = {}
_LOCK = Lock()


def _process(token: str, xlsx_path: Path, dest_dir: Path) -> None:
    try:
        exit_code = run_compile_cli(xlsx_path, dest_dir, debug=False, chat=False)
        with _LOCK:
            _JOBS[token]["status"] = "DONE" if exit_code == 0 else "ERROR"
    except Exception as e:  # noqa: BLE001 — status do job NUNCA é silencioso
        with _LOCK:
            _JOBS[token]["status"] = "ERROR"
            _JOBS[token]["detail"] = str(e)
    finally:
        # O input já foi totalmente consumido pelo pipeline — não precisa
        # persistir. dest_dir é mantido: GET /result/{token} lista seus arquivos.
        xlsx_path.unlink(missing_ok=True)


def create_app() -> FastAPI:
    app = FastAPI(title="EXRS — Interface Local")

    @app.get("/", response_class=HTMLResponse)
    async def upload_page():
        return (
            "<html><body>"
            "<h1>EXRS — Reversão de Planilhas</h1>"
            "<form action='/upload' method='post' enctype='multipart/form-data'>"
            "<input type='file' name='file' accept='.xlsx'>"
            "<button type='submit'>Processar</button>"
            "</form></body></html>"
        )

    @app.post("/upload")
    async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
        token = uuid.uuid4().hex
        work_dir = Path(tempfile.mkdtemp(prefix=f"exrs_ui_{token}_"))
        xlsx_path = work_dir / file.filename
        xlsx_path.write_bytes(await file.read())
        dest_dir = work_dir / "output"

        with _LOCK:
            _JOBS[token] = {"status": "RUNNING", "dest_dir": dest_dir, "xlsx_path": xlsx_path}

        background_tasks.add_task(_process, token, xlsx_path, dest_dir)
        return {"token": token}

    @app.get("/status/{token}")
    async def status(token: str):
        with _LOCK:
            job = _JOBS.get(token)
        if job is None:
            raise HTTPException(status_code=404, detail="job não encontrado")
        return {"status": job["status"]}

    @app.get("/result/{token}", response_class=HTMLResponse)
    async def result(token: str):
        with _LOCK:
            job = _JOBS.get(token)
        if job is None:
            raise HTTPException(status_code=404, detail="job não encontrado")
        if job["status"] != "DONE":
            raise HTTPException(status_code=409, detail=f"job ainda não concluído: {job['status']}")
        dest_dir: Path = job["dest_dir"]
        files = sorted(f.name for f in dest_dir.iterdir())
        links = "".join(f"<li>{name}</li>" for name in files)
        return f"<html><body><h1>Resultado</h1><ul>{links}</ul></body></html>"

    return app


def serve(port: int = 8765) -> None:
    import uvicorn

    url = f"http://127.0.0.1:{port}"
    webbrowser.open(url)
    uvicorn.run(create_app(), host="127.0.0.1", port=port)

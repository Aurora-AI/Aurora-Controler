import sys
import os
import tempfile
from pathlib import Path

# Add paths to sys.path so we can import modules
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parents[1]

# Add trustware and phase folders to sys.path
for _p in [
    _PROJECT_ROOT / "libs" / "trustware",
    _PROJECT_ROOT / "src" / "phase_c0",
    _PROJECT_ROOT / "src" / "phase_c1",
    _PROJECT_ROOT / "src" / "phase_c2",
    _PROJECT_ROOT / "src" / "phase_c3",
    _PROJECT_ROOT / "src" / "orchestrator",
    _PROJECT_ROOT / "src" / "worker",
    _HERE,
]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from dashboard_contracts import DashboardSpec, C0Dataset
from unpivot import build_c0_dataset
from semantic import build_semantic_model
from metrics import build_metrics_report
from spec_builder import build_dashboard_spec, validate_spec_self_contained
from narrative import generate_narrative

from storage_manager import StorageManager
from jobs import JobStore
from upload_guard import validate_upload, UploadValidationError
from celery_app import compile_job

job_store = JobStore()

app = FastAPI(title="Aurora Controler - EXRS Dashboard Engine", version="1.0.0")

class DashboardRequest(BaseModel):
    dataset: C0Dataset
    use_llm: bool = False

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Aurora Controler EXRS"}

@app.post("/api/v1/dashboard/generate", response_model=DashboardSpec)
async def generate_dashboard(request: DashboardRequest):
    """
    Recebe um dataset (C0) e gera a especificação de dashboard visual (Fase C3).
    """
    try:
        c0 = request.dataset
        semantic = build_semantic_model(c0)
        metrics = build_metrics_report(c0, semantic)
        
        title = f"Dashboard - {Path(c0.source_file).stem}" if c0.source_file else "Dashboard Gerado"
        dashboard_id = "dashboard_executivo"
        
        spec = build_dashboard_spec(
            semantic,
            metrics,
            dashboard_id=dashboard_id,
            title=title,
            theme="executive_dark",
            llm_used=False,
        )
        
        if request.use_llm:
            spec.narrative = generate_narrative(metrics)
            spec.llm_used = bool(spec.narrative)
            
        validate_spec_self_contained(spec)
        return spec
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/dashboard/upload-and-generate")
async def upload_and_generate(file: UploadFile = File(...)):
    """
    Recebe uma planilha Excel ou CSV, executa a engenharia reversa do Excel (Fase C0-C3),
    e retorna o dataset un-pivotizado (C0Dataset) e a especificação de dashboard (DashboardSpec).
    """
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".xlsx", ".xlsm", ".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Formato de arquivo não suportado: {suffix}. Envie .xlsx, .xlsm ou .csv."
        )

    temp_path = None
    try:
        # Save upload to temporary file
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            temp_path = Path(tmp.name)

        # 1. Phase C0: Read and Un-pivot
        c0_dataset = build_c0_dataset(str(temp_path))
        # Override the original file name in dataset for display purposes
        c0_dataset.source_file = file.filename

        # 2. Phase C1: Semantic modeling
        semantic = build_semantic_model(c0_dataset)

        # 3. Phase C2: Metrics computation
        metrics = build_metrics_report(c0_dataset, semantic)

        # 4. Phase C3: Dashboard Spec synthesis
        title = f"Dashboard Executivo - {Path(file.filename).stem}"
        spec = build_dashboard_spec(
            semantic,
            metrics,
            dashboard_id="dashboard_executivo",
            title=title,
            theme="executive_dark",
            llm_used=False
        )

        # Self-contained validation
        validate_spec_self_contained(spec)

        return {
            "c0_dataset": c0_dataset,
            "spec": spec
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro no processamento: {str(e)}")
    finally:
        # Clean up temporary file
        if temp_path and temp_path.exists():
            try:
                os.unlink(temp_path)
            except OSError:
                pass

@app.post("/api/v1/compile")
async def compile_workbook(file: UploadFile = File(...)):
    """
    Plano de Controle: recebe um upload, valida (extensão/tamanho/zip-bomb), isola o arquivo
    sob output/{job_id}/, registra o job como PENDING e enfileira no broker (Celery+Redis).
    """
    content = await file.read()
    try:
        validate_upload(file.filename, content)
    except UploadValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    job_id = uuid.uuid4().hex
    storage = StorageManager(job_id)
    upload_dir = storage.output_dir / "upload"
    upload_dir.mkdir(parents=True, exist_ok=True)
    # Path(...).name neutraliza path traversal no nome do arquivo enviado.
    saved = upload_dir / Path(file.filename).name
    saved.write_bytes(content)

    job_store.create(job_id, file.filename)
    # Plano de Execução: enfileira no broker. Em EXRS_CELERY_EAGER=1 roda inline (testes).
    compile_job.delay(job_id, str(saved))
    return {"job_id": job_id, "status": "PENDING"}


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str):
    """Status do job de compilação (polling)."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job_id não encontrado")
    return record


# Mount static files folder to serve the frontend SPA
# This must be mounted AFTER API endpoints so they take priority
static_dir = _PROJECT_ROOT / "src" / "api" / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

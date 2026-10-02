# -*- coding: utf-8 -*-
"""
EXRS — Suíte de Sabotagem Preliminar e Controles Positivos (P06: FIX-05, FIX-08, FIX-09).
Contratos verificados:
1. Controles Positivos: Casos legítimos (upload válido, acesso pelo próprio tenant) passam.
2. FIX-05: Quebra de importação do CLI fora da raiz sem PYTHONPATH (reprodução de defeito).
3. FIX-08: Streaming sem Content-Length > 26 MiB cortado na camada ASGI (reprodução de defeito).
4. FIX-08: Erro de processamento vazando segredo e caminho físico no corpo (reprodução de defeito).
5. FIX-09: Tentativa de impersonação (Credencial B + Cabeçalho A) barrada com 403 (reprodução de defeito).
6. FIX-09: Path traversal em StorageManager barrado com erro estrito (reprodução de defeito).
7. FIX-09: Worker executando arquivo fora da pasta do tenant/job barrado (reprodução de defeito).
8. FIX-09: JobStore.update_status aceitando tenant divergente (reprodução de defeito).
9. FIX-09: Job legado em quarentena acessível por cliente comum (reprodução de defeito).
"""
import os
import sys
import subprocess
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]


# ─── CONTROLES POSITIVOS (DEVEM PASSAR DE INÍCIO) ───────────────────────────

def test_reprova_p06_control_positive_normal_upload(tmp_path, monkeypatch):
    """Controle Positivo 1: Upload válido de tamanho normal (< 25 MiB) é aceito."""
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    from api.main import app
    client = TestClient(app)
    csv_data = "col1,col2\nval1,val2\n"
    resp = client.post(
        "/api/v1/dashboard/upload-and-generate",
        files={"file": ("valid_small.csv", csv_data, "text/csv")}
    )
    assert resp.status_code == 200, f"Upload válido falhou inesperadamente: {resp.status_code}"
    data = resp.json()
    assert "c0_dataset" in data
    assert "spec" in data


def test_reprova_p06_control_positive_health_check():
    """Controle Positivo 2: Health check responde normalmente."""
    from api.main import app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "Aurora Controler EXRS"}


# ─── REPRODUÇÕES DE DEFEITO (DEVEM FALHAR ANTES DAS CORREÇÕES) ──────────────

def test_p06_fix05_cli_isolated_import_succeeds():
    """
    FIX-05: Comprovação do empacotamento hermético.
    Quando executado fora da raiz e sem PYTHONPATH,
    o CLI e suas dependências internas (libs.trustware) importam com sucesso.
    """
    py_exe = sys.executable
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    code = "import sys; from cli.main import main; import libs.trustware; sys.exit(0)"
    res = subprocess.run(
        [py_exe, "-c", code],
        cwd=os.path.expanduser("~"),
        env=env,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"Falha na importação isolada do CLI: {res.stderr}"


def test_reprova_p06_defect_streaming_upload_without_content_length_rejected_asgi():
    """
    FIX-08: Reprodução de corte em streaming ASGI de multipart.
    Upload incremental sem Content-Length que excede MAX_REQUEST_BYTES (26 MiB)
    deve ser interrompido com HTTP 413 pelo ASGI middleware durante a leitura.
    """
    from api.main import app
    client = TestClient(app)

    boundary = "----WebKitFormBoundaryTest123"

    def chunk_generator():
        header = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"large.xlsx\"\r\n"
            f"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
        ).encode("latin1")
        yield header
        # Gera 27 MiB em pedaços de 1 MiB
        for _ in range(27):
            yield b"X" * (1024 * 1024)
        yield f"\r\n--{boundary}--\r\n".encode("latin1")

    resp = client.post(
        "/api/v1/compile",
        content=chunk_generator(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    assert resp.status_code == 413, (
        f"Esperava HTTP 413 por corte ASGI em upload > 26 MiB, retornou: {resp.status_code}"
    )


def test_reprova_p06_defect_error_response_leaks_injected_secret_and_path(monkeypatch):
    """
    FIX-08: Verificação de que resposta de erro não vaza segredo nem caminho físico.
    Quando ocorre falha interna contendo dados sensíveis na exceção,
    a API deve responder com mensagem genérica e segura sem expor os literais no corpo.
    """
    from api.main import app
    from libs.trustware.dashboard_contracts import C0Dataset, IngestionStrategy, DetectedStructure, ValidationSummary
    client = TestClient(app)

    injected_secret = "SECRET_TOKEN_XYZ_123"
    injected_path = "C:\\Projetos\\Aurora\\Secret\\payroll_confidential.xlsx"

    # Simula exceção interna contendo segredo e caminho do sistema
    def mock_internal_error(*args, **kwargs):
        raise RuntimeError(f"Falha de processamento em {injected_path} com token {injected_secret}")

    monkeypatch.setattr("api.main.build_semantic_model", mock_internal_error)

    dataset = C0Dataset(
        source_file="input.csv",
        ingestion_strategy=IngestionStrategy(primary="structured_model", fallback="grid_scraping", used="structured_model", reason="flat"),
        detected_structure=DetectedStructure(table_kind="flat"),
        dataset=[{"row_id": 1, "val": 100}],
        source_map=[],
        discarded_rows=[],
        validation_summary=ValidationSummary(total_rows_read=1, source_rows_emitted=1, source_rows_context=0, source_rows_discarded=0, dataset_rows_emitted=1)
    )

    resp = client.post(
        "/api/v1/dashboard/generate",
        json={"dataset": dataset.model_dump(), "use_llm": False}
    )

    assert resp.status_code == 500, f"Deveria ter retornado HTTP 500, retornou {resp.status_code}"
    body = resp.text
    assert injected_secret not in body, f"Vazou segredo injetado no corpo da resposta: {body}"
    assert injected_path not in body, f"Vazou caminho físico injetado no corpo da resposta: {body}"



def test_reprova_p06_defect_impersonation_not_blocked(monkeypatch):
    """
    FIX-09: Reprodução de impersonação de tenant.
    Se o Cliente B envia X-Tenant-ID: cliente_a com sua própria credencial,
    o sistema deve rejeitar categoricamente com HTTP 403 Forbidden.
    No código atual, não existe validação de credencial vinculada a tenant,
    portanto a asserção de status_code == 403 FALHA.
    """
    import json
    monkeypatch.setenv("EXRS_API_TOKENS", json.dumps({"token_cliente_b": {"tenant_id": "cliente_b"}}))
    from api.main import app
    client = TestClient(app)

    resp = client.get(
        "/api/v1/jobs/nonexistent_id",
        headers={
            "Authorization": "Bearer token_cliente_b",
            "X-Tenant-ID": "cliente_a"
        }
    )
    assert resp.status_code == 403, (
        f"Código atual não bloqueou impersonação com 403, retornou: {resp.status_code}"
    )


def test_reprova_p06_defect_path_traversal_in_storage_manager(tmp_path):
    """
    FIX-09: Reprodução de ausência de confinamento estrito no StorageManager.
    Tentativa de escapar com '../' em tenant_id ou job_id deve levantar erro estrito.
    No código atual, StorageManager concatena caminhos diretamente sem validação regex
    ou is_relative_to, permitindo path traversal.
    """
    from orchestrator.storage_manager import StorageManager
    base_dir = tmp_path / "base_output"
    base_dir.mkdir()

    # No código corrigido, deve levantar ValueError / PermissionError.
    # No código atual, cria normalmente a pasta fora de base_output sem erro:
    with pytest.raises((ValueError, PermissionError), match="(?i)traversal|inválido|invalid|confinado"):
        StorageManager(job_id="../../escaped_job", output_base_dir=base_dir)


def test_reprova_p06_defect_worker_file_confinement(tmp_path):
    """
    FIX-09: Reprodução de ausência de confinamento de arquivo no worker.
    O worker run_compile deve validar se o arquivo de entrada pertence estritamente
    à pasta de upload do tenant e job correspondentes.
    No código atual, run_compile não valida o tenant e aceita arquivos de qualquer lugar.
    """
    from worker.celery_app import run_compile

    outside_file = tmp_path / "other_tenant_file.xlsx"
    outside_file.write_text("dummy", encoding="utf-8")

    # No código corrigido, deve recusar processar arquivo não confinado ao tenant/job:
    with pytest.raises((ValueError, PermissionError, TypeError), match="(?i)confinado|tenant|não autorizado"):
        run_compile(job_id="job123", file_path=str(outside_file), tenant_id="cliente_a")


def test_reprova_p06_defect_job_store_update_status_allows_tenant_mismatch(tmp_path):
    """
    FIX-09: Reprodução de falta de trava de tenant em update_status.
    JobStore.update_status deve exigir o tenant_id e rejeitar atualização de job pertencente a outro tenant.
    No código atual, update_status só recebe (job_id, status) e não valida o tenant.
    """
    from api.jobs import JobStore
    store = JobStore(db_path=tmp_path / "test_jobs.db")

    try:
        store.create("job_xyz", "file.xlsx", tenant_id="cliente_a")
    except TypeError:
        pytest.fail("JobStore.create no código atual não suporta tenant_id!")

    with pytest.raises((ValueError, PermissionError), match="(?i)tenant|mismatch|incompatível"):
        store.update_status("job_xyz", tenant_id="cliente_b", status="RUNNING")


def test_reprova_p06_defect_legacy_unassigned_job_exposed_to_regular_client(tmp_path):
    """
    FIX-09: Reprodução de exposição indevida de job legado em quarentena.
    Jobs migrados com tenant_id='unassigned_quarantine' devem retornar 404 para clientes comuns.
    No código atual, JobStore.get retorna qualquer job independente de tenant.
    """
    from api.jobs import JobStore
    store = JobStore(db_path=tmp_path / "test_jobs.db")

    try:
        store.create("job_legacy", "legacy.xlsx", tenant_id="unassigned_quarantine")
    except TypeError:
        pytest.fail("JobStore.create no código atual não suporta tenant_id!")

    res = store.get("job_legacy", tenant_id="cliente_a")
    assert res is None, "Job em quarentena não pode ser retornado para cliente comum!"


def test_reprova_p06_defect_no_hardcoded_admin_token_bypass(monkeypatch):
    """
    SEC-01: Prova de que não existem credenciais administrativas coringa embutidas.
    Sem configuração de tokens no ambiente, qualquer tentativa de usar 'token_admin'
    ou similar DEVE retornar HTTP 401 Unauthorized.
    """
    monkeypatch.delenv("EXRS_API_TOKENS", raising=False)
    from api.main import app
    client = TestClient(app)

    resp = client.get(
        "/api/v1/jobs/test_job",
        headers={"Authorization": "Bearer token_admin"}
    )
    assert resp.status_code == 401, f"Token admin não configurado deveria ser 401, retornou {resp.status_code}"


def test_reprova_p06_defect_malformed_token_env_fails_closed(monkeypatch):
    """
    SEC-01: Prova de Fail-Closed em configuração corrompida.
    Se EXRS_API_TOKENS contiver JSON inválido, o sistema NÃO deve ativar tokens padrão.
    Deve falhar imediatamente com erro (500 ou recusar autenticação com 401).
    """
    monkeypatch.setenv("EXRS_API_TOKENS", "{invalid_json_tokens: true,")
    from api.main import app
    client = TestClient(app)

    resp = client.get(
        "/api/v1/jobs/test_job",
        headers={"Authorization": "Bearer token_admin"}
    )
    assert resp.status_code in (401, 500), f"Configuração inválida não deve dar 200, deu {resp.status_code}"


def test_reprova_p06_defect_anonymous_request_rejected_401():
    """
    SEC-02: Prova de rejeição de acesso anônimo.
    Requisição sem cabeçalho Authorization DEVE ser rejeitada com HTTP 401.
    Não pode existir compartilhamento anônimo sob tenant 'default'.
    """
    from api.main import app
    client = TestClient(app)

    resp = client.get("/api/v1/jobs/any_job_id")
    assert resp.status_code == 401, f"Acesso sem credencial deveria ser 401, retornou {resp.status_code}"


def test_reprova_p06_defect_job_error_response_does_not_leak_internals(tmp_path, monkeypatch):
    """
    SEC-03: Prova de sanitização da resposta pública de jobs em status ERROR.
    Quando um job falha com erro contendo segredos ou caminhos físicos,
    a consulta via GET /api/v1/jobs/{job_id} NÃO deve expor esses dados confidenciais no corpo.
    """
    import json
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EXRS_API_TOKENS", json.dumps({"valid_token_a": {"tenant_id": "cliente_a"}}))
    from api.jobs import JobStore
    import api.main as main_mod

    test_store = JobStore(db_path=tmp_path / "test_jobs.db")
    monkeypatch.setattr(main_mod, "job_store", test_store)

    job_id = "job_leak_test"
    secret_str = "SUPER_SECRET_INTERNAL_KEY_999"
    path_str = "C:\\Projetos\\Aurora\\Confidential\\secrets.py"

    test_store.create(job_id, "file.xlsx", tenant_id="cliente_a")
    test_store.update_status(
        job_id=job_id,
        status="ERROR",
        tenant_id="cliente_a",
        detail=f"RuntimeError in {path_str}: failed with key {secret_str}"
    )

    client = TestClient(main_mod.app)
    resp = client.get(
        f"/api/v1/jobs/{job_id}",
        headers={"Authorization": "Bearer valid_token_a"}
    )
    assert resp.status_code == 200
    body = resp.text
    assert secret_str not in body, f"Vazou segredo na resposta pública do job: {body}"
    assert path_str not in body, f"Vazou caminho de sistema na resposta pública do job: {body}"


def test_reprova_p06_defect_dashboard_upload_enforces_25mib_file_limit():
    """
    SEC-04: Prova de aplicação de validate_upload em dashboard.
    Upload de arquivo com 25 MiB + 1 byte em /api/v1/dashboard/upload-and-generate
    deve ser barrado imediatamente com HTTP 413, antes de processamento C0-C3.
    """
    from api.main import app
    client = TestClient(app)

    oversize_payload = b"A" * (25 * 1024 * 1024 + 1)
    resp = client.post(
        "/api/v1/dashboard/upload-and-generate",
        files={"file": ("oversize.csv", oversize_payload, "text/csv")}
    )
    assert resp.status_code == 413, f"Upload > 25 MiB no dashboard deveria retornar 413, retornou: {resp.status_code}"


def test_reprova_p06_defect_job_store_update_status_requires_tenant_id(tmp_path):
    """
    SEC-05: Prova de obrigatoriedade de tenant_id em update_status.
    Chamar update_status sem tenant_id DEVE levantar TypeError (argumento posicional obrigatório sem default).
    """
    from api.jobs import JobStore
    store = JobStore(db_path=tmp_path / "test_jobs.db")
    store.create("job_t1", "file.xlsx", tenant_id="cliente_a")

    with pytest.raises(TypeError):
        # Chamada sem tenant_id deve falhar por falta de argumento obrigatório
        store.update_status("job_t1", status="RUNNING")  # type: ignore


def test_reprova_p06_defect_worker_confinement_rejects_arbitrary_paths(tmp_path):
    """
    SEC-07: Prova de confinamento estrito sem exceções no worker.
    Tentativa de processar arquivo fora de output/{tenant_id}/{job_id}/
    (inclusive em /tmp/ ou tests/fixtures) DEVE levantar PermissionError incondicionalmente.
    """
    from worker.celery_app import run_compile

    fake_file = tmp_path / "arbitrary.xlsx"
    fake_file.write_text("dummy", encoding="utf-8")

    with pytest.raises(PermissionError, match="(?i)não confinado"):
        run_compile(job_id="job_strict", file_path=str(fake_file), tenant_id="cliente_a")


def test_reprova_p06_streaming_upload_real_interruption():
    """
    SEC-06: Prova de interrupção real do streaming ASGI.
    Verifica que o servidor cessa de consumir chunks assim que o teto de 26 MiB é excedido,
    e que blocos subsequentes NÃO são lidos.
    """
    import asyncio
    import httpx
    from api.main import app

    boundary = "----WebKitBoundaryStreamingProof"
    consumed_chunks = []

    async def chunk_generator():
        header = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="large.xlsx"\r\n'
            f"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
        ).encode("latin1")
        yield header

        # Envia até 35 chunks de 1 MiB (total 35 MiB)
        for i in range(35):
            consumed_chunks.append(i)
            yield b"Z" * (1024 * 1024)

        yield f"\r\n--{boundary}--\r\n".encode("latin1")

    async def run_test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/v1/compile",
                content=chunk_generator(),
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Authorization": "Bearer any_token"
                }
            )

    resp = asyncio.run(run_test())
    assert resp.status_code == 413, f"Status inesperado: {resp.status_code}"
    # Se o corte funcionou, o servidor interrompeu a leitura ao estourar 26 MiB
    # e NÃO deve ter consumido todos os 35 chunks.
    assert len(consumed_chunks) < 35, f"Servidor consumiu todos os {len(consumed_chunks)} chunks sem corte prévio!"
    assert len(consumed_chunks) <= 27, f"Consumiu mais chunks do que o teto de 26 MiB: {len(consumed_chunks)}"


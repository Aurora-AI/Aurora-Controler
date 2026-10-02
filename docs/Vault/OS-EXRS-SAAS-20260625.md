# OS-EXRS-SAAS — EXRS-as-SaaS (Plano de Controle + Execução)

**OS ID:** OS-EXRS-SAAS-20260625-001
**Data:** 2026-06-25
**Autoridade:** `CLAUDE.md` (portfólio) + Manual de Construção Aurora v9.0
**Risco:** Alto (execução de código gerado por LLM + nova superfície de rede)
**Status:** ABERTA — aguardando início da ME-0

---

## 1. Objetivo

Evoluir o pipeline EXRS (hoje CLI monolítico em `run_pipeline.py`) para um serviço
assíncrono — Plano de Controle (API) + Plano de Execução (workers) — preservando o
determinismo e a auditabilidade da fábrica.

## 2. Contexto verificado fisicamente (Descoberta de Contratos)

> Varredura ativa executada em 2026-06-25 antes da redação desta OS.

- Pipeline real: **A0→A4** (determinístico/batch) → **B1/B2/B3** (LLM + **HITL interativo**)
  → **C0→C4** (engine de dashboard). Ref.: [`run_pipeline.py`](../run_pipeline.py),
  `src/phase_b*`, `src/phase_c*`.
- API **já existe** em [`src/api/main.py`](../src/api/main.py):
  `POST /api/v1/dashboard/upload-and-generate` roda **C0→C3** usando `tempfile`.
- `execute_in_sandbox` **já existe** em [`src/phase_a4/runner.py`](../src/phase_a4/runner.py)
  (linha 72) e é **inseguro**: injeta `__builtins__` completo e não impõe timeout.
- Versão Python divergente entre fontes: `README.md` (3.11+), `pyproject.toml` (>=3.12),
  regra Aurora (>=3.14).

### 2.1 Correção de premissa fabricada (obrigatória)

O plano de origem citava *"A Constituição (AGENTS.md) … Docker não validado"*. A varredura
confirmou que **não existe `AGENTS.md`** no repositório nem a string citada em nenhum `.md`.
A autoridade real é `CLAUDE.md` + manual v9.0. Esta premissa fica **invalidada** e é
corrigida na ME-0. (Princípio: *Descoberta Física de Contratos — Anti-Alucinação*.)

## 3. Decisão arquitetural

**Job unificado.** Um `job_id` recebe o arquivo, classifica via A0 e roteia para o
sub-pipeline **A** (engenharia reversa) ou **C** (dashboard).
**B1/B3 (HITL interativo) ficam explicitamente fora do worker assíncrono** — não são
executáveis sem input humano em loop.

## 4. Decisões de implementação (travadas com o solicitante)

| Tópico | Decisão |
|---|---|
| Produto SaaS | Ambos os pipelines sob job unificado (A→roteamento→C) |
| Sandbox A4 | Whitelist de `__builtins__` + subprocess com timeout (portável Windows/Unix) |
| Broker | Redis + Celery local via WSL |

## 5. Fora de escopo (declarado, não esquecido)

Auth/multi-tenancy, rate-limiting e variantes assíncronas de B1/B3. Cada item deve virar
OS própria. Esta OS entrega o núcleo *compile-as-a-service* single-tenant.

---

## 6. Micro-Etapas (sequenciais — Blast Radius 10–15 min cada)

> Regra da Parada: executar 1 ME → rodar Gate → acionar `@qa-review` → **PARAR** e aguardar
> aprovação sem ressalvas antes da próxima.

### ME-0 — Reconciliação documental e de ambiente
- **Objetivo:** eliminar a premissa alucinada e alinhar a versão Python.
- **Ação:** remover a citação AGENTS.md/Docker; alinhar `README.md` + `pyproject.toml` para
  `>=3.14`; registrar em `docs/ARCHITECTURE.md` os três tracks (A/B/C) e a decisão de job unificado.
- **Arquivos:** `README.md`, `pyproject.toml`, `docs/ARCHITECTURE.md`.
- **Gate:** `grep` confirma ausência da citação fabricada; `uv sync` resolve sob 3.14.
- **Evidência:** diff + saída do grep em `docs/Vault/OS-Evidence/SAAS/me0_*`.

### ME-1 — Desacoplamento de I/O (StorageManager)
- **Contrato (antes do código):** `StorageManager(job_id)` com
  `write_artifact(phase: str, model: BaseModel)` gravando em
  `output/{job_id}/{stem}_{phase}.json`. As fases retornam objetos Pydantic; nada escreve
  `output/` com `stem` fixo.
- **Problema real:** `run_pipeline.py:45` grava com `stem` fixo → colisão entre jobs concorrentes.
- **Ação:** extrair `src/orchestrator/pipeline_orchestrator.py`; `run_pipeline.py` vira wrapper CLI fino.
- **Gate:** 461 testes existentes passam + novo teste de isolamento (`job_a`/`job_b` simultâneos não colidem).
- **Evidência:** `pytest -q` + listagem `output/{job_id}/`.

### ME-2 — Roteador de pipeline unificado (A vs C)
- **Contrato:** `route(workbook_class, compile_decision) -> Literal["track_a","track_c","escalate"]`.
- **Ação:** orquestrador roda A0 e decide track; track A = A1→A4, track C = C0→C3;
  B1/B3 levantam `UnsupportedInAsyncMode` no worker.
- **Gate:** workbook de fórmulas → track_a; CSV tabular → track_c; UNSUPPORTED → escalate sem crash.
- **Evidência:** `pytest -q` dos 3 caminhos.

### ME-3 — Sandbox A4 endurecido (whitelist + subprocess timeout)
- **Contrato:** `execute_in_sandbox(func_code, func_name, inputs, *, timeout_s: float) -> Any`.
  `__builtins__` substituído por whitelist mínima
  (`len, range, min, max, abs, round, sum, float, int, str, bool`). Execução em **subprocess**
  com `timeout`; estouro → `RUNTIME_ERROR: TIMEOUT`.
- **Problema real:** `runner.py:74` injeta `__builtins__` completo (permite `__import__`/`open`/`exec`)
  e não tem timeout (`while True` trava o worker).
- **Gate (adversarial):** `import os; os.system(...)` e `while True: pass` são barrados sem
  derrubar o processo pai; funções legítimas continuam passando paridade.
- **Evidência:** `pytest -q` do teste de segurança + tempo do caso TIMEOUT < `timeout_s + ε`.

### ME-4 — Trustware gate no selo do CertifiedModule
- **Contrato:** gate determinístico **não-LLM** que valida o `CertifiedModule` antes de
  persistir (paridade, ausência de `RUNTIME_ERROR`/`#ERROR!`, integridade do artefato).
  Usa `libs/trustware/`.
- **Princípio:** "nenhuma mutação de estado crítico sem gate determinístico não-LLM" (`CLAUDE.md`).
- **Gate:** artefato adulterado (paridade < 1.0 marcado como PASSED) é rejeitado pelo gate.
- **Evidência:** teste de tamper + selo persistido.

### ME-5 — Plano de Controle (API compile)
- **Contrato:** `POST /api/v1/compile` (multipart) → `{job_id}`;
  `GET /api/v1/jobs/{job_id}` → `{status, track, artifacts[]}`.
  Validação de upload: extensão, **limite de tamanho** e **proteção zip-bomb**
  (xlsx é zip — checar ratio de descompressão antes de processar).
- **Ação:** estender `src/api/main.py` sem quebrar o endpoint de dashboard existente;
  status store em SQLite local.
- **Gate:** upload de `coverage_test.xlsx` retorna `job_id`; arquivo acima do limite e
  zip-bomb são rejeitados com 4xx.
- **Evidência:** logs do teste de API (TestClient/httpx).

### ME-6 — Workers Celery + Redis (WSL)
- **Contrato:** task `compile_job(job_id, file_path)` consumindo fila; `enqueue` no
  `POST /compile`; status `PENDING→RUNNING→PASSED/FAILED`.
- **Ação:** Redis local via WSL como broker; worker chama o `pipeline_orchestrator` (ME-1).
- **Gate:** fluxo ponta-a-ponta real (broker ligado): polling em `GET /jobs/{id}` transita
  `PENDING→RUNNING→PASSED`.
- **Evidência:** transcript do polling + `redis-cli` mostrando a task.

### ME-7 — Observabilidade e eventos de fábrica
- **Contrato:** trace por `job_id`/micro-etapa; evento `FACTORY_TOOL_UNAVAILABLE` com fallback
  explícito se Redis/broker indisponível (proibida falha silenciosa — `CLAUDE.md`).
- **Ação:** instrumentar orquestrador e worker; consultar gateway de Observabilidade
  read-only quando disponível.
- **Gate:** com broker derrubado, evento + fallback são emitidos (não trava silenciosamente).
- **Evidência:** eventos persistidos + entrada de indisponibilidade registrada.

---

## 7. Ordenação justificada

Segurança (ME-3) e gate (ME-4) **precedem** o broker (ME-6): expor um worker que executa
código gerado por LLM com `__builtins__` completo *antes* de endurecê-lo transformaria cada
job enfileirado em vetor de RCE. Endurece-se o executor antes de abrir a fila.

## 8. Verification Plan (consolidado)

- **Automatizado:** `pytest -q` (461 + novos: isolamento de job, roteamento A/C,
  sandbox adversarial, Trustware tamper, API upload/zip-bomb).
- **Manual:** `curl` upload `coverage_test.xlsx` → polling `GET /jobs/{id}` até `PASSED`;
  verificar `output/{job_id}/` com `_a0`…`_a4`.

## 9. Critério de encerramento da OS

Todas as ME aprovadas em `@qa-review` sem ressalvas, evidências persistidas em
`docs/Vault/OS-Evidence/SAAS/`, e fluxo end-to-end `compile → PASSED` reproduzível.

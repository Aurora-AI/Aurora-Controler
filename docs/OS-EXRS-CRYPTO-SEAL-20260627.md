# OS-EXRS-CRYPTO-SEAL — Selo Criptográfico de Paridade (Trustware Proof)

**OS ID:** OS-EXRS-CRYPTO-SEAL-20260627-001
**Data:** 2026-06-27
**Autoridade:** `CLAUDE.md` (portfólio) + Manual de Construção Aurora v9.0
**Risco:** Alto (gera evidência jurídico-regulatória; falha cripto = prova falsa)
**Status:** ABERTA — aguardando início da ME-0

---

## 1. Objetivo

Transformar o veredito do `certification_gate` de uma **alegação interna** numa **prova
criptográfica verificável por terceiros** (auditor forense, Banco Central, CRO/CCO) sem que o
verificador precise rodar o EXRS. Esta OS fecha o **Gap 1** do relatório de estratégia
enterprise: o documento usa "prova criptográfica de paridade" 8× como argumento central de
venda, e hoje ela não existe fisicamente.

## 2. Contexto verificado fisicamente (Descoberta de Contratos)

> Varredura ativa executada em 2026-06-27 antes da redação desta OS.

- **`CertifiedModule`** existe em [`libs/trustware/pipeline_contracts.py:349`](../libs/trustware/pipeline_contracts.py)
  com campos: `original_file`, `domain_module: DomainModule`, `validation_report: MismatchReport`,
  `certification_status: str`, `certified_at: str`, `certified_by: str`.
  **Não há campo de selo, hash nem assinatura.**
- **`verify_certification(certified) -> None`** em
  [`libs/trustware/certification_gate.py:54`](../libs/trustware/certification_gate.py)
  recomputa paridade determinística. **Zero `hash/sha/sign/hmac/crypto`** (confirmado por grep).
- **Persistência do selo** ocorre em
  [`src/orchestrator/pipeline_orchestrator.py:125`](../src/orchestrator/pipeline_orchestrator.py):
  `verify_certification(certified)` → `storage.write_artifact(stem, "a4_certified", certified)`.
- **Segundo ponto de construção citado originalmente** — `src/phase_a4/orchestrator.py:55` —
  foi **invalidado na ME-5** por Descoberta Física: esse arquivo constrói `CertifiedModule`
  com campos (`file_path`, `validation_results`, `parity_score`, `certification_date`,
  `mismatch_reports`, `audit_logs`) que **não existem** no schema real. Instanciar com esses
  campos levanta `pydantic.ValidationError`. `grep -rn "phase_a4.orchestrator\|run_phase_a4"
  src/ tests/` confirma **zero importadores**. É código morto/pré-refactor, não referenciado
  por nenhum caminho de execução. **Correção de premissa (ME-5):** o único ponto real de
  persistência de `CertifiedModule` em produção é
  [`src/orchestrator/pipeline_orchestrator.py:125`](../src/orchestrator/pipeline_orchestrator.py).
  Esta OS sela apenas ali. Achado auditado e confirmado pelo QA independente da ME-5.
- `StorageManager.write_artifact(stem, phase, model)` grava
  `output/{job_id}/{stem}_{phase}.json` ([`storage_manager.py:16`](../src/orchestrator/storage_manager.py)).
- Suíte existente: **8 testes** em [`tests/test_certification_gate.py`](../tests/test_certification_gate.py).

## 3. Decisão arquitetural

**Assinatura assimétrica Ed25519** (não HMAC). O documento de estratégia exige que o auditor
verifique **independentemente**; com HMAC o verificador precisaria do segredo (que também
assina) — inviável para terceiros. Com Ed25519, o EXRS assina com a chave privada e o auditor
verifica com a **chave pública**, sem capacidade de forjar.

**Canonicalização determinística antes do hash.** O selo cobre o hash SHA-256 de uma
serialização canônica (JSON com chaves ordenadas, sem espaços variáveis) do `CertifiedModule`
**excluindo o próprio campo de selo**. Mesmo módulo certificado → mesmo digest, sempre.

**Selo como artefato destacável.** Novo modelo `CertificationSeal` embutido no `CertifiedModule`
(campo opcional `seal: CertificationSeal | None`), mais um **verificador standalone**
(`verify_seal.py`) que não importa o pipeline.

## 4. Decisões de implementação (a travar com o solicitante antes da ME-1)

| Tópico | Decisão proposta |
|---|---|
| Algoritmo de assinatura | Ed25519 via `cryptography` (já transitiva? confirmar na ME-0) |
| Origem da chave privada | Arquivo apontado por `EXRS_SIGNING_KEY_FILE` (espelha padrão `AURORA_MASTER_KEY_FILE`) |
| Timestamp | Local UTC ISO-8601 nesta OS; **TSA RFC-3161 externo fica fora de escopo** (OS própria) |
| Hash | SHA-256 sobre JSON canônico (`sort_keys`, separators fixos) |

## 5. Fora de escopo (declarado, não esquecido)

Timestamping RFC-3161 por autoridade externa (TSA), rotação/HSM de chaves, e cadeia de
certificados X.509. Cada item vira OS própria. Esta OS entrega o selo Ed25519 verificável
offline + o verificador standalone.

---

## 6. Micro-Etapas (sequenciais — Blast Radius 10–15 min cada)

> Regra da Parada: executar 1 ME → rodar Gate → acionar `@qa-review` → **PARAR** e aguardar
> aprovação sem ressalvas antes da próxima.

### ME-0 — Confirmação de dependência e chave
- **Objetivo:** garantir que `cryptography` (Ed25519) está disponível e definir a origem da chave.
- **Ação:** confirmar `cryptography` em `pyproject.toml` (adicionar se ausente); documentar
  `EXRS_SIGNING_KEY_FILE` no `.env.example` e gerar par de chaves de teste fora do repo.
- **Gate:** `uv run python -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey"` ok.
- **Evidência:** diff do `pyproject.toml`/`.env.example` + fingerprint da chave pública de teste.

### ME-1 — Contrato do selo (antes do código)
- **Contrato:** novo `CertificationSeal(BaseModel)` em `pipeline_contracts.py`:
  `digest_sha256: str`, `signature: str` (base64), `public_key: str` (base64/PEM),
  `algorithm: str = "Ed25519"`, `canonicalization: str = "json-sort-keys-v1"`,
  `sealed_at: str` (UTC ISO). Campo `seal: CertificationSeal | None = None` em `CertifiedModule`.
- **Ação:** apenas schema + docstrings; nenhuma lógica de assinatura ainda.
- **Gate:** `461`+ suíte atual passa (campo opcional não quebra nada); import do novo modelo ok.
- **Evidência:** `pytest -q` verde + diff do contrato.

### ME-2 — Canonicalização + digest determinístico
- **Contrato:** `canonical_digest(certified: CertifiedModule) -> str` em
  `libs/trustware/sealing.py` — serializa o módulo **sem** o campo `seal`, `json.dumps(...,
  sort_keys=True, separators=(",", ":"))`, retorna SHA-256 hex.
- **Gate (determinismo):** mesmo módulo → mesmo digest em 1000 iterações; reordenar dict de
  entrada **não** muda o digest; alterar 1 `actual_value` **muda** o digest.
- **Evidência:** `pytest -q` do teste de determinismo + colisão negativa.

### ME-3 — Assinatura e selagem
- **Contrato:** `seal_module(certified, private_key) -> CertifiedModule` (retorna cópia com
  `seal` preenchido); chave carregada de `EXRS_SIGNING_KEY_FILE`.
- **Ação:** assinar o `digest_sha256` com Ed25519; embutir `public_key` no selo.
- **Gate:** selo produzido tem `signature` não-vazia; assinar 2× o mesmo módulo com a mesma
  chave produz assinatura verificável (Ed25519 é determinístico).
- **Evidência:** `pytest -q` + artefato selado de exemplo em evidência.

### ME-4 — Verificador standalone (a prova do terceiro)
- **Contrato:** `verify_seal.py <artifact.json>` — **não importa o pipeline**, só
  `pipeline_contracts` + `cryptography`. Recarrega o JSON, recomputa `canonical_digest`,
  confirma `digest == seal.digest_sha256` **e** `Ed25519.verify(signature, digest, public_key)`.
  Exit 0 = válido; exit ≠ 0 + motivo = inválido.
- **Gate (adversarial):** (a) artefato íntegro → válido; (b) 1 byte de `actual_value` alterado
  → digest diverge → **inválido**; (c) assinatura trocada por outra chave → **inválido**;
  (d) selo removido → **inválido com mensagem clara**.
- **Evidência:** transcript dos 4 casos.

### ME-5 — Integração no ponto real de selagem (reescopada)
- **Contrato original:** selar em "ambos os pontos". **Reescopo por Descoberta Física
  (registrado na Seção 2):** `phase_a4/orchestrator.py:55` é código morto, não importado por
  nenhum caminho de execução, e já quebra hoje contra o schema real do `CertifiedModule`. A
  ME-5 sela apenas o ponto real de produção.
- **Contrato aplicado:** após `verify_certification(certified)` passar, chamar
  `seal_module(certified, load_private_key())` **antes** de `storage.write_artifact(...)`, em
  [`pipeline_orchestrator.py:125`](../src/orchestrator/pipeline_orchestrator.py). Falha na
  selagem (chave ausente OU erro inesperado) nunca crasha o job nem persiste selo forjado —
  captura dupla (`SigningKeyUnavailable` e `Exception` genérica), ambas emitindo
  `FACTORY_TOOL_UNAVAILABLE` e mantendo `seal=None`.
- **Princípio:** o gate determinístico precede a assinatura — nunca se assina um selo que o
  gate rejeitaria (`CLAUDE.md`: nenhuma mutação crítica sem gate não-LLM antes).
- **Gate:** fluxo end-to-end: compilar `coverage_test.xlsx` → artefato persistido tem `seal`
  preenchido → `verify_seal.py` no artefato real retorna válido; adulteração de 1 byte
  pós-persistência → `verify_seal.py` retorna inválido; ausência de chave e erro inesperado
  na assinatura → job completa sem selo, evento gravado, suíte completa sem regressão.
- **Evidência:** artefato real selado + saída do verificador + adulteração detectada +
  evento `FACTORY_TOOL_UNAVAILABLE` reproduzido + selo do QA independente.

### ME-6 — Falha de assinatura nunca é silenciosa (herdada da ME-5, verificada no worker)
- **Contrato:** chave ausente/ilegível → evento `FACTORY_TOOL_UNAVAILABLE`
  (tool=`signing-key`) via `factory_events.py` + status explícito; **proibido** persistir
  selo sem assinatura mascarando como certificado.
- **Descoberta na execução:** o `except Exception` genérico adicionado na ME-5 (achado do QA
  independente) já cobre integralmente este contrato dentro de
  `orchestrate_pipeline` — chave ausente e erro inesperado de assinatura resultam ambos em
  evento + trace + `seal=None`, sem propagar exceção. A lacuna real que restava não era no
  orquestrador síncrono (já testado na ME-5), mas **confirmar que o caminho do worker Celery
  herda essa garantia** sem seu próprio `except Exception` (ME-7) mascarar o resultado.
- **Gate:** `run_compile` (worker) processa `coverage_test.xlsx` sem `EXRS_SIGNING_KEY_FILE`
  definida e transiciona o job a um status **terminal real** (PASSED/PARTIAL/FAILED) — nunca
  preso em RUNNING, nunca ERROR espúrio por causa da ausência de chave.
- **Evidência:** [`tests/test_worker_seal_no_orphan.py`](../tests/test_worker_seal_no_orphan.py)
  — `run_compile` real (modo eager) até status terminal persistido no `JobStore`; evento
  `FACTORY_TOOL_UNAVAILABLE` já coberto por `tests/test_pipeline_seal_integration.py` (ME-5).

---

## 6.1 ME-7 — Pinning de identidade do emissor (achado do QA final)

**Achado crítico do QA final consolidado (2026-07-01):** o verificador (ME-4) confiava em
qualquer `public_key` embutida no próprio artefato. Um atacante SEM a chave privada do EXRS
consegue forjar um artefato **inteiramente novo** (conteúdo falso + chave própria + assinatura
própria) que é internamente consistente — digest e assinatura batem entre si — e o
verificador retornava `SELO VÁLIDO`. Reproduzido: `certification_status` adulterado de
`FAILED` para `PASSED`, re-selado do zero com uma chave de atacante, `verify_seal.py` sem
`--expected-pubkey` aceitou.

**Distinção que faltava declarar:** o selo (ME-1→ME-6) prova **integridade interna** —
"nada mudou desde a selagem" — mas sozinho não prova **identidade do emissor** — "isto veio
do EXRS legítimo". Um auditor só obtém a segunda garantia se possuir a chave pública do EXRS
por um canal **separado** do próprio artefato (site institucional, contrato, distribuição
fora de banda) e a usar para pinar a verificação.

- **Correção:** `verify_seal.py --expected-pubkey <base64>` rejeita selos cuja `public_key`
  não bate com a informada; sem o argumento, a prova retorna `pubkey_pinned: false` e o script
  imprime um **aviso explícito em stderr** de que a identidade não foi autenticada.
- **Gate:** artefato forjado (conteúdo falso + chave de atacante, internamente consistente)
  → sem pin: válido com aviso; com pin na chave legítima: **inválido**.
- **Evidência:** `tests/test_verify_seal.py::test_forged_but_self_consistent_artifact_rejected_by_pubkey_pin`
  + `test_matching_expected_pubkey_still_validates`; reprodução manual via CLI com os dois
  modos (com/sem `--expected-pubkey`).

## 7. Ordenação justificada

Contrato (ME-1) e digest determinístico (ME-2) precedem a assinatura (ME-3): assinar antes de
ter canonicalização estável produziria selos não-reproduzíveis — um auditor recomputaria um
digest diferente e a prova falharia. O verificador (ME-4) precede a integração (ME-5) para que
a prova seja validada isoladamente antes de tocar o caminho de produção.

## 8. Verification Plan (consolidado)

- **Automatizado:** `pytest -q` (suíte atual + novos: determinismo de digest, colisão negativa,
  assinatura/verificação, 4 casos adversariais do verificador, falha de chave não-silenciosa).
- **Manual:** compilar `coverage_test.xlsx` → `python verify_seal.py output/{job}/..._a4_certified.json`
  retorna válido; alterar 1 dígito do artefato → verificador retorna **inválido**.

## 9. Critério de encerramento da OS

Todas as ME aprovadas em `@qa-review` sem ressalvas; artefato real selado + verificável
offline por terceiro; adulteração de 1 byte detectada; falha de chave gera evento (não
silenciosa); pinning de identidade do emissor disponível e documentado (ME-7); evidências
persistidas em `docs/Vault/OS-Evidence/CRYPTO-SEAL/`.

**Status final:** ✅ ENCERRADA — 7 rodadas de QA independente (uma por ME + 1 final
consolidado), 3 achados 🔴/🟡 substantivos corrigidos no ciclo (traceback cru vazado no
verificador, `except` restrito demais na integração de produção, pinning de identidade
ausente), 1 correção de premissa fabricada (segundo ponto de selagem era código morto).
Suíte final: **658 passed, 1 skipped, 0 failed**.

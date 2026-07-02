# EXRS CLI + UI Web Local — MVP (Design)

**Data:** 2026-07-01
**Status:** Aprovado para planejamento de implementação

## Contexto e motivação

O EXRS tem hoje dois produtos construídos: (1) o pipeline CLI monolítico original (`run_pipeline.py`, Trilhas A/B/C), e (2) o Plano de Controle/Execução SaaS (OS-EXRS-SAAS: API assíncrona, Celery/Redis, multi-tenant) com selo criptográfico de paridade (OS-EXRS-CRYPTO-SEAL) voltado a bancos/seguradoras/PE.

Este MVP é um **terceiro produto, mais simples**, com público e proposta de valor diferentes: desenvolvedores e TIs freelancer/pequenas empresas que precisam reverter planilhas Excel de clientes em código Python funcional. Sem certificação bancária, sem selo criptográfico, sem multi-tenancy, sem billing nesta fase — grátis para validar demanda antes de qualquer monetização.

## Objetivo

Entregar uma ferramenta instalável via `pip` que roda **inteiramente na máquina do usuário**, com duas formas de uso: linha de comando (para quem prefere terminal/scripts) e uma interface web local no navegador (para quem quer visual, sem fricção de CLI pura).

## Escopo

### Dentro do MVP
- Trilha A completa (A0→A4): classificação → extração → normalização → DAG → padrões → tradução → validação com sandbox Docker (mantém a exigência de Docker para preservar a garantia de segurança/determinismo já validada em produção).
- Trilha B opcional (`--chat`): captura de intenção via LLM (B1) + visualização de grafo (B2) + simulação HITL (B3) — reaproveita `chat_loop.py`, `graph_assembler.py`, `html_visualizer.py`, `hitl_loop.py` já existentes.
- Saída limpa por padrão: `<planilha>_output/<planilha>.py` + `<planilha>_output/<planilha>_report.html`. JSONs técnicos por fase continuam sendo gerados internamente (nada se perde do rastro determinístico) mas só permanecem na pasta final com `--debug`.
- CLI instalável via `pip install` expondo o comando `exrs` (hoje só existe `python run_pipeline.py`, sem entry point empacotado).
- UI web local (`exrs ui`): servidor FastAPI em `localhost`, aberto automaticamente no navegador — upload, progresso, relatório embutido, download de `.py`/`.html`.
- Mensagem de erro acionável quando Docker não está disponível (hoje é um sentinela técnico `SANDBOX_UNAVAILABLE`; precisa virar instrução clara: "Docker não encontrado. Instale: docker.com/products/docker-desktop").

### Fora do MVP (deferido, não esquecido — já existe ou será outra OS)
- Selo criptográfico de paridade (OS-EXRS-CRYPTO-SEAL) — é do produto enterprise, não faz sentido aqui.
- API assíncrona multi-tenant, Celery/Redis, SQLite JobStore — infraestrutura do SaaS bancário; a UI local usa execução síncrona em memória.
- Licenciamento/billing — grátis nesta fase.
- Trilha C (dashboard) — não faz parte da proposta de valor "reversão de código".
- Verticais regulatórias (IFRS17, BCBS239, reforma tributária) — não fazem sentido para o público de micro/pequena empresa.

## Arquitetura

### Reaproveitamento (base é `run_pipeline.py`, não uma reescrita)
- `run_pipeline.py` já orquestra A0→A4 e B1→B3 opcionais via flags `--llm`/`--hitl`. Vira a base do novo comando `exrs compile`.
- `libs/trustware/html_reporter.py::generate_html_report` já existe e é testado (12 testes em `test_html_reporter.py`), mas **nunca é chamado** pelo `run_pipeline.py` hoje — lacuna real a fechar nesta OS.
- `src/api/main.py` já tem o padrão de upload FastAPI reaproveitável para a UI local.
- `phase_b2/html_visualizer.py` já gera visualização HTML do grafo (vis-network) — embutido na tela de resultado da UI.

### Novo: `src/cli/` (nome de módulo a confirmar no plano)
- `exrs compile <arquivo.xlsx> [--chat] [--debug] [--job-id ID]` — CLI pura, decorada como entry point `pip`.
- `exrs ui [--port PORTA]` — sobe servidor FastAPI local, abre navegador automaticamente (`webbrowser.open`).
  - Execução **síncrona** por requisição (sem Celery/Redis) — status de progresso em memória (dict simples, chave = job_id efêmero), adequado a uso single-user local.
  - Fluxo: upload → tela de progresso (polling simples na fase atual) → tela de resultado (relatório embutido + downloads).
  - Checkbox opcional "Capturar intenção via chat" na tela de upload, condicionado a chave de LLM configurada (variável de ambiente já usada pelo B1).

### Empacotamento
- `pyproject.toml`: adicionar `[project.scripts]` com `exrs = "cli.main:main"` (ou equivalente, a definir no plano).
- Nome do pacote PyPI a definir (`exrs-cli` sugerido no design, não travado).

## Tratamento de erros

- Docker indisponível na Trilha A: mensagem acionável no CLI e na UI (não o sentinela técnico cru).
- `--chat` sem chave de LLM configurada: erro claro antes de iniciar o pipeline, não uma falha no meio do B1.
- UI web: erros do pipeline (ex: `GATE_REJECTED`, `SKIPPED_NO_CACHE`) devem aparecer na tela de resultado de forma legível, não como stack trace.

## Testes

- Reaproveita a suíte A0→A4 já madura (656+ testes existentes, sem regressão).
- Novo: smoke test do entry point `exrs` instalado via `pip install -e .`.
- Novo: teste de saída limpa (sem `--debug`) vs saída completa (com `--debug`).
- Novo: teste de mensagem de erro quando Docker ausente (mock/skip conforme disponibilidade).
- Novo: teste de fluxo da UI web (upload → status → resultado) via `TestClient`/`httpx`, análogo ao padrão já usado em `tests/test_api.py`.

## Decisões travadas nesta sessão

| Decisão | Escolha |
|---|---|
| Formato de entrega | Local primeiro, expandir depois |
| Empacotamento | CLI via `pip install` |
| Trilhas incluídas | A (núcleo) + B opcional (`--chat`) |
| Validação A4 | Exige Docker (mantém garantia atual) |
| Monetização | Grátis nesta fase |
| Saída | Código Python + relatório HTML |
| Poluição de saída | Limpa por padrão; JSONs técnicos só com `--debug` |
| Interface | Web local no navegador (não CLI pura, não desktop nativo) |
| Stack da UI | FastAPI + HTML simples (consistente com o resto do projeto, sem dependência nova) |

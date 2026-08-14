# Arquitetura do Aurora Controler (EXRS)

O Aurora Controler opera o ecossistema EXRS (Excel Reverse System), destinado a realizar a engenharia reversa de lógicas encapsuladas em planilhas financeiras e de negócios.

## Modelo de Roteamento (Job Unificado)

Para simplificar a interface do usuário e o ponto de entrada da API, adotamos o modelo de **Job Unificado**.
Um único endpoint e identificador (`job_id`) aceita o arquivo de entrada (`.xlsx`, `.xlsm`, ou `.csv`).
A **Fase A0 (Classificador)** analisa o arquivo e determina dinamicamente para qual sub-pipeline ("track") o arquivo será roteado.

## Os Três Tracks (A / B / C)

O sistema é dividido em três "Tracks" distintos baseados na finalidade da execução:

### Track A: Engenharia Reversa (A1 → A4)
Focado na conversão de uma planilha de lógica pesada (com fórmulas complexas) em código Python validado.
- **A0:** Classifica como "track_a".
- **A1/A1.5:** Extrai e normaliza a estrutura.
- **A2/A2.5:** Constrói o DAG e mapeia padrões.
- **A3:** Tradução lógica via LLM.
- **A4:** Sandbox endurecida via `subprocess` para validação determinística de paridade entre o código gerado e os valores originais.
*(Executado assincronamente no worker).*

### Track B: Simulação Interativa (B1 → B3)
Focado em extrair a "intenção" humana através de conversas e *Human-In-The-Loop* (HITL).
- **Aviso de Arquitetura:** As Fases B1 e B3 exigem **interação síncrona com o usuário em loop**.
- Portanto, o Track B está **explicitamente excluído do worker assíncrono (Celery)**.
- Permanecerá funcional apenas em modo CLI / execução interativa local, sem integração via API no fluxo principal SaaS, até que interfaces WebSocket / Async HITL sejam desenvolvidas no futuro.

### Track C: Dashboard Engine (C0 → C4)
Focado na análise de dados tabulares (ex: relatórios, planilhas planas) para a geração de visualizações e especificação de dashboards executivos.
- **A0:** Classifica como "track_c" (dados em forma tabular/lista sem fórmulas complexas).
- **C0:** Unpivot e carga do dataset.
- **C1:** Modelagem semântica.
- **C2:** Relatório de métricas.
- **C3:** Síntese da especificação do Dashboard (`DashboardSpec`).
*(Pode ser executado via worker para evitar timeouts no HTTP).*

## Resumo da Decisão Arquitetural
1. **Unificação de Ponto de Entrada:** Um job, roteamento inteligente via A0.
2. **Separação de Contextos de Execução:** Tracks A e C operam em background (workers), Track B isolado para interações CLI.
3. **Segurança (A4):** A execução do código Python do usuário em A4 acontece sob Sandbox rígida (whitelist de built-ins + subprocess timeout).

## Nota de mapeamento — refatoração kernel / product_a / product_b

A refatoração que criou `src/kernel/`, `src/product_a/` e `src/product_b/` reorganizou
o **Track A** (A0/A1/A1.5 → `src/kernel/`; A2 em diante + Track B + Trustware →
`src/product_a/`) e trouxe o motor comercial (antigo `src/oracle/`) para
`src/product_b/oracle/`. Um blueprint anterior dessa refatoração mapeou o **Track C**
(`phase_c0` a `phase_c4`, `src/api/main.py`) incorretamente como se fosse o Produto B
— não é. Track C é a **Dashboard Engine**, um terceiro pipeline independente que já
existia antes dessa refatoração (ver `docs/superpowers/specs/2026-05-16-phase-c-dashboard-generator-design.md`),
serve os endpoints `/api/v1/dashboard/generate` e `/upload-and-generate` em
`src/api/main.py`, e tem testes próprios em `tests/test_api.py`. Track C fica **fora
do escopo** da separação Kernel/Produto A/Produto B; uma classificação formal dele
nessa nova nomenclatura (possível "Produto C") é trabalho de uma OS futura, não desta.

### ADR — Produto B não consome o IR do kernel; utilitários de robustez ficam nele por ora

O `src/kernel/contracts.py` (IR de planilha: `WorkbookIR`, DAG, formulários
normalizados) é um contrato de **compilador**, construído para o Track A. O Produto B
(`src/product_b/oracle/`) audita dados tabulares de vendas com ingestão própria
(`column_mapper.py`) e nunca precisou desse IR — não force essa dependência por
uniformidade arquitetural; o Produto B funciona e está testado.

Cogitou-se também mover utilitários de robustez hoje só existentes no Produto B —
dedupe de cliente por CPF, registro de pseudo-entidade (`is_pseudo_entity`,
`benchmark_population`), guarda de dataset vazio — para o kernel, como código
"compartilhado" entre A e B. Na data desta nota, `src/kernel` e `src/product_a` têm
**zero** ocorrências desses conceitos: não há duplicação para eliminar, só uma aposta
sobre necessidade futura do Produto A. Mantidos em `src/product_b/oracle/` até que o
Produto A tenha um consumidor real — aí a extração ganha uma segunda chamada forçando
a interface certa, em vez de uma adivinhada hoje.

### Dívida conhecida — `libs/trustware/` órfão (OS futura, junto da classificação do Track C)

A consolidação kernel/product_a/product_b deixou `libs/trustware/` no disco como cópia
órfã, byte-idêntica a `src/product_a/trustware/`. `tests/test_phase_c0-c4.py` (restaurados
nesta rodada) e `src/api/main.py`/`test_api.py` já apontam para o canônico
(`src/product_a/trustware`); mas `src/phase_c0/__main__.py` a `phase_c3/__main__.py`
(scripts standalone, fora do caminho real da API) ainda importam de `libs/trustware`.
Duas cópias no disco podem divergir silenciosamente. Remover `libs/trustware/` e
repontar esses `__main__.py` é limpeza correta, mas mexe em código do Track C — fica
para a mesma OS futura que classificar formalmente o Track C (possível "Produto C"),
não para esta rodada.

### Nota de governança — revisão do trabalho concorrente

Nesta rodada, a consolidação da reestruturação concorrente (Antigravity) tinha suíte
100% verde, mas uma passada estrutural achou dois problemas que os testes não
capturavam: `tests/test_phase_c0.py` a `test_phase_c4.py` (64 testes, cobertura
unitária do Track C, código ainda vivo) tinham sido deletados sem justificativa —
restaurados nesta rodada, atualizados para o path canônico — e a duplicata órfã de
`libs/trustware/` acima. "Verde" prova que roda, não que a reestruturação está limpa;
mudanças estruturais de outro motor no mesmo repositório compartilhado merecem essa
mesma passada (inventário arquivo a arquivo contra o mapeamento pretendido, diff de
testes removidos/alterados, não só o resultado do pytest) antes de serem dadas como
fechadas.

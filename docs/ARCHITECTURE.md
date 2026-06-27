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

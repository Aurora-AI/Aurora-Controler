# EXRS `diagnose` — Diagnóstico DAG / Auditoria de Risco (Design)

**Data:** 2026-07-02
**Status:** Aprovado para planejamento de implementação

## Contexto e motivação

O relatório de estratégia enterprise original identificou a extração do DAG (Fase A2) como a
melhor "porta de entrada comercial": oferecer ao cliente uma "Auditoria Diagnóstica" — ele
manda 1 planilha, recebe de volta uma radiografia visual do grafo de dependências, com
hardcoding e referências quebradas expostas — antes de decidir comprar a reversão completa
para Python (`exrs compile`). Essa lacuna (Gap 2 do relatório de gap analysis) segue aberta:
o visualizador de grafo (`phase_b2/html_visualizer.py`) existe e é testado, mas está preso ao
fluxo interativo B1→B3 (que exige captura de intenção via chat/LLM), sem endpoint isolado.

Este design adiciona `exrs diagnose <arquivo.xlsx>`, reaproveitando a base do CLI local MVP
(`docs/superpowers/specs/2026-07-01-exrs-cli-local-mvp-design.md`) e o motor de classificação
já existente, para entregar essa radiografia sem exigir LLM nem Docker.

## Objetivo

Comando rápido e leve que roda apenas as fases determinísticas de análise (A0→A2.5 — sem
tradução para Python via LLM, sem validação em sandbox Docker) e entrega um relatório HTML
único contendo: (1) o grafo visual interativo de dependências e (2) uma lista de riscos
detectados, categorizados.

## Escopo

### Dentro
- Novo subcomando `exrs diagnose <arquivo.xlsx> [--out PASTA]` em `src/cli/main.py`.
- Roda A0 (classificação) → A1 (extração) → A1.5 (normalização) → A2 (DAG) → A2.5
  (padrões) diretamente — **não** usa `orchestrate_pipeline` (que sempre avança até A4/Docker).
- Novo módulo `src/cli/risk_analysis.py` detectando 4 sinais de risco:
  1. `EXTERNAL_REF` — já classificado por `fmap.patterns` (Fase A2.5).
  2. `UNRESOLVED` — já classificado por `fmap.patterns` (Fase A2.5).
  3. **Células órfãs** — nó do DAG com `formula_raw` preenchido e **zero arestas** tocando-o
     (não aparece como `source` nem `target` em nenhum `DAGEdge`).
  4. **Valores hardcoded** — tokens do tipo `CONSTANT` (`FormulaTokenType.CONSTANT`) dentro de
     `NormalizedCell.formula_tokens`, cujo `value` seja parseável como número (`int`/`float`).
     Reaproveita a tokenização que a Fase A1.5 já produz — nenhum parser novo de fórmula.
- Reaproveita `phase_b2/graph_assembler.build_graph(dag: dict, norm_ir: dict, intent:
  IntentCapture)` chamando com um `IntentCapture` **vazio** (sem chat/LLM): `IntentCapture(
  workbook_name=stem, user_goal="", input_parameters=[], output_metrics=[])`. Confirmado por
  leitura do código-fonte: `intent` só é usado para rotular nós (`_get_label`) e priorizar
  quais entram no corte de 150 nós (`_filter_nodes`) — com listas vazias, o comportamento
  degrada graciosamente para "label = coordenada" e "prioriza só nós com fórmula".
  `graph_assembler.build_graph` espera `dag`/`norm_ir` como **dict** (não os modelos Pydantic
  `ExecutionDAG`/`NormalizedWorkbookIR`) — o chamador deve `.model_dump()` antes de passar.
- Reaproveita `phase_b2/html_visualizer.py::generate_html(graph: StagedRuleGraph) -> str`
  **sem modificação** — o arquivo já é testado e não deve ser tocado por este design.
- Novo módulo `src/cli/diagnose_report.py`: monta o relatório HTML final combinando (a) o
  HTML do grafo (`generate_html`, embutido inteiro, sem pós-processamento/recoloração — ver
  Decisão de Escopo abaixo) com (b) uma tabela de riscos abaixo dele, listando cada achado
  com `node_id`, tipo de risco e descrição — permitindo ao usuário cruzar visualmente com o
  grafo acima. Reaproveita o estilo CSS de `libs/trustware/html_reporter.py` (cores,
  tipografia) para consistência visual com o relatório de `exrs compile`.

### Decisão de escopo: destaque visual dos nós de risco
O design conversacional original mencionava "nós de risco destacados com cor diferente"
dentro do próprio grafo interativo. Investigação técnica: a coloração de nós em
`html_visualizer.py` é interna a `_vis_nodes`/`_COLORS`, por tipo de nó (`GraphNodeType`), não
por lista externa de IDs — adicionar destaque exigiria modificar esse arquivo já testado, o
que viola a regra de não tocar em código compartilhado sem necessidade clara. **Decisão:** o
grafo é embutido sem modificação; o destaque visual dos riscos acontece via uma **tabela de
riscos separada, imediatamente abaixo do grafo**, com os `node_id`s exibidos com destaque
(ex: badge colorido por categoria), permitindo ao usuário localizar o nó no grafo acima pelo
ID. Cobertura funcional idêntica (grafo + riscos no mesmo relatório); a diferença é apenas
"riscos coloridos dentro do canvas do grafo" vs "riscos em tabela ao lado do grafo" — este
design escolhe a segunda por não exigir mudança em código já testado.

### Saída
`<nome>_diagnostico/relatorio.html` — só o relatório. Sem `.py`, sem JSONs técnicos (isso é
escopo de `exrs compile`, não de `exrs diagnose`).

### Fora (deferido, não esquecido)
- Endpoint web (`exrs ui`) para o diagnóstico — este design cobre só o CLI; a UI web pode
  ganhar uma tela de diagnóstico numa OS futura, reaproveitando `diagnose_report.py`.
- Score de risco agregado (ex: "7/10 de risco") — mencionado no relatório de estratégia
  original, mas não travado nesta sessão; fica para follow-up se o produto validar demanda.
- Qualquer variante hospedada/multi-tenant do diagnóstico (a estratégia original imaginava
  isso como funil SaaS "Cavalo de Troia"; esta OS mantém a filosofia local/CLI já decidida
  para o MVP).

## Arquitetura

### Novo: `src/cli/risk_analysis.py`
```
find_external_refs(fmap: FormulaRegistryMap) -> list[RiskFinding]
find_unresolved(fmap: FormulaRegistryMap) -> list[RiskFinding]
find_orphan_cells(dag: ExecutionDAG) -> list[RiskFinding]
find_hardcoded_values(norm_ir: NormalizedWorkbookIR) -> list[RiskFinding]
analyze_risks(dag, fmap, norm_ir) -> list[RiskFinding]  # agrega os 4 detectores
```
`RiskFinding` é um novo `dataclass`/`BaseModel` local ao módulo CLI (não em
`pipeline_contracts.py`, que é código compartilhado com o SaaS — este é um conceito exclusivo
do produto de diagnóstico): campos `node_id: str`, `category: str` (um dos 4 tipos acima),
`description: str`.

### Novo: `src/cli/diagnose_report.py`
```
render_diagnose_report(graph_html: str, findings: list[RiskFinding], source_file: str) -> str
```
Retorna o HTML final combinado (grafo + tabela de riscos). Função pura, testável isoladamente
com um `graph_html` e uma lista de `findings` de exemplo.

### Modificado: `src/cli/main.py`
Novo subcomando `diagnose` no `argparse`, com uma função `run_diagnose_cli(xlsx_path: Path,
dest_dir: Path | None) -> int` (mesmo padrão de exit codes de `run_compile_cli`: 0 sucesso, 1
erro, 2 uso incorreto), chamando A0→A2.5 diretamente (não `orchestrate_pipeline`) e depois
`risk_analysis.analyze_risks` + `graph_assembler.build_graph` + `html_visualizer.generate_html`
+ `diagnose_report.render_diagnose_report`.

## Tratamento de erros
- Planilha classificada como `track_c` (CSV/tabular) ou `ESCALATE` na Fase A0: mensagem clara
  ("diagnóstico não aplicável a este tipo de arquivo"), exit 1 — mesmo padrão de
  `run_compile_cli` para status não-sucesso.
- Planilha sem nenhuma fórmula (grafo vazio): relatório ainda é gerado, com uma nota explícita
  "nenhuma fórmula encontrada" em vez de uma tabela de riscos vazia sem contexto.

## Testes
- `tests/test_risk_analysis.py`: cada um dos 4 detectores testado isoladamente com fixtures
  Pydantic construídas à mão (padrão já usado em `tests/test_codegen.py`).
- `tests/test_diagnose_report.py`: `render_diagnose_report` com HTML/findings de exemplo,
  verifica que o HTML final é sintaticamente válido e contém o grafo + a tabela.
- `tests/test_cli_diagnose.py`: `exrs diagnose` ponta-a-ponta contra `tests/fixtures/
  coverage_test.xlsx` (que já tem uma aba `ExternalRef` — cobre o caso de risco real sem
  precisar de fixture nova), verificando que o relatório é gerado e contém achados esperados.

## Decisões travadas nesta sessão

| Decisão | Escolha |
|---|---|
| Onde este diagnóstico vive | Novo comando `exrs diagnose`, reaproveitando o CLI já construído |
| Sinais de risco detectados | Os 4: EXTERNAL_REF, UNRESOLVED, células órfãs, valores hardcoded |
| Grafo visual no relatório | Sim — reaproveita `phase_b2/html_visualizer.py` sem modificação |
| Destaque de risco | Tabela separada abaixo do grafo (não recoloração dentro do canvas) |
| Trilhas B/A3/A4 | Fora de escopo — só A0→A2.5, sem LLM, sem Docker |

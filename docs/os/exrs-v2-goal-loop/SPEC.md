# SPEC DE CORREÇÃO DO EXRS — EM FORMATO DE LOOP (Goal Loop)

> Objetivo: levar o motor a passar 100% da suíte de aceitação v2 **consertando a lógica geral**, não decorando o gabarito. Serve para os dois motores (Claude Code e Antigravity); a Parte 4 traz o que é específico de cada um.
>
> Versionado aqui porque o `/goal` do harness rejeita conteúdo acima de 4000 caracteres — este arquivo é a fonte de verdade, não um paste volátil na conversa.

---

## 0. Regras do loop (leia antes de tudo)

- **Modo:** goal loop. Implementa → roda a suíte de aceitação → uma segunda IA (avaliador/subagente) confere resultado **e** generalidade → se falhou, feedback específico → repete. Cap de tentativas por bloco (disciplina de token).
- **Critério de sucesso = a Parte 2 inteira verde.** O loop só para quando todas as asserções (positivas E negativas) passam.
- **Proibições (anti-overfit — o avaliador reprova se violar):**
  1. O código **não pode ler a aba `Gabarito`** nem cravar IDs/valores esperados. Fix é lógica geral.
  2. Proibido validar em dado limpo ou "ajustar o teste" para passar.
  3. Todo número de saída precisa de **procedência** (linhas/SKUs/clientes que o geraram) no artefato JSON.
- **Ordem obrigatória (há dependência):** Bloco A (integridade de dado) **antes** de B/C/D. Corrigir recall e macro sobre receita inflada por estorno e outlier gera número errado com aparência de certo.

---

## 1. Objetivo

Corrigir os falsos-positivos e implementar os módulos ausentes do EXRS, validando cada mudança contra a suíte v2, até verde total — mantendo o artefato de métricas com procedência como saída auditável.

---

## 2. Critério de sucesso (suíte de aceitação) — o coração do loop

Cada item é uma asserção **pass/fail**. Valores conferidos contra o dado real da `Consultoria.xlsx`.

### Bloco A — Integridade de dado (pré-requisito, roda primeiro)
- **A1 · Estornos líquidos.** Linhas com `qtd < 0` nunca contam como venda positiva. Impacto esperado: a receita de L6 (SKU `ARP-006`, 6 estornos) corrige em ~**R$ 6.480**. Asserção: receita bruta da rede cai ~R$ 6.480 vs. o cálculo atual.
- **A2 · Outlier robusto.** Ticket e margem usam mediana/P75/winsorização. A venda de **R$ 33.900** (ARP-001, L9) e a de **qtd = 99** (ARM-001, L9) **não** entram no ticket médio nem inflam faturamento/`expected_value`. Asserção: ticket mediano da rede muda < 2% ao remover essas 2 linhas.
- **A3 · Data robusta.** Apenas **1** linha descartada por data (a proposital `31/02/2026`); a coluna inteira **não** colapsa. Asserção: ≥ 99% das linhas aceitas E datas não trocam dia/mês (índice de sazonalidade pica em jan/fev = verão).
- **A4 · Dataset vazio nunca crasha (achado por QA review, não estava na v1 da spec).** Arquivo com zero linhas de venda, OU onde toda linha é descartada na limpeza (schema incompatível, datas todas malformadas, export corrompido), produz um laudo **vazio válido** — `0` achados em todo detector, sem exceção não tratada — e o `cli` imprime a mensagem amigável já escrita para esse cenário (`"Nenhuma linha de venda válida após a limpeza"`), não um traceback. Asserção: `run_audit()` sobre um DataFrame vazio (tipado, sem nenhuma linha) retorna `ExecutiveAuditReport` com todas as listas de achados vazias; nenhum detector individual levanta exceção. Motivo de virar regra: nenhum teste do repositório cobria esse cenário antes desta rodada — risco real de recorrência em qualquer motor que compartilhe a mesma suíte (inclusive o Antigravity).

### Bloco B — Achados verdadeiros (recall)
- **B1 · Churn = 5** exatos (`C-017..021`), COM piso: nenhum cliente com silêncio < 90 dias na lista (mata o falso `months_silent: 0`).
- **B2 · Campeão em declínio:** `DECL-001..003` aparecem (alta freq/valor até 2025-Q3, silêncio desde ~set/2025).
- **B3 · Estoque morto = 16 SKUs / R$ 35.040** (`DEAD-001..012` + `DEADX-001..004`).
- **B4 · Margem negativa:** `NEG-001..003` marcados.
- **B5 · Vazamento AG-12:** queda detectada em 2025-04/05/06.
- **B6 · Receita latente:** attach de solar ~66%, com conversão **rotulada como cenário assumido**.
- **B7 · Concentração (módulo novo):** `KEY-001` sinalizado como risco — ~**32%** da receita de L5.
- **B8 · RFM campeões:** os 10 plantados (`C-001..010`) voltam ao topo (≥ 8/10) após RFM **por loja** (o quintil global quebrou com a rede 10×).

### Bloco C — Falsos-positivos (precisão — o anti-gaming)
- **C1 ·** `SEAS-001..005` **NÃO** no churn (ciclo anual, não silêncio).
- **C2 ·** `SOL-001..005` **NÃO** no estoque morto (sazonal, ~150 d < limiar).
- **C3 ·** `PROMO-001` **NÃO** marcado como prejuízo (margem bruta positiva; considerar `forma_pagto = promocao`).
- **C4 ·** `SOLAR-SEASONAL` **NÃO** marcado como leak (integrar sazonalidade por SKU × detector de queda).
- **C5 ·** Tendência: **sem enxurrada de "decoupled"**. `company_growth` não pode usar a expansão de lojas como crescimento orgânico; baseline **mesma-loja**; limiar > 0.
- **C6 ·** GMROI: valores plausíveis (não é crível todas as categorias < 1) OU declarado explicitamente como **direcional**.

### Bloco D — Macro e robustez estrutural
- **D1 · MACRO (prioridade máxima).** P&L por loja + ranking por **margem de contribuição real**. Asserção: `L7-Oeste` e `L9-Serra` aparecem com **margem negativa** apesar de alto faturamento/volume; o ranking por margem ≠ ranking por faturamento; e o laudo declara em R$ quanto o agregado saudável **mascara** (a rede "pensa" que ganha X, ganha X − prejuízo das duas).
- **D2 · Dedupe por CPF:** `XS-01A` e `XS-01B` (mesmo CPF, 2 lojas) contam como **1** cliente em base/RFM/concentração.
- **D3 · Cold-start L10:** metas de `L10-Industrial` **rotuladas "cenário assumido"**, não derivadas do histórico (< 4 meses).
- **D4 · SEV (quando existir):** vendedor novo `V-35` (ramp ~40 d) **não** penalizado; `V-03` (lobo, ~60% sem cliente id) penalizado apesar de converter.

### Bloco E — Honestidade (transversal)
- **E1 ·** Todo número tem procedência no JSON.
- **E2 ·** Fato medido separado de cenário assumido, rotulado.
- **E3 · Pseudo-entidade nunca contamina régua de referência (achado por QA review, não estava na v1 da spec).** Cliente sem cadastro, loja/vendedor não identificado (qualquer identidade sintética usada como pseudo-grupo estável) NUNCA entra em uma estatística de referência cross-entidade (mediana, percentil, quantil) usada para avaliar entidades reais — mesmo que continue visível no relatório como fato bruto. Motivo de virar regra: achado 3x na mesma sessão antes de virar registro único (RFM excluía `_ANONYMOUS_CUSTOMER` com filtro próprio; churn de novo; SEV esqueceu de excluir `_UNKNOWN_SALESPERSON` da mediana de volume, penalizando vendedor real por engano) — a defesa morava na cabeça de quem escrevia cada detector, não na estrutura. Asserção: injetar um volume GRANDE de linhas de pseudo-entidade no dado não pode mudar NENHUM resultado calculado para as entidades reais em nenhum detector com padrão de régua de referência (teste de invariância, não um valor cravado). Implementação de referência: registro único de sentinelas + helper `benchmark_population(entity_stats, predicate)` por onde todo cálculo de régua é obrigado a passar — `src/oracle/commercial_auditor.py::is_pseudo_entity`/`benchmark_population`, `tests/test_pseudo_entity_registry.py`. Motivo de subir pra suíte compartilhada: o Antigravity quase certamente tem a mesma contaminação no churn/RFM dele — só se descobre rodando o teste lá também.

---

## 3. Saída esperada do loop

1. Suíte da Parte 2 **verde** (todas as asserções positivas e negativas).
2. Artefato **JSON de métricas com procedência** (mantém auditabilidade — não confie só no verde).
3. Log do avaliador confirmando que cada fix é **geral** (sem hardcode).

---

## 4. Apêndice — específico por motor

**Comum aos dois (convergência das duas auditorias):** A1 estornos, A2 outlier, C3 PROMO, B8 RFM por loja, e todo o Bloco D (macro, dedupe, cold-start, SEV) — ausentes ou quebrados nos dois.

**Claude Code (foco):** implementar Bloco D inteiro + A2 (nenhum tratamento de outlier hoje) + A1 (estorno cru). Data (A3) já corrigida na sessão — manter o fix de "maioria > 50%".

**Antigravity (foco):** B1 piso de churn (hoje inclui `months_silent: 0`); C5 baseline de tendência (limiar 0 + crescimento 185% de artefato); C6 GMROI (todas < 1); C4 integrar sazonalidade × leak. Data (A3) já robusta — não regredir.

---

## 5. Nota do contra cérebro

O loop transfere todo o peso para este documento. Se a suíte estiver errada ou for gameável, o motor produz lixo mais rápido. Por isso as asserções **negativas** (Bloco C) e a proibição de hardcode (Parte 0) não são opcionais: são elas que impedem o motor de "decorar a prova". Verde aqui = lógica geral consertada, não gabarito memorizado.

---

## 6. Execução nesta sessão (Claude Code) — decisão de modo

- **A1 + A2:** implementação direta, sequencial, auto-verificada nesta sessão (fixes mecânicos e determinísticos — um número recalculado fecha a questão).
- **Bloco D (D1 prioridade máxima, depois D2/D3/D4):** Workflow com verificador adversarial checando generalidade (sem hardcode, sem ler Gabarito) — lógica nova e gameável, onde self-check fraco já falhou antes (laudo alucinado da primeira interação desta sessão).
- **Dependência dura:** Bloco A tem que fechar verde **antes** de abrir o Workflow do Bloco D — macro sobre receita ainda inflada por estorno/outlier dá número errado com aparência de certo.
- **Cap de tentativas baixo no D1:** se não fechar em poucas voltas, o workflow deve parar e reportar "não consegui, falta X" em vez de girar em círculo torrando token.
- **Fora de escopo aqui:** B1, C4, C5, C6 (Antigravity).

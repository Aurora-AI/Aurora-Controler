# EXRS `audit --narrative` — Sintetizador Cognitivo (Design, OS 2)

**Data:** 2026-07-06
**Status:** Aprovado para planejamento de implementação

## Contexto e motivação

A OS 1 (Data Oracle, núcleo) entrega números exatos e incontestáveis — vazamento de
receita, churn invisível, tendência de produto — mas CEOs não compram números, compram
narrativas. A OS 2 acopla um LLM (via a infraestrutura `litellm` já usada em
`phase_a3`/`phase_b1`) para traduzir o `ExecutiveAuditReport` (já pseudo-anonimizado pela
OS 1) num texto executivo frio, direto e pronto para colar numa apresentação ou e-mail de
consultoria.

## Objetivo

`exrs audit <pasta-ou-arquivo> --narrative` — roda a auditoria determinística normal
(que **sempre** sucede independentemente do LLM) e, ao final, gera `narrativa.md` na
mesma pasta de saída: um resumo executivo dos achados mais graves, no formato *"Nos
últimos X meses, a empresa perdeu Y no produto Z... Recomendação tática: [ação]"*.

## Escopo

### Dentro
- Novo módulo `src/oracle/narrative_synthesizer.py`.
- Flag `--narrative` em `exrs audit` (aditiva, opt-in — sem a flag, comportamento
  idêntico ao da OS 1).
- Triagem determinística (top N por categoria + "caixa" agregada dos demais) — o LLM
  nunca decide o que é prioritário, só narra o que o Python já selecionou.
- Prompt de sistema restritivo (anti-alucinação, anti-prolixidade — ver §Governança).
- Telemetria de falha via o Event Bus já existente (`factory_events.emit_event`).
- Falha do LLM é best-effort: nunca derruba o exit code da auditoria determinística.

### Fora (declarado, não esquecido)
- Dashboard "Quiet Luxury" (OS 3, projeto de UI próprio).
- Flag de escolha de modelo/provider por linha de comando (usa `LITELLM_MODEL` do
  ambiente, já configurável globalmente — consistente com `phase_a3`/`phase_b1`).
- Cache/retry automático de chamadas LLM (fica para se o volume real justificar).

## Arquitetura

| Arquivo | Responsabilidade |
|---|---|
| `src/oracle/narrative_synthesizer.py` | Triagem (top N + caixa) + montagem do prompt + chamada `litellm` + parsing |
| `src/cli/main.py` | Modificado: flag `--narrative`, chamada best-effort após a auditoria |

### Triagem determinística (`select_top_findings`)
Por categoria, top N=3 (constante nomeada, não mágica):
- Vazamentos de receita → ordenados por `drop_sigma` decrescente
- Churns → ordenados por `historical_annual_value` decrescente
- Tendências de produto → só `decoupled=True`, ordenados por
  `company_growth_pct - product_growth_pct` decrescente

O restante de cada categoria vira uma **"caixa"** agregada — nunca descartado, só
resumido: `{"count": N, "total_impact": valor_somado}`. O prompt inclui os achados
detalhados do top N + uma linha por caixa agregada, garantindo que nenhum vazamento
fique de fora do relatório final (mesmo que não narrado individualmente).

### Governança do Prompt (anti-alucinação, anti-prolixidade)
Prompt de sistema ancorado, travado nesta sessão (texto exato, não paráfrase):

> "Você é um Analista de Risco Técnico. Sua função é traduzir achados matemáticos em
> narrativa executiva. É proibido inventar dados. Se o achado não estiver no contexto,
> ignore-o. O tom deve ser frio, direto e imperativo."

O prompt de usuário contém **apenas** os campos do top N + caixas agregadas,
serializados de forma compacta (não o `ExecutiveAuditReport` inteiro) — reduz superfície
de alucinação e mantém o contexto pequeno.

### Blindagem PII (herdada da OS 1)
O payload enviado ao LLM é construído a partir do `ExecutiveAuditReport` **já
pseudo-anonimizado** (`Client_A`, `Client_B`...) — a mesma garantia testada na OS 1
(`test_executive_audit_report_json_never_contains_real_customer_names`) se estende
transitivamente: se o nome real não está no report, não pode vazar para o prompt
montado a partir dele.

### Telemetria de falha (Event Bus)
Se `synthesize_narrative` falhar (sem chave de API, erro de rede, rate limit, resposta
vazia), dispara `emit_event("NARRATIVE_SYNTHESIS_FAILED", provider=..., detail=...,
job_id=...)` via `libs/trustware/factory_events.py` (o mesmo Event Bus já usado em todo o
projeto para `FACTORY_TOOL_UNAVAILABLE`) — permite monitoramento de gargalos recorrentes
de provedor (Chronos) sem interromper a auditoria. `synthesize_narrative` retorna `None`
nesse caso; `run_audit_cli` imprime aviso claro no stderr e **não cria** `narrativa.md`
— nunca finge sucesso.

## Fluxo

```
exrs audit vendas/ --narrative
  → (idêntico à OS 1) motor determinístico roda, audit_report.json + relatorio.html
    sempre gerados, exit code reflete só isto
  → gate: --narrative foi passada?
      → não: fim, comportamento idêntico à OS 1
      → sim: narrative_synthesizer.select_top_findings(report, n=3)
              → build_narrative_prompt(top_findings, boxes) [prompt de sistema fixo]
              → litellm.completion(...)
                  → sucesso: escreve narrativa.md
                  → falha: emit_event("NARRATIVE_SYNTHESIS_FAILED", ...) + aviso no
                    stderr + NÃO escreve narrativa.md (best-effort, exit code inalterado)
```

## Testes
- `select_top_findings`: corte correto por categoria, ordenação, caixa agregada com
  contagem/soma corretos, nenhum achado desaparece (soma top N + caixa == total).
- `build_narrative_prompt`: prompt de sistema é o texto EXATO travado; nenhum nome real
  de cliente aparece no prompt montado (mesma asserção anti-regressão da OS 1, agora
  sobre o prompt).
- `synthesize_narrative`: mock de `litellm.completion` — caminho de sucesso (retorna
  texto) e caminho de falha (exceção do litellm → retorna `None` + evento emitido, sem
  propagar exceção).
- CLI: `exrs audit ... --narrative` com LLM mockado — sucesso gera `narrativa.md`; falha
  não gera o arquivo mas mantém exit code 0 (a auditoria em si foi bem-sucedida) e emite
  o evento no `factory_events.jsonl`.

## Decisões travadas nesta sessão

| Decisão | Escolha |
|---|---|
| Integração no CLI | Flag `--narrative` em `exrs audit` (aditiva, opt-in) |
| Estrutura do texto | Abertura + 1 parágrafo por achado do top N + caixa agregada + recomendação final |
| Priorização | Top N=3 por categoria (determinístico, não decidido pelo LLM) + caixa para o restante |
| Falha do LLM | Best-effort — auditoria determinística sempre sucede; narrativa.md só existe se realmente gerado |
| Prompt de sistema | Texto travado, restritivo (proíbe invenção de dados, tom frio/imperativo) |
| Telemetria | `emit_event("NARRATIVE_SYNTHESIS_FAILED", ...)` via Event Bus já existente (`factory_events.py`) |
| PII | Herdada da OS 1 — payload construído do report já anonimizado |

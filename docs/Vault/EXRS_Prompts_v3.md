# PROMPTS — RODADA v3 (serviços)

> Regras de sempre: ignore a aba `Gabarito`; não crave ID/valor esperado; todo número com procedência; verificação adversarial independente (não auto-atestado); reuse o registro de pseudo-entidade (`is_pseudo_entity`/`benchmark_population`), não reinvente. Critério de sucesso = `SPEC.md` (Blocos A–E + novo **Bloco SVC**). Saída: laudo do cliente no padrão de 9 seções + JSON de procedência.

---

## PROMPT — CLAUDE CODE

A planilha mudou de novo (v3): recopie `Consultoria.xlsx`. Continua com 10 lojas; **3 delas ganharam uma linha de serviços** (`categoria = servico`) — descubra quais varrendo o dado, não pergunte.

Seu escopo A/D/E3/B7 está verde; não regrida. O que falta nesta rodada:

1. **Implementar a camada de SERVIÇOS** (Bloco SVC da SPEC), reusando o registro E3:
   - `servico` é linha distinta: fora do GMROI (não tem estoque), não pode poluir ticket de produto nem RFM de produto.
   - **Decompor o resultado de cada loja em produto × serviço × follow-on.** Sinalize toda loja com **total positivo mas margem de produto negativa** — serviço mascarando produto quebrado. Não declare essa loja saudável.
   - Detectar o efeito **follow-on/CAC** (cliente que entrou por serviço e depois comprou produto).
   - Reconciliar `receita_servicos` (Financeiro) × vendas de `servico`; sinalizar meses-loja com gap.
2. **(Opcional, para um motor completo)** fechar B8 — RFM por loja (o quintil global quebrou com a rede 10×).
3. Rode o audit completo no v3 e **gere o laudo do cliente** (padrão 9 seções) a partir do motor corrigido — este é o laudo candidato à reunião. QA do laudo contra o JSON de procedência (nenhuma alucinação; todo número aponta pra linha de origem).

A decomposição produto×serviço passa pelo workflow adversarial (não auto-atestar): o avaliador deve construir do zero o caso de uma loja no vermelho de produto "salva" por serviço e confirmar que o motor a marca.

---

## PROMPT — ANTIGRAVITY

A planilha mudou de novo (v3): recopie `Consultoria.xlsx`. 10 lojas; **3 ganharam linha de serviços** (`categoria = servico`) — descubra quais varrendo o dado.

Antes dos serviços, feche as pendências do gabarito v2 (Apêndice da SPEC), que ainda são suas:
- **B1** piso de churn: nenhum cliente com silêncio < 90 dias na lista (hoje entra gente com `months_silent: 0`).
- **C4** integrar sazonalidade × leak: SKU sazonal (pico previsível) não pode virar "queda de receita".
- **C5** baseline de tendência **mesma-loja**, limiar > 0: a expansão de lojas não é crescimento orgânico (não use os ~185% de artefato).
- **C6** GMROI plausível (não é crível todas as categorias < 1) ou declarado direcional.
- **E3** registro único de pseudo-entidade: seu churn/RFM provavelmente inclui cliente anônimo/vendedor não identificado na régua de referência. Rode o teste de invariância — se contaminar, ele pega.

Depois, **implemente a camada de SERVIÇOS** (Bloco SVC da SPEC): separação (servico fora do GMROI, sem poluir produto), **decomposição produto × serviço × follow-on** com o flag de "serviço mascarando produto negativo", efeito follow-on/CAC, e reconciliação `receita_servicos` × vendas de serviço.

Rode tudo e entregue o laudo (9 seções) + JSON de procedência. Verificação adversarial independente em cada detector novo.

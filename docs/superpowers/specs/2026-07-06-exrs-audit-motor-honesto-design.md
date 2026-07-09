# EXRS `audit` — Motor Honesto (Design, OS-EXRS-AUDIT-HONESTO)

**Data:** 2026-07-06
**Status:** Aprovado — pré-requisito de fixture resolvido (opção a: estender a fixture como 1ª etapa do Fix 3)
**Autoridade:** spec do CSO (Rodrigo) + achados da fixture de ótica
  (`docs/superpowers/specs/2026-07-06-otica-fixture-e-achados.md`)

## Princípio ordenador

**Credibilidade antes de cobertura, cobertura antes de polimento.** Um falso positivo no
Executive Audit Report (o soco do D5) é pior que uma feature faltando — mata o gancho que
sustenta o contrato. Por isso: (Fix 1+2) tornar honestos os detectores que já existem →
(Fix 3) destravar a série B de estoque → (depois) OS 2 Sintetizador.

## Contexto

A fixture de ótica revelou que o `exrs audit` de hoje: acerta churn (5 exatos) e vazamento
pontual (AG-12), mas **falseia positivo em sazonalidade** (quedas de março do solar) e em
**ruído de série esparsa** (8 SKUs de lente), e é **cego para as abas de estoque/compras**.
Esta OS fecha os três.

---

## Fix 1 — Consciência de Sazonalidade (Year-over-Year)

**Regra:** uma variação só é anomalia se for pior que o **mesmo período do ano anterior**,
não que o mês adjacente. Remove-se o padrão sazonal antes de medir o desvio.

**Método (no detector de vazamento de receita, `detect_revenue_leaks`):**
1. Para cada produto, valor esperado do mês M = média do mês-do-ano M nos anos anteriores
   disponíveis (YoY).
2. Resíduo = valor real − esperado YoY.
3. Corte de anomalia (mantém `revenue_drop_sigma`, default 2.0) aplicado **sobre o resíduo**,
   não sobre a série crua.
4. **< 2 anos** de histórico para o produto → sem base YoY → não hard-flag; no máximo marca
   `low_confidence` (nunca sinaliza forte sem base).

**Caso de borda explícito (da fixture):** o histórico começa em 2023-07, então o primeiro
março é 2024-03 (sem março anterior). Logo `2024-03` é suprimido pela regra do §4
(low-confidence, não hard-flag); `2025-03` e `2026-03` têm março anterior → resíduo ≈ 0 → não
flagam. Os três marços deixam de flagar, por caminhos diferentes — ambos corretos.

**Casos de teste (assertáveis contra a fixture atual):**
- `SOLAR-SEASONAL`: quedas de março (2024/2025/2026-03) **NÃO** flagam.
- `AG-12`: queda de 2024-05 (~4.12σ, não sazonal → resíduo alto) **DEVE** continuar `high`.

**Aceite:** falsos positivos de sazonalidade = **0**; AG-12 mantido.

---

## Fix 2 — Piso de Materialidade

**Regra:** um produto só entra na detecção de anomalia se for material. Abaixo do piso, entra
só na soma dos totais, nunca no detector por-produto.

**Parâmetros (novos campos em `AuditThresholdsConfig`, tunáveis):**
- `materiality_revenue_pct: float = 1.0` — SKU analisado se ≥ 1% da receita do período, **OU**
- `materiality_min_sales: int = 12` — ≥ 12 vendas no período (≈1/mês). O que for atingido primeiro.

**Casos de teste (da fixture atual):**
- Os **8 `LEN-xxx`** de venda esparsa **NÃO** flagam (abaixo do piso).
- `AG-12` (material) **DEVE** flagar.

**Aceite:** ruído de série esparsa = **0** flags; AG-12 mantido.

> **Fix 1+2 são independentes e imediatamente assertáveis contra a fixture JÁ versionada** —
> nenhum pré-requisito. É o incremento de credibilidade, shippável sozinho.

---

## Fix 3 — Leitura multi-aba + Série B (cobertura)

**Contrato de schema:** passar a ler as abas **por nome** (`Vendas`, `Estoque`, `Compras`,
`Clientes`, `Vendedores`), não só a sheet 0. Vendas continua alimentando os detectores atuais.

**Fórmulas e valores esperados (Gabarito #5–#9):**

| Fórmula | Cálculo | Esperado |
|---|---|---|
| **B1 Giro/Cobertura** | Giro = CMV ÷ estoque médio a custo; Cobertura = 365 ÷ giro | solar: giro **6**, cob **60,8d** |
| **B2 GMROI** | Margem bruta (R$) ÷ estoque médio a custo | premium **0,625** (<1 alerta); lente **2,0** |
| **B4 Estoque Morto** | SKUs sem movimento > `dead_stock_months` (8); Σ(qtd×custo) | **R$ 9.600**; **12 SKUs**; **9,6%** |
| **B5 Margem Contribuição** | MC = preço − custo_entrada − variáveis (imposto+comissão+taxa); flag MC<0 | **3 SKUs**, MC **−R$20** |

**Contingência A1 (o pivô do dado ruim):** se completude de cadastro (telefone/CPF) < 30%
(`contingency_completeness_pct`), o relatório **lidera pela série B** (B4+B5) em vez de
churn/latente. Variante B da fixture (25%) pivota; Variante A (90%) roda normal.

### ⚠️ Pré-requisitos de fixture (achados na revisão da spec — DEVEM ser resolvidos antes de assertar Fix 3)

A fixture atual planta com exatidão **apenas #5 (estoque morto R$9.600) e #6 (3 SKUs MC<0
estrutural)**. As demais não são assertáveis hoje:

1. **B5 não tem de onde tirar "variáveis" (imposto+comissão+taxa).** A aba Estoque só tem
   `custo_unit`/`preco_venda`; não há taxa de variáveis em lugar nenhum. **Resolução proposta:**
   adicionar uma aba `Parametros` com `imposto_pct`, `comissao_pct`, `taxa_cartao_pct` (ou os
   R$ fixos), de modo que os 3 SKUs MCNEG deem MC = 200 − 190 − 30 = −R$20 exato.
2. **#7 (GMROI), #8 (giro), #9 (ABC) não são plantados deterministicamente.** As categorias do
   Estoque/Compras hoje são preenchimento aleatório — não produzem GMROI premium=0,625, lente
   =2,0, nem solar giro=6. **Resolução proposta:** estender o gerador para plantar essas
   agregações por categoria com os valores exatos do Gabarito (margem bruta e estoque médio
   engenheirados), antes de implementar B1/B2/B3.

**Decisão a travar com o solicitante:** (a) estender o gerador da fixture como 1ª etapa do
Fix 3 (recomendado — mantém tudo assertível ao padrão da casa), ou (b) implementar B1/B2/B3/B5
e assertar só "computado + direção correta" (GMROI<1 para premium, MC<0 para MCNEG) sem os
valores exatos. A recomendação é (a): sem gabarito exato, a série B vira "acha bonito", não
teste — exatamente o que a fixture existe para evitar.

**Aceite Fix 3:** B1/B2/B4/B5 computados com os valores esperados (após pré-requisito);
Variante B pivota para série B; Variante A roda normal.

---

## Critérios de aceitação (regressão consolidada)

1. Sazonalidade: `SOLAR-SEASONAL` para de flagar nos 3 marços; AG-12 permanece `high`.
2. Materialidade: os 8 `LEN-xxx` param de flagar; AG-12 permanece.
3. Multi-aba: B1/B2/B4/B5 com os valores esperados (após resolver pré-requisitos de fixture).
4. Contingência: Variante B (25%) pivota; Variante A (90%) normal.
5. Sem regressão na suíte existente; regressão nova para cada item acima.

## Parâmetros tunáveis (defaults — todos em `AuditThresholdsConfig`)

| Parâmetro | Default |
|---|---|
| Janela sazonal | YoY (mesmo mês, anos anteriores); mín. 2 anos, senão low-confidence |
| `materiality_revenue_pct` | 1.0 (% da receita do período) |
| `materiality_min_sales` | 12 (vendas/período) |
| `dead_stock_months` | 8 |
| `contingency_completeness_pct` | 30.0 |

## Nota para a OS 2 (Sintetizador `--narrative`)

A narrativa só pode apresentar achados **pós-sazonalidade e pós-materialidade** (nunca a lista
crua de 2σ), e deve declarar quando pivotou pela contingência (dado ruim → soco de estoque).
Polimento depois do motor honesto — o `select_top_findings` da spec da OS 2 consome a saída
já limpa por esta OS.

## Decisões travadas

| Decisão | Escolha |
|---|---|
| Ordem | Fix 1+2 (credibilidade) → Fix 3 (cobertura) → OS 2 (polimento) |
| Sazonalidade | YoY sobre resíduo; <2 anos = low-confidence, nunca hard-flag |
| Materialidade | 1% receita OU 12 vendas/período (o que primeiro) |
| Multi-aba | ler por nome; Vendas mantém os detectores atuais |
| Contingência | completude < 30% → liderar por série B |
| Pré-req Fix 3 | **RESOLVIDO (opção a):** estender fixture (aba Parametros p/ B5 + plantar #7/#8/#9 exatos) como 1ª etapa do Fix 3 |
| Thresholds | tudo em `AuditThresholdsConfig`, zero número mágico |

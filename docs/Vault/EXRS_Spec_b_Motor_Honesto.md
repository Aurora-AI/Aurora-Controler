# Spec (b) — Tornar o motor honesto (para o Claude Code)

Escopo: **três fixes num passo** — (1) sazonalidade YoY, (2) piso de materialidade, (3) multi-aba + série B. Parâmetros de metodologia travados abaixo; valores esperados batem com a fixture já versionada. Ordem de prioridade: credibilidade (1,2) → cobertura (3) → depois polimento (OS 2).

---

## Fix 1 — Consciência de Sazonalidade (Year-over-Year)

**Regra:** uma variação de um período só é anomalia se for pior que o **mesmo período do ano anterior**, não que o mês adjacente. Remova o padrão sazonal antes de medir o desvio.

**Método:**
1. Para cada produto/métrica, calcule o valor esperado do mês M = média do mês M nos anos anteriores disponíveis (YoY).
2. O resíduo = valor real − valor esperado YoY.
3. Aplique o corte de anomalia (mantenha o 2σ) **sobre o resíduo**, não sobre a série crua.
4. Se houver **menos de 2 anos** de histórico para aquele produto, não há base YoY → use tendência dessazonalizada e marque a flag como **baixa confiança** (nunca hard-flag sem base).

**Casos de teste (assertáveis, da fixture):**
- `SOLAR-SEASONAL`: as quedas de março (2024-03, 2025-03, 2026-03) **NÃO** devem mais flagar (resíduo YoY ≈ 0 — março é igual ao março típico).
- `AG-12`: a queda de 2024-05 (~34%, ~4.12σ) **DEVE** continuar flagando `high` (não é sazonal → resíduo alto).

**Aceite:** falsos positivos de sazonalidade = **0**; AG-12 mantido.

---

## Fix 2 — Piso de Materialidade

**Regra:** um SKU/produto só entra na detecção de anomalia se for material. Abaixo do piso, entra só na soma dos totais, nunca no detector.

**Parâmetros (travados; tunáveis por cliente):**
- SKU analisado se **≥ 1% da receita do período** **OU** **≥ 12 vendas no período** (o que for atingido primeiro).
- Racional: 1% = materialidade financeira; 12 vendas (≈1/mês) = mínimo estatístico pra uma série ter sinal em vez de ruído.

**Casos de teste (da fixture):**
- Os **8 `LEN-xxx`** de venda esparsa **NÃO** devem flagar (abaixo do piso).
- `AG-12` (produto material) **DEVE** flagar.

**Aceite:** ruído de série esparsa = **0** flags; AG-12 mantido.

---

## Fix 3 (quase-P0) — Leitura multi-aba + Série B

**Contrato de schema:** hoje o `exrs audit` lê só a primeira aba (sheet 0 = Vendas). Passar a ler as abas **por nome**: `Vendas`, `Estoque`, `Compras`, `Clientes`, `Vendedores`. (Manter Vendas como a aba dos detectores atuais.)

**Fórmulas e valores esperados (da fixture #5–#9):**

| Fórmula | Cálculo | Esperado na fixture |
|---|---|---|
| **B1 Giro / Cobertura** | Giro = CMV ÷ estoque médio a custo; Cobertura = 365 ÷ giro | Categoria solar: giro **6**, cobertura **60,8 dias** |
| **B2 GMROI** | Margem bruta (R$) ÷ estoque médio a custo | Premium **0,625** (<1 alerta); Lente **2,0** |
| **B4 Estoque Morto** | SKUs sem movimento > N meses (N=8, tunável 6–9); Capital preso = Σ (qtd × custo) | **R$ 9.600**; índice **9,6%**; **12 SKUs** |
| **B5 Margem de Contribuição** | MC = preço − custo_entrada − variáveis (imposto+comissão+taxa); flag MC<0 | **3 SKUs**, MC = **−R$ 20** cada |

**Contingência A1 (o pivô do dado ruim):** se a completude de cadastro (telefone/CPF) for **< 30%**, o relatório **lidera pela série B** (estoque morto + prejuízo oculto) em vez de churn/latente.
- Variante B da fixture (completude 25%): deve pivotar; soco = B4 (R$ 9.600) + B5 (3 SKUs no prejuízo). Limpeza reporta ~12% de linhas descartadas (bate com os 11,9% já observados).

---

## Critérios de aceitação (resumo para regressão)

1. Sazonalidade: `SOLAR-SEASONAL` deixa de flagar nos três marços; AG-12 permanece `high`.
2. Materialidade: os 8 `LEN-xxx` deixam de flagar; AG-12 permanece.
3. Multi-aba: B1/B2/B4/B5 computados com os valores esperados acima.
4. Contingência: Variante B (25%) pivota para a série B; Variante A (90%) roda o fluxo normal.
5. Sem regressão nos testes existentes; adicionar regressão para cada item acima.

## Parâmetros tunáveis (defaults)
- Janela sazonal: YoY (mesmo mês, anos anteriores). Mínimo 2 anos, senão baixa confiança.
- Piso de materialidade: 1% da receita **ou** 12 vendas/período.
- Estoque morto: sem movimento > 8 meses.
- Contingência: completude < 30%.

---

## Nota para quando chegar na OS 2 (Sintetizador `--narrative`) — evitar round-trip
A narrativa só pode apresentar achados **pós-sazonalidade e pós-materialidade** (nunca a lista crua de 2σ). E deve declarar quando pivotou pela contingência (dado ruim → soco de estoque). Polimento vem depois do motor honesto — não antes.

# PROMPT — `build_executive_summary(...)` (decisões travadas para o golden master)

Implemente a função que pré-computa os agregados do laudo (o frontend não calcula nada). Estas decisões estão **fechadas** — vire fórmula e trave no golden master. Nada de reabrir.

## Princípio-mãe (grave no docstring do módulo)
O motor depende só do que é universal numa base transacional (data, valor, custo, id, categoria). Onde o dado **não responde a intenção** (promoção vs. erro, sazonal vs. morto), o motor **afirma o fato e adia o juízo para confirmação humana** — nunca adivinha por nome mágico nem por coluna que torce existir. Todo agregado é **calculado da fonte, contado uma vez — nunca somando os números dos achados** (achado é lente; total é fato).

## 1. `total_operational_loss`
- Base: soma da margem de contribuição negativa dos SKUs (`contribution_margin < 0`) de `contribution_margin_alerts` (SKU-nível-rede, como existe hoje).
- **NÃO** somar com `service_decomposition` (evita double-count).
- **NÃO** excluir promoção — não há sinal universal no dado; excluir por prefixo de nome viola o princípio de não cravar string mágica, e por coluna nova viola "ler qualquer planilha".
- **Rótulo honesto obrigatório:** nunca "sangria estrutural confirmada". Rotular: *"R$ X em SKUs vendendo abaixo da margem de contribuição — pode incluir promoção intencional, a confirmar."* A classificação promo-vs-erro é pergunta para o dono (nível N2), não fórmula.
- Docstring: escopo = SKU-nível-rede. A perda mascarada por loja continua reportada à parte via `service_decomposition` (é linha distinta no CTA, não undercount).

## 2. CTA decomposto por natureza contábil (não um lump "total sangrando")
Três campos separados, cada um da fonte, contado uma vez:
- `total_operational_loss` — fluxo (os SKUs no vermelho), rótulo "a confirmar".
- `total_capital_frozen` — estoque morto (capital **recuperável**).
- `total_ltv_risk` — churn (LTV **projetado, em risco**, não perda confirmada).
- **Regra dura:** naturezas não somam num número único. Cada uma tem palavra própria (parado / em risco / sangrando).
- Receita latente (cenário) fica **fora** do total, rotulada à parte como hipótese.

## 3. `total_discarded_alarms` (versão leve — só o que o motor realmente checa hoje)
Lista `{alarme, motivo}`, não um int. Conta apenas os checks que existem:
- Queda sazonal descartada em `revenue_leaks` (flag `seasonality_adjusted`).
- Vendedor em rampa não penalizado (SEV, tenure < ramp).
- Loja em cold-start sinalizada.
- **NÃO** incluir "estoque sazonal" nem "promoção descartada" — o motor não faz esses checks hoje; incluí-los seria padding. Não infla o count; todo descartado é um check real e defensável.

## 4. `action_plan[]` (pré-ordenado pelo motor; o front renderiza cego)
- Mapeamento base: `churn→LTV`, `dead_stock→capital`, `perda operacional→operational`.
- Ordenação por R$ **dentro de tiers de certeza** (não `abs(R$)` puro):
  - Tier 1 — perda operacional certa/recorrente (caixa saindo agora).
  - Tier 2 — capital recuperável (estoque morto).
  - Tier 3 — LTV projetado (churn — probabilístico, precisa de campanha).
  - **Fora/separado** — cenário (latente): nunca no plano como se fosse fato.
- Cada item: `{achado, ação, impacto_R$, natureza, tier}`.

## Travas de verificação
- **Renderize, não calcule:** todos os agregados prontos no `ExecutiveSummary`; grep no front não pode achar aritmética (`.reduce`, `.sort`, `+/-`) sobre valores financeiros.
- **Sem double-count**, inclusive intra-bucket: o agregado vem da fonte, não da soma dos achados.
- **Golden master:** os agregados sobre o laudo real (v4) ficam congelados como não-regressão.
- **Rótulo = natureza:** nenhum número apresentado além do que é (fato / "a confirmar" / cenário).

## Explicitamente FORA desta rodada (registra como ADR, não faz agora)
- Detector novo de margem de contribuição por **loja×SKU** (a perda mascarada fica no `service_decomposition`).
- Coluna/sinal de **promoção** na planilha de origem.
- **Sazonalidade-para-planejamento** (forecast do padrão medido) e **promoção-colaborativa** (dono marca as promoções → motor mede o impacto). Próxima OS.
- Noção de sazonalidade dentro de `dead_stock`.

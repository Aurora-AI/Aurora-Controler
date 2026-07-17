# Laudo: Executive Summary (backend) + Drill-down do Frontend — Design

**Data:** 2026-07-17
**Repos envolvidos:** `AuroraControler` (backend, Produto B / Oracle) e `aurora-frontend` (Next.js, consumidor)

## 1. Contexto

O `aurora-frontend` (`C:\Projetos\Aurora\aurora-frontend`) está construindo a UI do laudo executivo com um padrão de drill-down de 3 níveis (N0 número/frase → N1 "Mecanismo" → N2 "Evidência"), já provado em `src/components/InsightBoard.tsx`. O objetivo é elevar o nível de detalhamento do laudo ao padrão do relatório de referência "Laudo Diagnóstico — Auditoria Comercial EXRS (v4)".

Uma análise de gap (ground-truth, direto no código) mostrou que a maior parte das seções do relatório de referência já é construível hoje a partir de campos que `ExecutiveAuditReport` (`src/product_b/oracle/forensic_contracts.py:402-425`) já calcula — mas o frontend também depende de um bloco de agregados de topo (sumário executivo + plano de ação) que **não existe no contrato real do backend**. Esse bloco foi mockado à mão no frontend (`src/data/mock_audit_report.json`, campo `executive_summary`) e precisa ser promovido a cálculo real do backend antes que o frontend possa consumi-lo — por regra de arquitetura: **o frontend nunca calcula, só remodela/reformata dado que já chega pronto.**

## 2. Escopo desta rodada

- **Backend (`AuroraControler`, escopo desta sessão):** nova função `build_executive_summary(...)` que agrega os outputs já calculados pelos detectores existentes em três blocos honestos (perda operacional, capital parado, risco de LTV), mais uma lista leve de alarmes descartados e um plano de ação pré-ordenado.
- **Frontend (`aurora-frontend`, arquitetura decidida, implementação em sessão própria):** componentizar em `ExpandableCard` + seções + `selectors.ts` central (ver seção 6), consumindo os campos reais do `ExecutiveAuditReport` — incluindo, quando pronto, o novo `executive_summary` do backend.
- **Explicitamente fora desta rodada:** detector novo de margem por loja×SKU, coluna/sinal de promoção na planilha de origem, sazonalidade dentro de `dead_stock`, sazonalidade-para-planejamento, promoção-colaborativa. Ver seção 8 (ADR).

## 3. Backend — novos contratos Pydantic (`forensic_contracts.py`)

```python
class DiscardedAlarm(BaseModel):
    """Um candidato que o motor avaliou e decidiu NÃO reportar como achado, com o
    motivo — só cobre categorias que o motor genuinamente checa hoje (nunca padding)."""
    category: str          # "seasonal_drop" | "salesperson_ramp" | "store_cold_start"
    entity_id: str
    reason: str             # frase curta e honesta do motivo


class ActionPlanItem(BaseModel):
    """Item do plano de ação, pré-ordenado pelo motor (o frontend renderiza cego,
    nunca reordena)."""
    id: str
    category: str
    title: str
    description: str
    impact_brl: float
    nature: str              # "operational" | "capital" | "ltv_risk"
    tier: int                # 1 = perda certa/recorrente, 2 = capital recuperável, 3 = LTV projetado


class ExecutiveSummary(BaseModel):
    """Agregados de topo do laudo — cada campo vem DA FONTE (dos detectores),
    contado uma vez; nunca soma os números de outros campos deste mesmo modelo."""
    total_operational_loss: float   # Σ |contribution_margin| dos SKUs negativos em contribution_margin_alerts
    total_capital_frozen: float     # dead_stock[0].capital_frozen se houver, senão 0.0
    total_ltv_risk: float           # Σ historical_annual_value de churn_findings
    discarded_alarms: list[DiscardedAlarm] = Field(default_factory=list)
    action_plan: list[ActionPlanItem] = Field(default_factory=list)
```

`ExecutiveAuditReport` ganha um campo novo: `executive_summary: ExecutiveSummary`.

**Nota de nomenclatura:** o mock atual do frontend usa `total_discarded_alarms: int`. O contrato real usa `discarded_alarms: list[DiscardedAlarm]` — é uma mudança de shape deliberada (lista com motivo, não só contagem); o frontend deriva a contagem via `.length` no `selectors.ts` (isso é remodelagem, não cálculo — não há aritmética envolvida em contar itens de uma lista).

## 4. Backend — regras de negócio travadas

Estas regras são o contrato final; qualquer alteração passa por nova decisão explícita, não por ajuste silencioso durante implementação.

### 4.1 `total_operational_loss`
- Soma de `|contribution_margin|` para todo item de `contribution_margin_alerts` com `contribution_margin < 0` (granularidade: SKU, rede inteira — mesma granularidade que o campo já tem hoje).
- **Não soma** com `service_decomposition` (evita contar a mesma perda duas vezes).
- **Não exclui promoção** — não há sinal universal disso no dado de origem hoje (ver seção 8, ADR). Excluir por heurística de nome de produto violaria o princípio já documentado no código de nunca cravar string mágica; adicionar coluna nova é mudança de schema de entrada, fora de escopo.
- **Rótulo obrigatório no texto/copy do frontend que consome este campo:** nunca apresentar como "sangria estrutural confirmada". Rótulo correto: *"R$ X em SKUs vendendo abaixo da margem de contribuição — pode incluir promoção intencional, a confirmar."*
- Limitação documentada: não captura perda mascarada por loja específica (isso é `service_decomposition`, reportado à parte, não somado aqui).

### 4.2 As três naturezas nunca se somam num único número
`total_operational_loss`, `total_capital_frozen` e `total_ltv_risk` são três fatos de natureza contábil diferente (fluxo "a confirmar" / capital recuperável / LTV projetado e incerto) e **nunca são somados entre si** em nenhum campo do relatório. `latent_revenue` (receita latente) fica inteiramente fora de `ExecutiveSummary` — é cenário/hipótese, nunca fato, e não deve ser confundido com os três totais acima em nenhuma tela.

### 4.3 `discarded_alarms` (lista, não contagem)

**Decisão final (não fica para confirmar durante a implementação): a categoria "queda sazonal descartada" fica FORA de `discarded_alarms` nesta rodada.** `detect_revenue_leaks`/`_scan_yoy` (linha 312-348 de `commercial_auditor.py`) só instancia `RevenueLeakAnomaly` quando `sigma >= thresholds.revenue_drop_sigma` — ou seja, o motor não expõe, em nenhuma estrutura, os candidatos que passaram pelo ajuste de sazonalidade e ficaram *abaixo* do limiar (o "checado e limpo"). `seasonality_adjusted=True` marca uma anomalia real que sobreviveu ao ajuste, não um descarte. Não há dado de onde extrair essa categoria sem alterar `detect_revenue_leaks` para também emitir os "quase" — isso é mudança de detector, fora de escopo (ver seção 8, ADR: fica reservado para quando a sazonalidade virar análise de planejamento, não filtro).

`discarded_alarms` nesta rodada cobre só:
- Vendedor em rampa — `salesperson_performance` com `has_sufficient_tenure=False`.
- Loja em cold-start — `store_performance` com `has_sufficient_history=False`.

Não inclui "estoque sazonal", "promoção descartada" nem "queda sazonal descartada" (sem sinal no dado hoje para os três — ver seção 8). Consequência aceita: a seção "o que não é problema" fica mais enxuta nesta rodada — perde o exemplo mais forte de confiança (a queda sazonal óbvia), mas não mostra o que o motor não checou de verdade. É honesto agora e recupera força quando a camada de sazonalidade-para-planejamento (fora de escopo, seção 8) reframar o índice sazonal existente como orientação, não como filtro de alarme.

### 4.4 `action_plan[]`
- Mapeamento base fixo: `churn_findings` → item de natureza `ltv_risk`; `dead_stock` → item de natureza `capital`; `total_operational_loss` → item de natureza `operational`. Cada item só aparece se o total correspondente for > 0.
- Ordenação: por `tier` ascendente (1, 2, 3), e dentro do mesmo tier, por `impact_brl` descendente. Nunca ordenado só por R$ bruto.
  - Tier 1 — perda operacional certa/recorrente.
  - Tier 2 — capital recuperável (estoque morto).
  - Tier 3 — LTV projetado (churn, probabilístico).
- Receita latente nunca entra no `action_plan` (é cenário, não fato).

### 4.5 Travas de verificação
- O frontend renderiza os campos de `executive_summary` como vierem — nenhuma soma/ordenação adicional no lado do cliente. Isso é auditável: `selectors.ts` (frontend) não deve conter operadores aritméticos (`+`, `-`, `*`, `/`, `.reduce` com acumulador numérico) sobre valores financeiros — só sobre os campos de `executive_summary` prontos.
- Golden master (`tests/fixtures/golden_laudo_v3.json`) precisa ser regenerado deliberadamente para incluir o novo campo `executive_summary` — ver seção 7.

## 5. Backend — ponto de integração

`run_audit()` (`src/product_b/oracle/commercial_auditor.py:1240-1318`) já calcula todos os detectores antes de montar `ExecutiveAuditReport`. A nova função `build_executive_summary(...)` roda **depois** de todos os detectores (recebe os outputs já prontos: `contribution_margin_alerts`, `dead_stock`, `churn_findings`, `revenue_leaks`, `salesperson_performance`, `store_performance`) e antes da montagem final do `report = ExecutiveAuditReport(...)`, no mesmo padrão de `build_store_macro_summary` (função pura, sem novo acesso a `df`).

## 6. Frontend — arquitetura (para quando este backend estiver pronto)

Decidida em sessão de brainstorming, implementação em sessão própria:

- `src/lib/selectors.ts` — único lugar que toca no `ExecutiveAuditReport`: `.filter/.sort/.map/.groupBy`, zero aritmética.
- `src/components/ExpandableCard.tsx` — generaliza o padrão N0→N1→N2 já existente em `InsightBoard.tsx`.
- `src/components/sections/*.tsx` — um componente por seção do relatório-padrão.
- `src/types/audit.ts` — passa a espelhar exatamente `forensic_contracts.py` (remove o `executive_summary` inventado à mão, substitui pelo shape real definido na seção 3 deste documento assim que o backend entregar).
- `src/data/mock_audit_report.json` — regenerado a partir de uma rodada real do backend (não editado à mão), incluindo o novo `executive_summary`.

**Seções construíveis já hoje, sem depender deste backend** (dado real já existe, zero cálculo): ranking de lojas (`store_macro_summary`), loja a loja (`service_decomposition`), achados por tema (serviço/estoque/margem/cliente/vendedor via `service_reconciliation`, `dead_stock`, `gmroi`, `contribution_margin_alerts`, `product_trends`, `customer_concentration`, `rfm_champions`, `latent_revenue`, `churn_findings`, `salesperson_performance`), qualidade de dados (`cleaning`, `data_completeness`), anexo de metodologia (`thresholds`, copy pode vir das docstrings do `forensic_contracts.py`).

**Seções que dependem deste backend:** sumário executivo (KPIs de rede), plano de ação, "o que não é problema" — ficam **omitidas da UI** até `executive_summary` existir de verdade (decisão já tomada: nunca renderizar número simulado como se fosse real).

## 7. Golden master

`tests/fixtures/golden_laudo_v3.json` e `tests/test_golden_laudo_v3.py` fazem igualdade exata contra `report.model_dump(mode="json")` — adicionar `executive_summary` ao `ExecutiveAuditReport` quebra `test_laudo_matches_golden_master_exactly` por design. A regeneração do fixture é parte obrigatória da entrega desta funcionalidade, não um acidente a corrigir depois. `test_key_findings_from_the_meeting_stay_pinned` trava campos específicos hoje (`service_decomposition`, `dead_stock[0]`, `customer_concentration[0]`, `churn_findings`, `service_reconciliation`) — nenhum desses é alterado por este trabalho, mas o plano de implementação deve rodar a suíte completa (`python -m pytest tests/ -q`) antes de considerar a entrega pronta.

### 7.1 Verificar antes de congelar (passo obrigatório, não opcional)

Regenerar o fixture deixa o teste verde **por construção** — ele congela o que o código emitiu, bug incluso. Se `build_executive_summary` tiver um erro (soma errada, tier fora de ordem, receita latente vazando para dentro de um total), a regeneração assa esse erro dentro do golden master e o teste passa para sempre contra o valor errado. "Verde" aqui não significa "correto".

Ordem obrigatória da entrega:

1. Rodar o motor sobre o dado de referência (`consultoria_real_test.xlsx` ou o dataset usado em v4) e obter o `executive_summary` gerado.
2. **Conferir os valores à mão (ou com um teste independente que recalcula da fonte, não que compara contra o próprio dump) contra as regras da seção 4:**
   - `total_operational_loss` bate a soma de `|contribution_margin|` de todo item negativo em `contribution_margin_alerts`, e não inclui nada de `service_decomposition`?
   - `total_operational_loss`, `total_capital_frozen` e `total_ltv_risk` permanecem três campos separados em nenhum lugar somados entre si, e `latent_revenue` não vazou para dentro de nenhum dos três?
   - `discarded_alarms` só contém categorias com check real (rampa de vendedor, cold-start de loja — e sazonal, se e somente se um caso real for observável; ver 4.3) — sem item artificial/padding?
   - `action_plan` está ordenado por `tier` ascendente e, dentro do mesmo tier, por `impact_brl` descendente — e nenhum item de natureza `latent`/cenário aparece nele?
3. **Só depois dessa conferência** regenerar `golden_laudo_v3.json` e rodar a suíte completa (`python -m pytest tests/ -q`).

Regenerar sem o passo 2 é trocar a âncora de regressão por uma âncora falsa — o plano de implementação deve tratar este passo como parte da definição de "pronto", não como uma checagem opcional de qualidade.

## 8. Fora de escopo desta rodada (registrar como ADR / próxima OS)

- Detector novo de margem de contribuição por loja×SKU (perda mascarada por loja continua reportada só via `service_decomposition`, não soma em `total_operational_loss`).
- Coluna/sinal de promoção na planilha de origem (`is_promo`/motivo de desconto) — mudança de schema de ingestão (A1/C0), não de detector.
- Sazonalidade dentro de `detect_dead_stock` (hoje é meses-desde-movimento puro, sem noção de entressafra).
- Sazonalidade-para-planejamento (forecast do padrão medido).
- Promoção-colaborativa (dono marca promoções manualmente → motor mede o impacto real dela).

## 9. Riscos

- `total_operational_loss` sem exclusão de promoção pode gerar número maior do que o "real" aos olhos do cliente de negócio — mitigado pelo rótulo obrigatório "a confirmar" (seção 4.1); qualquer UI que remova esse rótulo para simplificar o texto reintroduz o risco que a regra foi desenhada para evitar. O rótulo é parte da correção, não um detalhe de copy — carrega a honestidade que o número sozinho não carrega.
- Regenerar o golden master sem verificação independente dos valores novos (seção 7.1) congela qualquer bug de `build_executive_summary` como "correto" permanentemente — o teste ficaria verde por construção, não por estar certo. Mitigado por tornar a verificação passo 2 obrigatório antes do passo 3 (regenerar) na seção 7.1.

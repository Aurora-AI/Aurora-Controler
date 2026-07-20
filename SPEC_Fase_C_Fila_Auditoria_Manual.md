# ENGENHARIA DE BACKEND: EXRS Data Oracle — Fase C: Triagem de Discrepâncias e Fila de Auditoria Manual

> **Status:** EXECUTADA (20/07/2026). Motor implementado, testado (TDD, 19 testes) e validado contra dado real — ver §7 (fora de escopo desta fase: fila só existe no motor/JSON, sem UI de painel/frontend ainda).
> **Origem:** achado de QA da Fase B — `discount_pct` de 337,78% (V-30/L9-Serra) na fórmula do Algoritmo 3, mais o padrão sistêmico L6/L7/L9 vendendo a ~1/4 do preço de tabela enquanto L1/L2 vendem acima. Decisão de produto registrada em 20/07/2026: distorção severa não é erro para descartar nem fato para exibir cru — é caso para triagem.
> **Subordinada a:** `laudo_executivo/EXRS_Spec_Laudo_Executivo_v4.md` §15 (a lei do fluxo) e §1 (audit_report congelado, procedência).

---

## 1. Contexto e Objetivo

O motor da Fase B mede desconto por vendedor (`Σdesconto / Σreceita`) — fórmula sem teto, que produz números como 337% quando o preço praticado destoa muito da tabela. O erro clássico seria (a) descartar como bug ou (b) exibir cru no laudo. Ambos destroem credibilidade.

Esta fase implementa a resposta correta, em duas camadas:

1. **Pré-classificação automática (o motor faz):** cruzar cada transação discrepante com as evidências que JÁ EXISTEM no dado — custo da própria linha, custo real de aquisição (aba Compras), lista de estoque morto, flag de promoção — e classificar deterministicamente o que tem sinal claro.
2. **Fila de auditoria manual (o humano decide):** somente o RESÍDUO não classificável vai para veredito humano, com todas as evidências anexadas para decisão em ~30 segundos por item.

**Princípio dimensionador (inegociável):** a fila manual recebe o resíduo, nunca o atacado. Uma fila com 300 itens é backlog morto; uma fila com 5 itens especificamente inexplicáveis é governança. No dado de referência, o trigger ingênuo ("desconto alto → fila") despejaria TODAS as transações de L6/L7/L9 na fila — inaceitável.

### Evidência empírica que fundamenta o desenho (verificada em 20/07/2026 contra `tests/fixtures/consultoria_real_test.xlsx`)

SKU `ARP-013`, três fontes do mesmo arquivo:

| Fonte | Campo | Valor |
|---|---|---|
| Compras (NF de entrada) | `custo_unit` | **R$ 309,11** (única compra, CP-00499) |
| Estoque (catálogo) | `custo_unit` / `preco_venda` | R$ 309,11 (bate com a NF) / **R$ 838,85 uniforme na rede** |
| Vendas em L2/L3 | `preco_unit` / `custo_entrada` | R$ 1.344–2.031 / R$ 564–855 (**custo divergente da NF**) |
| Vendas em L9 | `preco_unit` | R$ 172–248 (**~1/4 da tabela**) |

Conclusões que o motor deve ser capaz de tirar sozinho: (a) o preço de tabela único da rede não descreve a prática de nenhuma loja — assinatura de **erro cadastral/catálogo desalinhado**, não de vendedor descontista; (b) `custo_entrada` da venda diverge do custo real de aquisição — segunda assinatura cadastral independente; (c) nada disso é culpa do V-30, e o laudo NUNCA deve apresentá-lo como "vendedor que corrói margem" com base nesse número.

---

## 2. Arquivos-Alvo

- **Principal:** `src/product_b/oracle/commercial_auditor.py` (novo detector `detect_discrepancy_triage` + leitura da aba Compras).
- **Contratos:** `src/product_b/oracle/forensic_contracts.py` (novos modelos + limiares).
- **Mapeador:** `src/product_b/oracle/column_mapper.py` (vocabulário da aba Compras).
- **Gerador de laudo:** `laudo_executivo/build_laudo.py` (regra: pendente nunca vira fato) e template (renderização do bloco "em auditoria").
- **Testes:** `tests/test_discrepancy_triage.py` (novo).

---

## 3. Regras de Negócio

### 3.1. Os DOIS triggers por transação (nunca por agregado de vendedor)

A métrica de disparo da Fase B (`Σdesconto/Σreceita` por vendedor) NÃO é o trigger — ela mede agregado e não tem teto. Os triggers são por linha de venda:

**Trigger A — Desconto implausível sobre a tabela:**
```
desconto_sobre_tabela_pct = (preco_tabela − preco_praticado) / preco_tabela × 100
```
- Limitada a ≤100% por construção (preço praticado ≥ 0 após o filtro de devolução da Fase B).
- Dispara quando `desconto_sobre_tabela_pct > manual_review_discount_pct` (default: **60.0**, configurável em `AuditThresholdsConfig` — nunca número mágico).
- Desconto NEGATIVO além do simétrico (vender muito ACIMA da tabela, caso L1/L2) também é discrepância cadastral — dispara quando `< −manual_review_discount_pct`.

**Trigger B — Venda abaixo do custo (binário, severidade própria):**
```
preco_praticado < custo_entrada (da própria linha de venda)
```
- Independente do Trigger A: vender 60% abaixo da tabela mas acima do custo é agressividade comercial; vender 5% abaixo do custo é sangria. Nunca misturar os dois num limiar único.

**Exclusões herdadas (não redetectar o que já tem dono):**
- Linha com `forma_pagto = promo_payment_label` → já classificada como promoção (C3), entra na triagem PRÉ-classificada como `deliberate_liquidation` candidata, nunca como pendente.
- Devolução/estorno (`value ≤ 0`) → fora, mesmo filtro da Fase B.
- Serviço (`service_category_label`) → fora, não tem preço de tabela.

### 3.2. Pré-classificação automática (o coração da fase)

Para cada transação disparada, o motor monta o **vetor de evidências** e aplica a árvore de decisão, nesta ordem de precedência:

| # | Evidência | Fonte | Como calcular |
|---|---|---|---|
| E1 | `below_cost` | Vendas (linha) | Trigger B |
| E2 | `sku_in_dead_stock` | `dead_stock` (já existe) | SKU ∈ lista de estoque parado |
| E3 | `is_promo_flagged` | `payment_method` (já existe, C3) | forma_pagto = promoção |
| E4 | `cost_diverges_from_nf` | **aba Compras (NOVA leitura)** | `custo_entrada` da venda vs custo da compra mais recente do SKU anterior à data da venda; divergência > `nf_cost_divergence_pct` (default: **15.0**) |
| E5 | `store_systemic_pattern` | Vendas (agregado por loja×SKU) | mediana de `desconto_sobre_tabela_pct` da LOJA para aquele SKU também dispara o Trigger A — o desvio é da loja, não do vendedor |

**Árvore de decisão (determinística, precedência de cima para baixo):**

```
1. E5 (padrão sistêmico da loja) OU E4 (custo diverge da NF)
   → veredito automático: suspected_cadastral_error
     (o número é distorção de cadastro/tabela — NUNCA atribuir ao vendedor)

2. senão, E3 (promo) OU (E2 estoque morto E desconto alto sem E1)
   → veredito automático: deliberate_liquidation
     (desova consciente de capital parado — estratégia, não erro)

3. senão, E1 (abaixo do custo) sem nenhuma evidência mitigante
   → veredito automático: below_cost_sale
     (prejuízo oculto de balcão — alerta vermelho de governança)

4. senão (evidências ausentes ou contraditórias)
   → status: pending_manual_review  →  FILA MANUAL
```

Cada item classificado carrega o vetor de evidências completo (os cinco E's com valores) — o veredito automático é auditável, nunca uma caixa-preta.

### 3.3. Leitura da aba Compras (capacidade nova)

Vocabulário no `column_mapper.py`, dict separado (mesma razão dos existentes — "sku"/"custo" significam coisas diferentes por aba):

```python
_COMPRAS_ROLE_KEYWORDS = {
    "purchase_id": ["compra_id", "id"],
    "date": ["data", "emissao"],
    "sku": ["sku", "produto", "item", "codigo"],
    "qty": ["qtd", "quantidade"],
    "cost": ["custo"],
}
_COMPRAS_REQUIRED_ROLES = ("date", "sku", "cost")
```

- Custo de referência do SKU na data da venda = custo da compra **mais recente anterior** àquela data (merge_asof vetorizado, nunca laço). Sem compra anterior → E4 = indeterminado (não dispara, não inventa).
- `load_named_sheets` passa a incluir "Compras". Sem a aba → E4/E5 degradam graciosamente (a triagem roda com as evidências restantes; itens ambíguos vão para a fila — que é exatamente o comportamento certo quando falta dado).

### 3.4. O arquivo-irmão de vereditos humanos (`manual_review_<rodada>.json`)

O `audit_report.json` é congelado (Spec v4 §1) — o veredito humano é posterior ao congelamento e vive FORA dele:

```json
{
  "rodada": "v3",
  "audit_report_ref": "audit_report_v3.json",
  "audit_report_generated_at": "2026-07-20T14:32:01.123456+00:00",
  "reviews": [
    {
      "queue_item_id": "DTQ-0001",
      "verdict": "cadastral_error | below_cost_sale | deliberate_liquidation",
      "reviewed_by": "nome",
      "reviewed_at": "YYYY-MM-DD",
      "note": "texto livre curto"
    }
  ]
}
```

**`audit_report_generated_at` [INEGOCIÁVEL, achado de QA pós-execução]:** cópia exata de `ExecutiveAuditReport.generated_at` do relatório que a triagem originou. IDs de fila (`DTQ-0001`...) são sequenciais e POSICIONAIS — só estáveis dentro do MESMO relatório congelado. `apply_manual_review_verdicts` REJEITA (`ManualReviewMismatchError`) qualquer arquivo cujo `audit_report_generated_at` declarado não bata com o relatório sendo mesclado — nunca mescla em silêncio um veredito de outra rodada.

- `queue_item_id` referencia o item no bloco `discrepancy_triage` do relatório congelado (procedência preservada nos dois sentidos).
- `verdict` usa EXATAMENTE a mesma taxonomia dos vereditos automáticos — humano e máquina falam a mesma língua.
- Arquivo ausente = todos os itens da fila permanecem `pending_manual_review` (estado válido, renderizável).

### 3.5. Schema no relatório congelado

Novo bloco em `advanced_metrics` (Fase B já criou o namespace):

```json
"discrepancy_triage": {
  "triggered_count": 0,
  "auto_classified": [
    {
      "id": "DTQ-0001",
      "sku": "...", "store": "...", "salesperson": "...",
      "source_rows": [123, 456],
      "practiced_price": 0.0, "list_price": 0.0,
      "entry_cost": 0.0, "nf_cost": 0.0,
      "discount_over_list_pct": 0.0,
      "evidence": {"below_cost": false, "sku_in_dead_stock": false,
                    "is_promo_flagged": false, "cost_diverges_from_nf": true,
                    "store_systemic_pattern": true},
      "verdict": "suspected_cadastral_error",
      "verdict_source": "auto"
    }
  ],
  "manual_queue": [ { "...mesma estrutura, verdict: null, status: pending_manual_review" } ]
}
```

Agregação: um item por (SKU × loja × vendedor) com `source_rows` apontando as linhas — nunca um item por linha de venda (a fila explodiria), nunca um item por vendedor (perderia a granularidade da evidência).

### 3.6. Efeito retroativo sobre o Algoritmo 3 da Fase B

`SellerMarginCorrosionAlert` ganha um campo `tainted_by_triage: bool` — True quando parte relevante do desconto do vendedor vem de transações classificadas como `suspected_cadastral_error`. Vendedor com desconto inflado por tabela errada NUNCA pode ser `is_corrosive=true` (o V-30 do caso real é exatamente isso). A corrosão só é imputável ao vendedor quando o preço de referência é confiável.

---

## 4. Regras de Apresentação (build_laudo.py + template)

1. **Pendente nunca vira fato [INEGOCIÁVEL]:** item `pending_manual_review` não entra em nenhuma soma de sangramento, nenhum card, nenhum plano de ação. Renderiza-se, no máximo, como bloco "Em auditoria: N casos de desvio extremo em verificação contra a NF de compra" — o que demonstra processo, não fragilidade.
2. **Veredito `deliberate_liquidation`** (auto ou humano) migra para o **Ato 4** ("O que NÃO é problema"): "Descontos agressivos em N produtos — desova deliberada de estoque parado, decisão de caixa da gerência". É literalmente um alarme descartado com motivo.
3. **Veredito `below_cost_sale`** entra no capítulo Lucro Fantasma com o R$ agregado da sangria e o gancho de governança ("trava de aprovação no balcão").
4. **Veredito `cadastral_error`** NUNCA vira dor no laudo do dono como se fosse perda — vira achado de qualidade de dado ("sua tabela de preço não descreve sua operação — nenhum relatório seu é confiável até corrigir isso"), que é um gancho de venda tão forte quanto.
5. **Validador (`build_laudo.py`):** nova regra no checklist — laudo REPROVADO se qualquer número derivado de item pendente aparecer como fato na visão executiva.

---

## 5. Novos limiares (`AuditThresholdsConfig` — nenhum número mágico)

```python
manual_review_discount_pct: float = 60.0   # Trigger A, desconto sobre tabela
nf_cost_divergence_pct: float = 15.0       # E4, custo da venda vs NF de compra
# E5 usa manual_review_discount_pct sobre a MEDIANA loja×SKU (sem limiar novo)
```

## 6. Acceptance Criteria (Gate de Saída)

1. **Dimensionamento:** rodando contra `consultoria_real_test.xlsx`, a `manual_queue` final contém MENOS de 10% dos itens disparados — o resto sai pré-classificado. Se a fila sair maior, a árvore de decisão está errada, não o critério de aceite.
2. **Caso ARP-013/L9:** classificado automaticamente como `suspected_cadastral_error` (E4 + E5 verdadeiros). V-30 com `tainted_by_triage=true` e `is_corrosive=false`.
3. **PROMO-001:** ~~se disparar trigger, sai como `deliberate_liquidation` via E3~~ — **corrigido pós-execução (20/07/2026):** no dado real (`consultoria_real_test.xlsx`), PROMO-001 pratica R$ 112 contra custo de R$ 100 (12% de markup) — não dispara NEM o Trigger A (desconto <60%) NEM o B (não é abaixo do custo). O item corretamente NUNCA entra na triagem, porque não é uma discrepância implausível — é uma promoção legítima e discreta. O comportamento do E3 (promoção extrema → `deliberate_liquidation`) está coberto por teste sintético dedicado (`test_deliberate_liquidation_via_promo_flag`), já que o dado real não produz esse cenário. Critério de aceite revisado: **nenhum item PROMO aparece na triagem do dado real** (verificado: `[]`).
4. Graceful degradation: sem aba Compras, sem coluna `preco_venda`, sem `forma_pagto` — a triagem roda com as evidências disponíveis e nunca quebra o motor.
5. Vetorizado — nenhum laço sobre linha de venda (merge_asof para E4, groupby/transform para E5).
6. Golden master regenerado com diff auditado (processo padrão das fases anteriores).
7. `build_laudo.py` reprova laudo com pendência exibida como fato (teste do validador incluído).

## 7. Fora de escopo desta fase (registrado para não virar scope creep)

- UI da fila (aba no painel/frontend) — a fase entrega o dado estruturado e o contrato do arquivo de vereditos; a interface é da fase 2 do frontend (Spec v4 §14.4).
- OCR/leitura de NF real (XML/DANFE) — "NF" nesta fase = aba Compras do arquivo do cliente.
- Workflow de aprovação multi-nível — um veredito por item, sem alçadas.

## 8. Ordem de implementação (para a execução posterior)

1. Contratos + limiares (`forensic_contracts.py`) — TDD: testes de schema primeiro.
2. Vocabulário Compras (`column_mapper.py`) + inclusão em `load_named_sheets`.
3. Triggers A/B por transação (vetorizado).
4. Evidências E1–E5 + árvore de decisão.
5. Bloco `discrepancy_triage` no relatório + `tainted_by_triage` no Algoritmo 3.
6. Leitura do arquivo-irmão de vereditos + regra do validador no `build_laudo.py`.
7. Golden master (diff auditado) + critério de aceite #1 verificado contra o dado real.

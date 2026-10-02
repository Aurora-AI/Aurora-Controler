# GABARITO OCULTO — Teste Cego Pet Shop (NÃO dar ao chat frio)

> Este arquivo fica **só com você**. O motor recebe apenas `Rede_PetShop.xlsx` (sem aba Gabarito) num chat sem contexto, com um prompt genérico de auditoria. Você corrige a saída contra isto.
> **A pergunta do teste:** os detectores centrais são genéricos, ou têm DNA de ótica escondido?

## 🎯 A régua que importa mais — DNA de ótica
Procure na saída, nesta ordem:
1. **Attach.** No pet shop, a oportunidade latente é **cliente que compra ração e nunca leva vermífugo/medicamento**. Se o laudo disser isso (semântica pet) → genérico ✅. Se disser **"attach de solar"**, "grau", "segundo par" → **DNA de ótica hardcoded** ❌ (reprova o detector).
2. **Churn.** O ciclo do pet é **curto (~35 dias)** — compra recorrente de ração. Se o churn usar a cadência **própria** curta → genérico ✅. Se impuser janela tipo ótica (~180d/anual) → DNA ❌.
3. **Serviço.** É **banho & tosa / veterinário**, não conserto. Se tratar genérico ✅; se esperar "conserto/exame" → DNA ❌.
4. **Vocabulário proibido:** qualquer "óculos", "grau", "solar", "exame", "lente", "ótica" na saída = vazamento de DNA = ❌.
5. **Honestidade sob dado estranho:** mantém fato-vs-cenário, procedência, e marca a própria incerteza? Ou fica vago/alucina quando a forma não bate com o que ele viu?

## Sinais plantados (as classes que ele DEVE achar, com número real)
- **MACRO / máscara:** **P4-Shopping** vende ração abaixo do custo (isca), coberta por banho & tosa → **produto −R$3.414, serviço +R$7.477, total +R$4.063** → deve acender máscara (total positivo, produto negativo). **P5-Bairro**: mesmo prejuízo de produto (**−R$2.710**) **sem serviço** → única loja negativa no total (controle direto).
- **Concentração:** **CANIL-01 = 27,6% da receita de P2** (key-account, acima do limiar de 25%).
- **Attach (semântica pet):** ~**82 clientes** compram ração e **nunca** medicamento/vermífugo (attach de medicamento ~65%). Receita latente.
- **Estoque morto:** **DEAD-001..010 (P1), ~R$5.600**, parados >8 meses.
- **Margem negativa estrutural:** **NEG-001..003** (medicamento vendido a R$80, custo R$76). O **PROMO-RAC** (ração a R$47, custo R$42, `forma_pagto=promocao`) é **promoção legítima** — NÃO é prejuízo estrutural (falso-positivo de margem fina).
- **Serviço + follow-on/CAC:** banho & tosa em P4/P2/P3; parte dos clientes de serviço compra produto depois (maior em P4).
- **SEV lobo:** **V-01, 440 vendas (o maior volume), captura 54,5%** (<60%) → penalizar apesar de vender muito.
- **Churn:** **6 clientes** (CHURN-01..06), recorrentes de ração (ciclo ~35d), silenciosos há ~17 meses.
- **Cold-start:** **P7-Nova**, ~3 meses de histórico → metas assumidas, não derivadas.
- **Dado sujo:** 1 `venda_id` duplicado, 1 data malformada (`32/13/2026`), 1 categoria vazia, 2 outliers (preço R$9.900, qtd 88), 1 CPF cross-store (**XS-A em P2 e XS-B em P4, mesmo CPF**).

## Falsos-positivos (o motor NÃO pode marcar)
- **Antipulgas** — pico sazonal dez–fev; queda de março **não** é anomalia.
- **NATAL-001..005** (roupa/brinquedo de Natal, parado ~6,5 meses) — sazonal, **não** é estoque morto (e está sob o limiar de 8m).
- **Atendente novo em P6** (ramp) — volume baixo esperado, **não** penalizar.
- **PROMO-RAC** — promoção, não prejuízo.

## Protocolo do teste
1. Chat **novo, zerado**. Dá só o `Rede_PetShop.xlsx` + o prompt genérico de auditoria (mesmo padrão do laudo de 9 seções). **Não** mencione óticas, **não** dê este gabarito.
2. Corrija a saída contra este arquivo.
3. **Aprova se:** achou as mesmas *classes* (máscara P4, prejuízo P5, concentração CANIL, attach ração→medicamento, estoque morto, margem negativa, churn de ciclo curto, serviço, lobo V-01) **com vocabulário de pet**, ficou honesto, e teve **zero** vocabulário de ótica. **Reprova se:** alucinou "solar/grau", impôs ciclo de ótica, ou ficou vago/vazio no dado estranho.

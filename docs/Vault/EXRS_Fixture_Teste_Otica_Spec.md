# EXRS — Especificação da Fixture de Teste (Ótica) com Anomalias Plantadas

Fixture **híbrida**: base de aparência realista + anomalias **plantadas e documentadas**, em **duas variantes** (dado bom / dado ruim). Cada anomalia tem um resultado **esperado assertível** — o teste passa se o EXRS achar exatamente o que foi plantado, com o valor esperado.

---

## 1. Estrutura da planilha (abas e colunas)

- **Clientes**: `cliente_id, nome, telefone, cpf, data_cadastro, data_ultimo_exame`
- **Vendas**: `venda_id, data, cliente_id, vendedor_id, sku, categoria, tipo_venda, qtd, preco_unit, custo_entrada, forma_pagto`
  - `tipo_venda` ∈ {grau_simples, multifocal, solar_grau, lente_contato, acessorio}
- **Estoque**: `sku, categoria, custo_unit, qtd_atual, data_ultimo_mov, preco_venda`
- **Compras**: `compra_id, data, sku, qtd, custo_unit` (para CMV e estoque médio)
- **Vendedores**: `vendedor_id, nome`
- **Gabarito** (aba oculta): a lista de anomalias abaixo + os valores esperados

## 2. Parâmetros de controle (o "seed" — para os esperados baterem)

- 36 meses de dados; **200 clientes**; ~2.500 linhas de venda; **4 vendedores**; **300 SKUs**.
- **Ticket médio da loja = R$ 800**.
- **Ciclo mediano de recompra = 180 dias** → os 195 clientes "normais" têm intervalo entre compras de **150–210 dias** (nenhum ultrapassa 270 por acaso, para não gerar churn acidental).
- **Estoque total a custo = R$ 100.000**.
- Toda aleatoriedade com semente fixa (reprodutível).

## 3. Anomalias plantadas (o coração do teste)

| # | Onde plantar | O que plantar (valores exatos) | Fórmula / detector alvo | Resultado esperado (assertível) |
|---|---|---|---|---|
| 1 | Clientes/Vendas | 5 clientes (C-017..C-021), compravam a cada ~60 dias, última compra há 300–360 dias | **A3 Churn Invisível** | 5 clientes em churn (300 > 180×1,5=270). Perda = 5 × R$ 800 = **R$ 4.000**. Nenhum dos 195 normais entra em churn. |
| 2 | Clientes/Vendas | 10 clientes "Campeões" (alta recência/freq/valor) + os 5 do #1 sem recência | **A2 RFM** | 10 em Campeões (555); C-017..021 em Perdidos/Hibernando. |
| 3 | Vendas | Base de grau = 100 clientes; 70 levaram solar_grau, **30 não** | **A4 Receita Latente / Attach** | Attach solar = **70%**. Latente = 30 × 20% × R$ 300 = **R$ 1.800**. Lista dos 30. |
| 4 | Clientes | V1: 90% com telefone/CPF · V2: **25%** | **A1 Completude / Contingência** | V1 = 90% (motor roda). V2 = 25% < 30% → **pivota para estoque (B4/B5)**. |
| 5 | Estoque | 12 SKUs de armação sem movimento há 8 meses, custo R$ 800 cada | **B4 Estoque Morto** | Capital preso = **R$ 9.600**; índice = 9.600/100.000 = **9,6%**. Lista dos 12. |
| 6 | Vendas/Estoque | 3 SKUs: preço R$ 200, custo R$ 190, variáveis R$ 30 | **B5 Margem de Contribuição** | MC = 200−190−30 = **−R$ 20** (< 0). 3 SKUs sinalizados (o "soco"). |
| 7 | Estoque | Categoria "armação premium": margem bruta R$ 5.000, estoque médio custo R$ 8.000. Categoria "lente": margem R$ 12.000, estoque R$ 6.000 | **B2 GMROI** | Premium = 5.000/8.000 = **0,625** (< 1, alerta). Lente = 12.000/6.000 = **2,0**. |
| 8 | Estoque/Compras | Categoria "solar": CMV R$ 24.000, estoque médio R$ 4.000 | **B1 Giro / Cobertura** | Giro = **6**; Cobertura = 365/6 = **60,8 dias**. |
| 9 | Estoque/Vendas | 300 SKUs onde 60 (20%) = 80% da receita; 2 SKUs classe A com giro < 1 | **B3 Curva ABC × giro** | Classe A = **60 SKUs**; 2 alertas de "capital preso em item nobre". |
| 10 | Vendas | Linha/produto "AG-12": queda de **34%** num trimestre específico (ex.: Q2 do ano 2), desvio > 2σ, sem sazonalidade | **Detector de tendência (atual)** | Flag de vazamento de receita em AG-12 no trimestre. |
| 11 | Vendas | Solar sobe ~40% dez–fev **todo ano** (padrão regular) | **Detector de sazonalidade (atual)** | Reconhecido como **sazonal**, NÃO como anomalia (teste de falso positivo). |
| 12 | Vendas/Vendedores | V-3 (lobo solitário): IC=20, IA=80, IT=90, IR=50, IAd=60. V-1 (topo): IC=95, IA=90, IT=95, IR=80, IAd=70 | **SEV (pesos Construção 0,30/0,25/0,20/0,15/0,10)** | V-3 = **57,5** (penalizado apesar da boa conversão). V-1 = **89** (banda topo). |
| 13 | Vendas | P75: grau_simples R$ 600, multifocal R$ 1.800. V-2 atende 80% grau simples; V-4 atende 80% multifocal | **TMI ponderado pelo mix** | TMIhv de cada reflete o mix; o IT ponderado **não pune** V-2 por atender ticket menor. |

## 4. As duas variantes

- **Variante A — Dado bom**: completude 90%, datas e valores íntegros. O motor de recompra roda; espera-se achar as anomalias #1–#3, #5–#13.
- **Variante B — Dado ruim**: 75% dos cadastros sem telefone/CPF (completude 25%) e **12% das linhas de venda** com data quebrada ou valor ausente. Espera-se: A1 dispara a **contingência** (pivota para estoque), o detector de higiene reporta ~12% de linhas com falha, e o choque do relatório vem de #5 e #6 (estoque morto + prejuízo oculto).

## 5. Como usar

1. Gerar as duas variantes com a mesma semente.
2. Rodar o `exrs audit` em cada uma.
3. Comparar a saída com a aba **Gabarito**.
4. **Passa** se: achou exatamente as anomalias plantadas, com os valores esperados; não gerou falso positivo (#11); e na Variante B pivotou corretamente.
5. As fórmulas ainda não implementadas (RFM, GMROI, completude, attach, SEV, TMI) usam esta mesma fixture como alvo de construção — cada uma já tem o valor esperado aqui.

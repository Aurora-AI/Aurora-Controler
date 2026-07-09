# Fixture de Teste da Ótica + Achados do EXRS (Consultoria Aurora Óticas)

**Data:** 2026-07-06
**Gerador:** `tests/fixtures/create_otica_test_workbook.py` (seed fixa `20260706`)
**Variantes:** `otica_test_bom.xlsx` (completude 90%) · `otica_test_ruim.xlsx` (completude 25%, ~12% corrompidas)

## Propósito

Fixture **híbrida** (base realista + anomalias plantadas e documentadas) que valida o
`exrs audit` sobre dados de ótica no **meio do ruído** — não em dado limpo, que dá falsa
confiança. Serve a três fins: (1) provar que os 4 detectores atuais funcionam em dado de
ótica; (2) ser a fixture-mãe para construir as ~21 fórmulas da metodologia ainda não
implementadas (RFM, GMROI, completude, attach, SEV, TMI), cada uma com valor esperado; (3)
virar dataset de demo (parece real na frente do cliente).

As duas travas que a tornam assertível: **seed fixa** (ruído reprodutível, sem anomalias
acidentais) e **Gabarito versionado** (aba oculta + este doc = answer key).

## Estrutura do workbook

Aba **Vendas** é a primeira/ativa — o `exrs audit` de hoje lê só a sheet 0 (achado de
roadmap: precisa ler múltiplas abas). Demais abas (Clientes, Estoque, Compras, Vendedores)
alimentam as fórmulas futuras. Aba **Gabarito** (oculta) lista as 13 anomalias.

## Answer key — 13 anomalias plantadas

| # | Anomalia | Detector/Fórmula | Esperado | Hoje? |
|---|---|---|---|---|
| 1 | 5 clientes C-017..C-021, cadência ~60d, param 300-360d antes do fim | A3 Churn | 5 em churn; nenhum normal | ✅ **CONFIRMADO** |
| 2 | 10 Campeões C-001..C-010 alta recência/freq/valor | A2 RFM | Campeões (555) | ⏳ futuro |
| 3 | Base grau 100 clientes; 70 c/ solar, 30 sem | A4 Attach/Latente | attach 70%; latente R$1.800 | ⏳ futuro |
| 4 | Completude V1=90% · V2=25% | A1 Completude | V2<30% pivota p/ estoque | 🟡 parcial (higiene) |
| 5 | 12 SKUs DEAD-xx sem mov. 8m, custo R$800 | B4 Estoque Morto | R$9.600 preso | ⏳ futuro (lê só Vendas) |
| 6 | 3 SKUs MCNEG preço 200/custo 190/var 30 | B5 Margem | MC=-R$20 | ⏳ futuro |
| 7 | premium MB5k/est8k · lente MB12k/est6k | B2 GMROI | 0,625 / 2,0 | ⏳ futuro |
| 8 | solar CMV 24k/est médio 4k | B1 Giro | giro 6; cob 60,8d | ⏳ futuro |
| 9 | 60 SKUs = 80% receita; 2 classe A giro<1 | B3 ABC×giro | classe A=60 | ⏳ futuro |
| 10 | AG-12 queda 85% em 2024-05 (>2σ) | Vazamento (atual) | flag AG-12 2024-05 | ✅ **CONFIRMADO** |
| 11 | solar +40% dez-fev (regular) | Sazonalidade (atual) | sazonal, NÃO anomalia | ❌ **MOTOR FALHA (FP)** |
| 12 | V-3 lobo solitário · V-1 topo | SEV | V-3=57,5; V-1=89 | ⏳ futuro |
| 13 | P75 grau R$600/multi R$1.800; mix por vendedor | TMI ponderado | TMIhv reflete mix | ⏳ futuro |

## Achados da execução (o ouro do teste)

### ✅ O que o motor acertou
- **Churn (#1):** achou EXATAMENTE os 5 plantados (C-017..C-021), zero falso positivo entre
  os 195 normais. Após corrigir um bug da própria fixture (ver abaixo).
- **Vazamento AG-12 (#10):** flag preciso em `2024-05`, `sigma 4.12`, `severity high`.
- **Variante B (dado ruim):** limpeza reportou **11,9%** de linhas descartadas (182 data
  inválida + 173 valor ausente) — honesto, nunca mesclou errado, nunca escondeu.

### 🐛 Bug de PRODUÇÃO exposto pela fixture (corrigido)
`anonymize_customers` usava `string.ascii_uppercase[i]` — estourava `IndexError` acima de 26
clientes. A fixture da OS 1 tinha só 4 clientes; a de ótica tem 200 e **quebrou o `exrs audit`
na primeira execução**. Teria falhado em QUALQUER ótica real. Corrigido para esquema estilo
coluna de Excel (A..Z, AA, AB...) + teste de regressão `test_anonymize_scales_beyond_26_customers`.

### ❌ Limitações do MOTOR reveladas (roadmap, não bugs da fixture)
1. **Falso positivo de sazonalidade (#11):** o detector de vazamento acusou `SOLAR-SEASONAL`
   em `2024-03`, `2025-03`, `2026-03` — as quedas de março após o pico dez-fev. O detector
   não tem consciência de sazonalidade. **Precisa:** ajuste sazonal antes de sinalizar queda.
2. **Sem piso de materialidade:** 8 SKUs `LEN-xxx` flagrados só por variação normal de vendas
   esparsas cruzando 2σ. Numa fixture limpa isso nunca apareceu. **Precisa:** limiar mínimo de
   volume/receita (ex: ignorar séries abaixo de R$X/mês) para suprimir ruído.
3. **Lê só a primeira aba:** todo o estoque/compras (anomalias #5-#9) é invisível ao motor
   hoje. **Precisa:** ingestão multi-aba com papéis por aba.
4. **Dado ruim gera churn espúrio:** a variante B achou 6 churns (1 a mais) porque a corrupção
   removeu compras de um normal. **Precisa:** cruzar com o gate de completude (A1) antes de
   confiar no churn quando o dado é podre.

## Conclusão

O `exrs audit` de hoje entrega **2 dos 13 sinais de forma limpa** (churn preciso, vazamento
pontual) mas **falseia positivo em sazonalidade e ruído**, e é **cego para as 4 abas de
estoque**. A fixture cumpriu o papel: em vez de "passou em dado limpo", mapeou exatamente
onde o motor é confiável hoje e o que falta construir — a espinha do roadmap da OS 3+ do
Data Oracle.

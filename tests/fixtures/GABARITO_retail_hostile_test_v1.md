# GABARITO OFICIAL — `retail_hostile_test_v1.xlsx`

> **Status:** SELADO (30/07/2026). Folha de respostas imutável da fixture hostil #3.
> **Verificação:** todos os números abaixo foram conferidos célula a célula contra o
> arquivo real antes de selar (script de verificação reproduzido em §4). As três tabelas
> (consolidado, por vendedor, por SKU) fecham entre si em R$ 36.553,50 / R$ 25.150,00.
> **Regra:** se a consultoria extrair números diferentes destes, o sistema inventou dado
> (Zero Sicofagia). Se o motor divergir, o defeito é do motor — nunca ajuste este arquivo
> para o motor passar.
>
> **Natureza da fixture:** diferente de `consultoria_real_test.xlsx` (dado real de cliente)
> e `rede_oticas_beta_test.xlsx` (adversarial contra as *teses analíticas*), esta é
> adversarial contra o **parser/ingestão**: simula a planilha caótica de PME real —
> cabeçalho poluído, fórmulas quebradas, referência externa morta e manipulação de total.

---

## 1. Gabarito de Estrutura & Traps

| # | Anomalia injetada | Localização física | Comportamento exigido do motor |
|---|---|---|---|
| **1** | Cabeçalho duplicado + coluna fantasma | Linha 6 (colunas D, E, F) | Mapear D como `Preço Praticado`, isolar/ignorar E (`COL_E`), desambiguar F para `Custo Praticado` |
| **2** | Referência externa fantasma | `F11` | `='[Estoque_2025.xlsx]Geral'!$B$4` — acionar flag `EXTERNAL_REF` e pular a paridade sem derrubar o teste |
| **3** | Fórmula circular + divisão por zero | `G10` | `=G10/0` — **a célula referencia a si mesma** (ver nota ⚠️1). Isolar como anomalia, devolver `NaN`/`None` no schema, sem crash |
| **4** | Subtotal mesclado no meio do grid | `A22:C22` (ver nota ⚠️2) | Texto *"SUBTOTAL PARCIAL MARÇO (NÃO EXCLUIR)"* — descartar da contagem de transações (não é venda) |
| **5** | Fator de correção hardcoded (fudge factor) | `D40` | `=SUM(D7:D21)+SUM(D23:D37)+1500` — disparar alerta `CONSTANT` acusando manipulação de resultado |

### ⚠️ Duas correções de precisão aplicadas na selagem

**⚠️1 — Trap #3 não é apenas "divisão por zero".** `G10 = =G10/0` é uma **referência
circular** (a célula G10 aponta para si mesma) *somada* a uma divisão por zero. O padrão
correto da coluna seria `=D10*0.05`, como em todas as outras linhas. O Excel dispararia
alerta de circularidade *antes* de qualquer `#DIV/0!`. São duas classes de falha distintas
e exigem detectores distintos — descrever só como "div/0" subestima a armadilha.

**⚠️2 — O merge real é `A22:C22`, não `A22:G22`.** Verificado via `ws.merged_cells.ranges`:
os únicos ranges mesclados no arquivo são `A3:H3` e `A22:C22`. As células `D22`, `F22` e
`G22` **não estão mescladas** — carregam fórmulas SUM vivas (`=SUM(D7:D21)` etc.). Isso
importa: um parser que apenas "pule a linha mesclada" ainda enxergará três fórmulas nessa
linha e pode contá-las como transação.

---

## 2. Gabarito Matemático & Financeiro

### A. Consolidado do grid bruto

- **Transações válidas:** **30 linhas** (15 no lote 1 + 15 no lote 2, excluída a linha 22)
- **Faturamento transacional real (Σ coluna D):** **R$ 36.553,50**
- **Faturamento declarado em `D40` (com `+1500`):** **R$ 38.053,50**
- 🔴 **Gap de reconciliação / injeção:** **+R$ 1.500,00**
- **Custo transacional real (Σ coluna F):** **R$ 25.150,00** *(desconsiderando `F11`, referência externa não resolvível)*
- **Lucro bruto real:** **R$ 11.403,50** — margem bruta média **31,2%**

### B. Diagnóstico por vendedor

| Vendedor | Transações | Faturamento real | Custo gerado | Lucro bruto | Margem |
|---|---|---|---|---|---|
| Carlos Silva | 11 | R$ 15.230,50 | R$ 11.000,00 | R$ 4.230,50 | 27,8% |
| Ana Costa | 10 | R$ 9.982,00 | R$ 6.150,00 | R$ 3.832,00 | 38,4% |
| Roberto M. | 4 | R$ 6.401,00 | R$ 4.250,00 | R$ 2.151,00 | 33,6% |
| Marcos Lima | 5 | R$ 4.940,00 | R$ 3.750,00 | R$ 1.190,00 | 24,1% |
| **TOTAL** | **30** | **R$ 36.553,50** | **R$ 25.150,00** | **R$ 11.403,50** | **31,2%** |

### C. Diagnóstico por produto (curva ABC)

| SKU | Vol. | Faturamento real | Custo total | Margem | Achado forense |
|---|---|---|---|---|---|
| SKU-9921 | 9 | R$ 11.350,00 | R$ 8.900,00 | **21,6%** | Maior volume, puxado para baixo por 1 estorno de `(250,00)` na linha 9 |
| SKU-5541 | 3 | R$ 9.600,00 | R$ 6.300,00 | **34,4%** | Ticket alto (R$ 3.200/un.). Única linha sem nenhuma armadilha — serve de controle |
| SKU-8832 | 8 | R$ 7.153,50 | R$ 4.200,00 | **41,3%** | Maior margem da casa; 1 célula de custo contaminada por referência externa (`F11`) |
| SKU-3321 | 4 | R$ 6.000,00 | R$ 3.800,00 | **36,7%** | Performance estável |
| SKU-1044 | 6 | R$ 2.450,00 | R$ 1.950,00 | **20,4%** | ⚠️ Pior margem. Contém a linha 10 com fórmula quebrada e preço zerado (`R$ - `) |

### D. Convenções de parsing (resolvem as ambiguidades do arquivo)

Estas leituras são **parte do gabarito** — um motor que as interprete diferente produzirá
números diferentes e estará errado:

| Célula | Conteúdo bruto | Leitura correta | Por quê |
|---|---|---|---|
| `D7` | `" R$   1.450,00 - "` | **+1.450,00** | O traço final é *padding* do formato Contábil brasileiro, **não** sinal negativo (o negativo viria à esquerda ou entre parênteses) |
| `D9` | `"(250,00)"` | **−250,00** | Parênteses = negativo na notação contábil (é a troca/devolução) |
| `D10` | `"R$ - "` | **0,00** | Traço isolado = zero no formato Contábil |
| `D12` | `"1500,00"` | **1.500,00** | String numérica com vírgula decimal pt-BR |
| `A7..A37` | 4 formatos distintos | data | `15/03/2026` (BR), `03/15/2026` (US), `45731` (serial Excel), `2026-03-17` (ISO) |
| `F11` | fórmula externa | **não somável** | Referência morta — excluída do custo, nunca estimada |

---

## 3. Veredito de consultoria (o que o laudo DEVE concluir)

1. **Injeção de faturamento (+R$ 1.500,00).** O faturamento transacional é
   **R$ 36.553,50**, mas `D40` declara **R$ 38.053,50**. Há uma constante arbitrária
   somada à fórmula de fechamento — manipulação de resultado, não erro de cálculo.
2. **Corrosão de margem no SKU-1044.** Pior rentabilidade da operação (**20,4%**),
   acumulando erro de registro comercial e venda sem margem de contribuição.
3. **Concentração operacional em Carlos Silva.** Responde por **41,7%** do faturamento
   (R$ 15.230,50 de R$ 36.553,50) e concentra a única troca/devolução do período.

> **Nota de precisão:** 15.230,50 ÷ 36.553,50 = **41,66%**, que arredonda para **41,7%**
> (a versão anterior deste gabarito trazia 41,6%, resultado de truncamento). Testes
> automatizados devem assertar `round(pct, 1) == 41.7` ou usar tolerância ≥ 0,1pp.

---

## 4. Como reverificar este gabarito

```bash
python tests/fixtures/verify_gabarito_retail_hostile.py
```

O script recalcula os 22 números acima direto do `.xlsx` e falha se algum divergir. Rode-o
sempre que a fixture for tocada — o gabarito e o arquivo têm de morrer juntos.

---

## 5. Estado do motor contra este gabarito (baseline em 30/07/2026)

Registrado como **fotografia do estado atual**, não como aprovação:

| Trap | `exrs diagnose` (Produto A) | `exrs audit` (Produto B / Data Oracle) |
|---|---|---|
| #1 cabeçalho duplicado | ❌ não reporta | ⚠️ desambigua (`Preço Praticado_1`, `Unnamed`) mas não reporta |
| #2 referência externa | ✅ detecta, flag vermelha | — |
| #3 circular + div/0 | ❌ sem detector | — |
| #4 subtotal no grid | ❌ sem detector | — |
| #5 fudge factor +1500 | ⚠️ detecta, mas **afogado** (ver abaixo) | — |

**Achado principal do baseline:** o `+1500` é emitido como `hardcoded_value`, na **mesma
categoria e severidade** das 32 taxas de comissão `0.05` — que são lógica de negócio
legítima. Dos 33 riscos do relatório, 32 são ruído normal e 1 é manipulação do resultado
final, indistinguíveis entre si. **Detectar ≠ reportar:** uma constante somada a um
*total* é fraude; uma constante multiplicando uma *linha* é a regra de comissão.

**Produto B recusou o arquivo inteiro** (0 de 34 linhas aceitas) por não haver coluna de
cliente identificável — comportamento **correto** (não existe coluna de cliente na
planilha; inventá-la violaria a lei do motor), registrado aqui para não ser confundido
com falha. Nenhum crash em nenhuma das armadilhas.

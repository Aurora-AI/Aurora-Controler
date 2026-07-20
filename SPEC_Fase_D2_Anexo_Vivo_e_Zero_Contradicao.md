# ENGENHARIA: EXRS Data Oracle — Fase D (parte 2): Anexo Vivo (D1/D2) e Validador Zero Contradição (D3/Pilar 4)

> **Status:** EXECUTADA (20/07/2026). D1.0 + D1 + D3 no motor/`build_laudo.py`; D2 no template; v3 e Beta regeneradas com `--report`. Critérios de aceite 1, 2, 3, 4, 5, 6 verificados diretamente contra os artefatos. Pendente: Z3 (ver Spec v4 §16, nota de execução) e a limpeza declarada em §7 (fora de escopo desde o início).
> **Pré-requisito CONCLUÍDO:** Fase D parte 1 (commit `b0eb74c`) — o motor já exporta mix de margem por vendedor (Pilar 1), chaves de rastreabilidade em todo achado material (Pilar 2: `source_rows`/`sku_source_rows`/`sample_source_rows`) e índice de recuperabilidade da fila de churn (Pilar 3: `silence_to_cycle_ratio`). Esta OS consome esses campos; não os reimplementa.
> **Origem:** pedido do usuário (20/07/2026) — "quais são os 2 modelos? quem são os vendedores? que números provam?" — o laudo promete anexo em ≥4 pontos do corpo e o anexo não existe. Promessa de auditoria que quebra no primeiro clique é a pior falha possível de um laudo C-Level.
> **Subordinada a:** `laudo_executivo/EXRS_Spec_Laudo_Executivo_v4.md` §16 (a lei, criada junto com esta OS), §1 (congelado/procedência), §13 (template mestre), §15 (triagem).

---

## 0. Princípio arquitetural (governa tudo)

**O anexo é um formatador burro de dados já auditados.** `build_anexo` lê SOMENTE o `audit_report_<rodada>.json` congelado — zero recálculo, zero acesso à planilha, zero LLM. Se um número precisa existir no anexo e não está no relatório congelado, a correção é exportá-lo do MOTOR (como D1.0 abaixo), nunca calculá-lo na apresentação. Dois lugares produzindo "verdade" é o bug arquitetural que esta casa não comete.

**O corpo afirma; o anexo É a soma.** Depois desta OS, o card não "diz" R$ 63.414,44 — ele exibe o total de uma tabela que qualquer diretor pode refazer à mão. O validador (D3) transforma isso de retórica em construção: divergência de 1 centavo entre card e Σ(anexo) = build quebrado, nada é gerado.

---

## 1. Arquivos-Alvo

| Arquivo | Mudança |
|---|---|
| `src/product_b/oracle/column_mapper.py` + `commercial_auditor.py` + `forensic_contracts.py` | D1.0 apenas (papel opcional `description` no Estoque; export de nomes legíveis) |
| `laudo_executivo/build_laudo.py` | D1 (`build_anexo`, novo parâmetro `--report`) + D3 (validador sintático + semântico-numérico) |
| `laudo_executivo/EXRS_Template_Laudo_Executivo_v4.html` | D2 (Ato 6, bloco `anexo` no AUDIT_DATA, coluna SRC padrão) |
| `tests/` | `test_anexo_and_zero_contradiction.py` (novo) + regeneração dos goldens com diff auditado |
| `laudo_executivo/rodadas/` | v3 e Beta regenerados com anexo completo |

---

## 2. D1.0 — Última lacuna do motor: nomes legíveis de SKU

Verificado em 20/07/2026: `DeadStockFinding` exporta `skus` e `sku_source_rows`, mas NÃO a descrição legível ("Óculos Solar Polarizado A") — que existe na aba Estoque (`descricao`) e hoje só é lida pelo `enrich_audit_data.py` (que acessa a planilha, exatamente o que o anexo não pode fazer).

- Novo papel **opcional** `description: ["descricao", "nome"]` em `_ESTOQUE_ROLE_KEYWORDS` (não entra em `_ESTOQUE_REQUIRED_ROLES` — planilha sem a coluna não quebra nada).
- `DeadStockFinding` ganha `sku_descriptions: dict[str, str]` (default `{}`). Sem coluna de descrição → dict vazio → o anexo mostra só o código do SKU (fallback honesto, nunca inventa nome).
- Mesma exportação para os SKUs da triagem (Fase C): `DiscrepancyTriageItem` já tem `sku`; adicionar `sku_description: str | None`.
- Golden masters: regeneração com diff auditado (esperado: só os campos novos).

## 3. D1 — `build_anexo` (gerador determinístico)

### 3.1. Interface

`build_laudo.py` ganha o parâmetro opcional `--report rodadas/audit_report_<rodada>.json`:

- **Com `--report`:** o bloco `anexo` é DERIVADO do relatório congelado e injetado no AUDIT_DATA na renderização (o `audit_data_<rodada>.json` em disco permanece narrativo — o anexo nunca é editado à mão; Spec v4 §13.1 aplicada ao anexo).
- **Sem `--report`:** modo legado. Se o AUDIT_DATA mencionar anexo (ver D3 sintático), o build REPROVA com a instrução de passar `--report` — nunca gera laudo com promessa vazia.
- Guarda de integridade: `--report` deve conter `generated_at`; se o AUDIT_DATA declarar `audit_report_generated_at` (recomendado a partir desta OS), os dois devem bater — mesma trava anti-fusão-errada do `apply_manual_review_verdicts` (`ManualReviewMismatchError`).
- Vereditos manuais: se existir `rodadas/manual_review_<rodada>.json`, o build o funde via `apply_manual_review_verdicts` ANTES de derivar o anexo — a tabela de triagem sai com o estado pós-veredito.

### 3.2. As cinco seções do anexo (schema)

```json
"anexo": {
  "audit_report_generated_at": "...",
  "estoque_parado": {
    "total": 5101.24,
    "itens": [ { "sku": "SOL-030", "descricao": "Óculos Solar Polarizado A",
                 "qtd": 27, "custo_unit": 93.80, "capital_preso": 2532.60,
                 "meses_parado": 9, "src": "Estoque #13" } ]
  },
  "fila_reativacao": {
    "total": 63414.44, "clientes": 37,
    "itens": [ { "cliente": "Client_I", "ultima_compra": "2026-02-14",
                 "ciclo_dias": 45.0, "silencio_dias": 107, "indice_aquecimento": 2.38,
                 "valor_historico": 4494.48, "src": "Vendas #211, #490, ... (+9)" } ]
  },
  "vendedores": {
    "itens": [ { "vendedor": "V-30", "loja": "L9 - Serra", "receita": 12444.38,
                 "n_vendas": 101, "captura_pct": 88.1,
                 "margem_pct": -13.3, "margem_loja_pct": 5.2, "gap_pp": 18.58,
                 "flags": ["destroi_margem"],
                 "notas": ["desconto vem de tabela cadastralmente errada — não imputável (tainted)"],
                 "mix_top_desvio": { "categoria": "solar", "desvio_pp": 22.5, "margem_categoria_pct": -8.1 },
                 "src": "Vendas #2212, #2218, ... (amostra de 101)" } ]
  },
  "triagem_discrepancias": {
    "disparos": 38, "pendentes": 0,
    "itens": [ { "id": "DTQ-0001", "sku": "ARP-013", "descricao": "Armação Grife Titânio",
                 "loja": "Loja 01", "vendedor": "V-01", "veredito": "suspected_cadastral_error",
                 "veredito_origem": "auto",
                 "evidencias": ["custo da venda (R$320,00) diverge da NF (R$150,00)",
                                 "padrão repetido por 2+ vendedores da loja"],
                 "src": "Vendas #189, #526" } ]
  },
  "metodologia": {
    "limiares": [ { "nome": "dead_stock_months", "valor": 8,
                    "significado": "meses sem giro para capital contar como preso" } ],
    "limpeza": { "linhas_lidas": 1426, "aceitas": 1426, "descartes": {}, "podas_outlier": 0 }
  }
}
```

### 3.3. Regras de conteúdo [INEGOCIÁVEL]

1. **Todo item tem `src`** (Pilar 2): formato `"<Aba> #<linha>[, #<linha>...]"`. Acima do teto de exibição (herda `provenance_sample_cap` do motor): `"... (+N)"` ou `"(amostra de N)"` — o corte é sempre declarado, nunca silencioso.
2. **Fila de reativação ordenada por `indice_aquecimento` ASCENDENTE (mais quente primeiro), R$ como desempate** (Pilar 3) — nunca por R$ puro. Rótulo fixo "índice de aquecimento" com legenda de leitura (D2); NUNCA "probabilidade"/"score de retorno".
3. **Vendedores:** flags traduzidas para linguagem humana com a evidência ao lado (nunca o adjetivo sozinho): `destroi_margem` só aparece com `gap_pp` + a categoria que o explica; `tainted_by_triage` vira nota de absolvição explícita (Spec v4 §15.5 — culpa exige referência confiável); vendedor em rampa aparece como "em maturação — não avaliado", nunca omitido em silêncio.
4. **Pseudonimização preservada:** `Client_X` e IDs de vendedor, como já saem do motor. O anexo NUNCA reverte identidade.
5. **Sem teto de 5 no anexo** (o teto da Spec v4 §6 é da visão executiva; o anexo é exatamente o lugar do "excedente → anexo") — mas tabela acima de 50 linhas colapsa em "top 50 + total do restante", com o corte declarado.
6. **Números crus no JSON, formatação só na renderização** — o validador (D3) compara números, nunca strings formatadas.
7. **Vocabulário:** as mesmas substituições da Spec v4 §3.4 valem no anexo (é visão do cliente, não log de engenharia). Exceção única: códigos de SKU são permitidos (são o vocabulário do PRÓPRIO cliente), sempre acompanhados da descrição quando disponível.

## 4. D2 — Ato 6 no template (mudança de forma → registrada na Spec v4 §16)

1. Novo Ato após o plano: **"Ato 6 · Anexo de Evidências"**. Cada seção é um `<details>` recolhido (`<summary>` = título + total + contagem). O dono só desce se quiser; o consultor abre ao vivo quando o diretor pergunta "me prova".
2. **Vínculo corpo→anexo:** cada sangramento no AUDIT_DATA ganha `anexo_ref` (ex.: `"estoque_parado"`); o card renderiza "ver evidências no anexo ↓" como âncora real para a seção. O texto solto "no anexo" fica proibido quando não houver `anexo_ref` correspondente (fiscalizado no D3).
3. **Coluna SRC padronizada:** última coluna de toda tabela, monoespaçada, cinza discreto — presente, nunca protagonista.
4. **Legenda do índice de aquecimento** (uma linha, fixa): *"silêncio ÷ ciclo próprio do cliente — 1,2× = acabou de estourar o ritmo, ligar primeiro; 4× = frio, não queimar energia de balcão"*.
5. **Cores:** anexo é neutro (o vermelho já gritou no corpo — Spec v4 §4.2, vermelho é moeda escassa). Exceções: valor negativo de margem em vermelho de texto; nota de absolvição (`tainted`) no verde único.
6. **Fallback honesto herdado:** seção sem dado no relatório (ex.: sem Estoque) não renderiza — e o corpo, coerentemente, não pode referenciá-la (D3 pega).
7. Retrocompatibilidade: AUDIT_DATA sem bloco `anexo` renderiza o laudo como hoje (Atos 1-5) — o Ato 6 só existe quando o bloco existe.

## 5. D3 — Validador Zero Contradição (Pilar 4) [INEGOCIÁVEL]

Duas camadas novas no `build_laudo.py`, executadas ANTES de qualquer HTML ser escrito. Falhou uma → `exit 1`, lista de violações por seção da lei, nada é gerado.

### 5.1. Camada sintática (promessa ↔ existência)

- Varredura de todos os campos narrativos do AUDIT_DATA pela palavra "anexo" (case-insensitive): cada menção exige bloco `anexo` presente E a seção referenciada existente.
- Todo `anexo_ref` de sangramento deve resolver para uma seção real do bloco.
- Inverso também: seção do anexo cujo total participa de um card DEVE estar vinculada por `anexo_ref` — evidência órfã indica corpo e anexo dessincronizados.

### 5.2. Camada semântico-numérica (o corpo É a soma do anexo)

Para permitir comparação numérica (nunca parse de string formatada), cada sangramento monetário ganha o campo `valor: <número>` ao lado de `valor_display`. As igualdades verificadas, tolerância de **R$ 0,01** (mesma régua da soma do paradoxo, §1.3):

| # | Igualdade | Fontes |
|---|---|---|
| Z1 | `sangramento[caixa].valor ≡ Σ(anexo.estoque_parado.itens[].capital_preso) ≡ anexo.estoque_parado.total ≡ report.dead_stock.capital_frozen` | card ↔ anexo ↔ motor |
| Z2 | `sangramento[clientes].valor ≡ Σ(anexo.fila_reativacao.itens[].valor_historico) ≡ report Σ(churn_findings.historical_annual_value)` | card ↔ anexo ↔ motor |
| Z3 | sangramento monetário vindo da triagem (ex.: sangria abaixo do custo) `≡ Σ` dos itens correspondentes da triagem no anexo | card ↔ anexo |
| Z4 | `manchete.total_risco: <número>` (novo campo) `≡ Σ(sangramentos monetários .valor)`; `total_risco_display` deve ser o arredondamento declarado desse número (regra: truncado a milhar, "R$ 69 mil" ⇐ 69.038,22) — display nunca excede o fato | manchete ↔ cards |
| Z5 | `plano[].impacto` com `cenario: false` que espelha um sangramento deve ser IGUAL ao `valor` do sangramento correspondente (vínculo opcional `sangramento_ref` no item do plano; quando presente, a igualdade é obrigatória) | plano ↔ cards |
| Z6 | contagens: `fila_reativacao.clientes ≡ len(itens exibidos + corte declarado)` e idem para estoque/triagem — contagem exibida nunca diverge do detalhamento | anexo interno |

- Todas as igualdades comparam TAMBÉM contra o `audit_report` congelado quando `--report` está presente (terceira perna: card ↔ anexo ↔ motor). Divergência em qualquer perna = reprovado.
- Checklist §11 da Spec v4 ganha os itens correspondentes (laudo reprovado se qualquer Z falhar).

### 5.3. O que o validador NÃO faz

- Não valida texto narrativo semanticamente (frase é responsabilidade editorial; número é lei).
- Não recalcula nada do motor — compara números já existentes entre camadas. Se Z1 falha, o erro diz QUAL perna divergiu, mas a correção é sempre a montante (motor ou AUDIT_DATA), nunca um ajuste no validador.

## 6. Acceptance Criteria (Gate de Saída)

1. **v3 e Beta regenerados com Ato 6 completo** — abrir o laudo Beta e a pergunta original do usuário ("quais são os 2 modelos?") é respondida com nome, qtd, R$, meses e `src` por item (SOL-030/SOL-031 nomeados).
2. **Zero promessa vazia:** toda menção a "anexo" nos dois laudos resolve para seção real (verificado pelo próprio validador rodando no build).
3. **Validador testado nos DOIS sentidos:** (a) dados íntegros passam; (b) suíte de sabotagem — card com valor divergente da soma, `anexo_ref` órfão, menção a anexo sem bloco, `total_risco_display` inflado acima do fato — cada uma reprova com `exit 1` e mensagem apontando a igualdade violada (teste por caso, mesmo padrão do teste de reprovação da Fase 1 do padrão).
4. **Fila de reativação da v3:** primeiro item é o de MENOR `silence_to_cycle_ratio` (não o de maior R$) — a inversão do Pilar 3 visível no artefato final.
5. **V-30 no anexo da v3:** aparece com gap de margem E a nota de absolvição do desconto (tainted) simultaneamente — as duas verdades convivem, nenhuma apaga a outra.
6. Retrocompatibilidade: AUDIT_DATA antigo (sem `anexo`/`valor`/`total_risco`) continua gerando laudo Atos 1-5 sem erro — os campos novos são obrigatórios apenas quando o anexo é usado.
7. Golden masters com diff auditado (D1.0); suíte completa verde; goldens novos para o bloco `anexo` derivado das duas rodadas.

## 7. Fora de escopo (declarado)

- Exportação CSV/filtros interativos/busca — Fase 2 (`aurora-frontend`, Spec v4 §14.4).
- OCR/link para NF real — "NF" segue sendo a aba Compras.
- Renderização da fila manual da triagem como formulário editável — o veredito humano continua entrando pelo arquivo-irmão (§15.6).

## 8. Ordem de implementação

1. **D1.0** — export de descrições no motor (TDD; golden diff auditado; menor mudança primeiro).
2. **D1 + D3 no mesmo commit** — o gerador de anexo e o fiscal nascem juntos: nunca existe um anexo sem o validador que o confere (decisão da OS original da Fase D).
3. **D2** — Ato 6 no template (retrocompatível, defaults ausentes = laudo atual).
4. **Regeneração v3 + Beta** com `--report`; critérios de aceite 1-5 verificados um a um contra os artefatos reais; Spec v4 §16 marcada como executada.

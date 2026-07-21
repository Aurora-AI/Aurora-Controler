# ENGENHARIA: EXRS Data Oracle — Fase E (parte 1): Fechamento de QA + MVP da Física da Equipe (E1/E2/E3-v1)

> **Status:** EXECUTADA (21/07/2026) — Parte A e Parte B. Esta é a
> primeira OS executável derivada da planta-mãe `SPEC_Fase_E_Fisica_da_Equipe.md`. Cobre
> DUAS frentes que compartilham o mesmo validador (D3/Zero Contradição) e por isso nascem
> juntas: **(A)** Z3 (`below_cost_loss_brl`/`below_cost_total_brl` no motor,
> filtrando por `verdict=="below_cost_sale"` — achado de execução, ver §1.1; validado contra
> Beta real: R$522,54 batendo exatamente com `cap-lucro.valor`) + guarda de `anexo_ref`
> duplicado. Goldens regenerados com diff auditado (v3 ganhou `below_cost_total_brl=4661.13`,
> não previsto na SPEC original mas correto — a triagem já detectava essas vendas, só não
> viravam sangramento na narrativa). **(B)** o MVP da Fase E — E1 `detect_seller_flight_risk`
> (agregação mensal própria, gatilho em σ, ver §3.1), E2 `detect_incentive_misalignment`
> (chamado pós-taint, ver §3.2), E3-v1 `detect_skill_gaps` (corte por margem blendada da
> loja, decidido em revisão — ver §3.3), bloco `team_diagnostics` (paralelo a
> `executive_summary`, nunca somado), Ato 7 no template, `build_team`/Z7/Z8 no validador.
> Lei: `EXRS_Spec_Laudo_Executivo_v4.md` §17. 54 testes novos entre as duas partes (17 + 37),
> suíte completa verde, validado contra v3/Beta reais (E2 já detecta V-29/V-30 quando
> `commission_basis="gross_revenue"` é declarado).
> **Fora desta OS (viram OS próprias quando autorizadas):** E4 (aba Escalas) e E5 (aba
> Escalas + Tráfego/hora) — dependem de ingestão nova; ficam na planta-mãe §5/§6.
> **Pré-requisitos CONCLUÍDOS:** Fase D parte 1 (`b0eb74c`) e parte 2 (`755e68e` + QA
> `d519693`). O motor já exporta `SellerMarginMixProfile`/`SellerCategoryMixEntry` (E3),
> `SellerMarginCorrosionAlert` (E2), `SalespersonPerformance`/SEV (E1) e a triagem (Z3).
> **Subordinada a:** `laudo_executivo/EXRS_Spec_Laudo_Executivo_v4.md` §16 (Zero
> Contradição — será estendida, não duplicada), §3.4 (vocabulário), §1 (congelado/
> procedência); planta-mãe `SPEC_Fase_E_Fisica_da_Equipe.md` §0 (as 6 regras da casa).

---

## 0. Princípio arquitetural (governa tudo — herdado, não reinventado)

As seis regras da planta-mãe (§0) valem sem exceção. As duas que esta OS mais exercita:

1. **Nunca inventa R$.** Confirmado no código: a triagem (`DiscrepancyTriageItem`) exporta
   `practiced_price`/`entry_cost` **unitários**, sem quantidade nem perda agregada. Logo o
   R$522,54 de "venda abaixo do custo" hoje escrito à mão em `cap-lucro.valor` (Beta) **não
   tem número somável no relatório congelado**. Fechar Z3 de verdade NÃO é "mais uma checagem
   no validador" — é primeiro **exportar a perda do motor** (§1.1, estilo D1.0), senão o Z3
   compararia o card contra um total que não existe na fonte da verdade.
2. **Nunca inventa número → nenhum pilar de E1-E5 entra em `ExecutiveSummary`.** Mesmo E1
   (`carteira_em_risco_brl` reusa `SalespersonPerformance.total_revenue`, número que já
   existe) fica de fora de `total_operational_loss`/`_capital_frozen`/`_ltv_risk`/
   `action_plan` — ver §3.1 para o porquê (não misturar risco de evasão de vendedor com
   risco de churn de cliente sob o mesmo total). Todos os cinco pilares vivem em
   `team_diagnostics`, um bloco novo e paralelo ao ES, com seção narrativa própria (Ato 7).

**Um lugar produz a verdade.** Todo campo novo abaixo é derivado no MOTOR e apenas *formatado*
por `build_anexo`/template. Zero recálculo na apresentação.

---

## 1. PARTE A — Fechamento das pendências do QA da Fase D2

### 1.1. Z3 — sangramento vindo da triagem ≡ Σ dos itens no anexo (achado 🟡 do QA)

**Estado atual (verificado 20/07/2026):** `build_anexo` (`build_laudo.py:273-288`) renderiza
`triagem_discrepancias.itens` **sem campo monetário** (só `id`/`sku`/`veredito`/`evidencias`/
`src`). O validador `valida_zero_contradicao` implementa Z1, Z2, Z4, Z5, Z6 — **Z3 nunca foi
implementado**. `cap-lucro.valor=522.54` (Beta) só é protegido por Z4 (contra a manchete).

**Motor (pré-requisito de Z3 — estilo D1.0):**
- `DiscrepancyTriageItem` ganha `below_cost_loss_brl: float | None = None`.
  **Correção de fórmula (achado de revisão):** o rascunho original desta OS definia a perda
  como `Σ qtd × (entry_cost − practiced_price)` sobre as linhas do grupo — mas `practiced_price`
  e `entry_cost` no `agg` de `detect_discrepancy_triage` (`commercial_auditor.py:1714-1719`)
  são **médias do grupo inteiro** (`.mean()`), e `below_cost` é agregado com `.any()`: um grupo
  pode ter `below_cost=True` com só ALGUMAS linhas abaixo do custo. Aplicar a média do grupo
  sobre a quantidade total do grupo superestima a perda (mistura linhas acima e abaixo do
  custo). **Fórmula correta, calculada por LINHA antes do `groupby`:** para cada linha de
  `candidates` com `unit_price < entry_cost`, `linha.loss = linha.qty × linha.entry_cost −
  linha.value` (equivalente a `qty × (entry_cost − unit_price)`, já que `value = unit_price ×
  qty` — usar `value` direto evita reconstruir `unit_price × qty` e herda a mesma robustez do
  piso `qty_safe` já aplicado). `below_cost_loss_brl` do grupo = **soma** de `linha.loss` só
  nas linhas do grupo que disparam `below_cost`; agregação nova no `agg` (`sum` de uma coluna
  de perda pré-calculada em `candidates`, não uma derivação pós-`groupby` a partir das médias).
  `None` (nunca `0.0` fingido) quando o grupo não disparou por `below_cost` ou `entry_cost` é
  indeterminável (mesmo fallback honesto de `discount_over_list_pct`). Trabalho de motor, com
  teste dedicado que prova a diferença entre a fórmula errada (média × qtd total) e a correta
  (soma por linha) num grupo misto (algumas linhas abaixo do custo, outras não).
- `DiscrepancyTriage` ganha `below_cost_total_brl: float | None`.
  **Correção encontrada na execução (verificado contra `rede_oticas_beta_test.xlsx` real):**
  `below_cost` é a EVIDÊNCIA, não o veredito final — ARP-013/LNT-900 (Beta) disparam
  `below_cost=True` mas são reclassificados para `suspected_cadastral_error` (custo
  cadastrado errado, não sangria real — mesmo princípio de "culpa exige referência
  confiável", §15.5, já aplicado à corrosão de margem). Somar TODOS os itens com
  `below_cost_loss_brl` não-nulo deu R$2.665,27; somar só os itens com veredito
  `below_cost_sale` (ARP-020/ARP-021, 20 vendas) deu **R$522,54 — exatamente o valor já
  escrito à mão em `cap-lucro.valor`**, confirmando a fórmula certa por fora. Fórmula
  final: `below_cost_total_brl` = Σ `below_cost_loss_brl` dos itens com `verdict ==
  "below_cost_sale"` (nunca `"is not None"` sozinho — mesmo padrão de
  `total_operational_loss` excluir alertas `promotional=True`). `below_cost_loss_brl`
  continua preenchido no item cadastral (fato honesto por linha: "esta venda, ao custo
  CADASTRADO, ficou abaixo dele") — só não entra no total agregado. `None` quando
  nenhum item tem veredito `below_cost_sale` (retrocompatível, Z3 não aciona).
- Golden masters regenerados com diff auditado (esperado: só os dois campos novos + o total
  de Beta materializado; v3 não tem sangria abaixo do custo → `None`, sem mudança de valor).

**Apresentação:**
- `build_anexo`: cada item de `triagem_discrepancias` ganha `perda_abaixo_custo` (=
  `below_cost_loss_brl`, omitido quando `None`); a seção ganha `total_abaixo_custo` (=
  `below_cost_total_brl`, omitido quando `None`).
- Vínculo card↔anexo: o sangramento correspondente (Beta `cap-lucro`) recebe
  `anexo_ref: "triagem_discrepancias"` e seu `valor` passa a espelhar `total_abaixo_custo`.

**Validador — nova checagem Z3 em `valida_zero_contradicao`:**
```
Z3 (só quando anexo.triagem_discrepancias.total_abaixo_custo presente):
  Σ(itens[].perda_abaixo_custo, só veredito=="below_cost_sale") ≡ total_abaixo_custo (interno)
  card[anexo_ref=triagem_discrepancias].valor ≡ total_abaixo_custo      (card ↔ anexo)
  se report presente: report...discrepancy_triage.below_cost_total_brl
        ≡ total_abaixo_custo                                            (card ↔ anexo ↔ motor)
```
Mesma tolerância `TOLERANCIA_ZERO_CONTRADICAO` (R$0,01). Cada perna guardada pela presença
do seu campo (retrocompatível: rodada sem sangria abaixo do custo não aciona nada).

### 1.2. Guarda de `anexo_ref` duplicado (achado 🟢 do QA)

`_sangramento_por_ref` retorna só o primeiro match; dois sangramentos com o mesmo `anexo_ref`
(erro de copiar/colar) fariam o segundo escapar de Z1/Z2/Z3 em silêncio. Adicionar a `valida()`
(checklist §11) uma verificação: `anexo_ref` deve ser único entre os `sangramentos`; duplicado
= `erro(...)`. Custo baixo, fecha o furo antes que o Ato 7 adicione mais refs.

### 1.3. Atualização da lei
- Spec v4 §16: marcar Z3 como **EXECUTADO**; documentar `below_cost_loss_brl`/
  `below_cost_total_brl` como a fonte-da-verdade do total de sangria abaixo do custo.
- `SPEC_Fase_D2_...md`: remover Z3 da lista de pendências no cabeçalho de status.

---

## 2. PARTE A — Acceptance Criteria (fechamento de QA)

1. **Z3 reprova sabotagem:** com `--report`, corromper `below_cost_total_brl` do motor OU o
   `cap-lucro.valor` do Beta → `exit 1` citando a perna Z3 violada. Íntegro passa.
2. **Beta materializa o total:** `cap-lucro.valor` deixa de ser autoral e passa a espelhar
   `below_cost_total_brl` derivado do motor; o Ato 6/triagem exibe `perda_abaixo_custo` por
   item abaixo-do-custo (ARP-020/ARP-021) e o `total_abaixo_custo` da seção.
3. **v3 intacto (corrigido — achado de QA):** a premissa original ("v3 não tem sangria abaixo
   do custo") era falsa — verificado após regenerar: v3 tem 56 itens com veredito
   `below_cost_sale`, `below_cost_total_brl=4661.13`. O anexo da v3 passa a exibir esse total
   na seção `triagem_discrepancias` (Z3 aciona parcialmente: as pernas "itens≡total" e
   "anexo≡motor" rodam e passam; a perna "card≡total" não roda porque nenhum sangramento
   referencia essa seção). O que PERMANECE verdadeiro e é o que este critério realmente
   protege: `cap-lucro` da v3 (qualitativo, "2 lojas") continua sem `valor`/`anexo_ref` — a
   narrativa não promove essa cifra a sangramento, e isso não é um erro, é uma decisão
   editorial válida (nem todo total do anexo precisa virar card, mesmo padrão de
   `vendedores`/`metodologia`).
4. **`anexo_ref` duplicado reprova** com mensagem clara; refs únicos passam.
5. Golden masters com diff auditado; suíte completa verde; regressões novas por caso.

---

## 3. PARTE B — MVP da Física da Equipe (E1 + E2 + E3-v1)

### 3.0. Novo bloco no relatório: `team_diagnostics`

`ExecutiveAuditReport` ganha `team_diagnostics: TeamDiagnostics = Field(default_factory=...)`
(sempre presente, listas vazias quando o dado de origem falta — mesmo graceful degradation de
`AdvancedMetrics`). Schema:
```python
class TeamDiagnostics(BaseModel):
    flight_risk: list[FlightRiskAlert] = Field(default_factory=list)          # E1
    incentive_misalignment: list[IncentiveMisalignmentAlert] = Field(...)     # E2
    skill_gaps: list[SkillGapDiagnosis] = Field(default_factory=list)         # E3-v1
    # occupancy_profiles / scheduling_mismatches → Fase E parte 2 (E4/E5)
```
Todos os detectores abaixo excluem pseudo-entidade (`is_pseudo_entity`) e usam
`benchmark_population` para qualquer régua entre pares — nunca reimplementam nem comparam
contra a rede inteira. Todo achado carrega `sample_source_rows` (teto `provenance_sample_cap`).

### 3.1. E1 — `detect_seller_flight_risk` (prioridade #1)

**Correção de grão (achado de revisão):** "reusa a fórmula do SEV/da corrosão" descreve a
ABORDAGEM, não uma chamada direta às funções existentes — verificado que ambas têm grão
incompatível com série mensal: `detect_salesperson_performance` calcula `capture_rate_pct`
como escalar único sobre o período inteiro (`commercial_auditor.py:830`, `df.groupby(
"salesperson").size()`, sem quebra por mês); `detect_seller_margin_corrosion` agrupa só por
`(store, salesperson)` (linha 1240), também sem mês. `detect_seller_flight_risk` implementa
sua PRÓPRIA agregação mensal (groupby adicional por `period = date.dt.to_period("M")`),
reaplicando a MESMA fórmula de cada métrica (capture = capturado/total; discount =
(list_price − unit_price)/list_price; ticket = value/qty) por (vendedor, mês) — não chama
`detect_salesperson_performance`/`detect_seller_margin_corrosion` para isso.

**Correção de gatilho (achado de revisão):** o rascunho original não definia quando uma perna
"dispara" — qualquer oscilação para baixo acenderia. Fechado assim: mesma mecânica de
`detect_revenue_leaks` (desvio em σ sobre a variabilidade da PRÓPRIA série, nunca um
ponto-percentual fixo — evita 3 números mágicos novos e mantém o mesmo idioma estatístico já
auditado). Para cada perna, com a série mensal do vendedor ordenada:
- `historico` = todos os meses exceto os últimos `flight_risk_trend_window_months`;
  `recente` = os últimos `flight_risk_trend_window_months` meses.
- Guarda: `len(historico) >= 3` (mesmo piso de `detect_revenue_leaks`) — sem isso a perna não
  é avaliada (não é "não disparou", é "sem base estatística pra avaliar", mesma distinção que
  `has_sufficient_tenure` já faz alhures).
- `std = historico.std()`; se `std == 0` ou `NaN`, a perna não é avaliada (série sem
  variabilidade não sustenta um σ).
- `delta = historico.mean() - recente.mean()` para captura/ticket (queda = delta positivo);
  `delta = recente.mean() - historico.mean()` para desconto (alta = delta positivo).
- Perna dispara quando `delta / std >= thresholds.flight_risk_trend_sigma`.
3 pernas, cada uma avaliada só se o dado existir: (1) captura, (2) desconto — **requer
`list_price` em Estoque**, sem ela a perna simplesmente não é avaliada (nunca inventa preço de
tabela) —, (3) ticket médio.

Gate: `has_sufficient_tenure=False` (mesmo do SEV, mesmo `sev_ramp_min_days`) nunca entra —
sem histórico suficiente, tendência não tem base (gate por DIAS; o `len(historico)>=3` acima é
um segundo guarda independente, por MESES COM VENDA — um vendedor pode ter tenure em dias
suficiente e ainda não ter 3+ meses com venda registrada, ex. sazonal). Vira achado só com
`len(risk_flags) >= flight_risk_min_flags`.

**Contrato `FlightRiskAlert`:** `salesperson, store, months_evaluated, capture_trend_pct,
discount_trend_pp, ticket_trend_pct, risk_flags: list[str], carteira_em_risco_brl,
sample_source_rows`. `carteira_em_risco_brl = SalespersonPerformance.total_revenue` do período
— **é receita BRUTA** (inclui venda anônima e estorno negativo, por construção do próprio
`SalespersonPerformance`, docstring `forensic_contracts.py:614-616`); a docstring de
`FlightRiskAlert` carrega a mesma ressalva explícita, para não virar um número que o diretor
possa contestar sem aviso.

**Thresholds novos (`AuditThresholdsConfig`):** `flight_risk_trend_window_months: int = 3`,
`flight_risk_trend_sigma: float = 1.5` (mesma ordem de grandeza de `seller_corrosion_std_
multiplier`, calibrar contra a fixture sintética do §3.5), `flight_risk_min_flags: int = 2`.

**Decisão de arquitetura verificada no código (correção de um erro do rascunho anterior
desta OS):** `ActionPlanItem.nature` (`"operational"|"capital"|"ltv_risk"`) já existe, mas
vive dentro de `ExecutiveSummary.action_plan` — mecanismo do motor fechado em **até 3 itens
fixos**, um por natureza (`commercial_auditor.py`, função de montagem do ES), e cuja própria
docstring proíbe somar naturezas contábeis diferentes. `build_laudo.py` nunca lê
`executive_summary`/`action_plan` hoje (verificado: zero ocorrências) — o `plano[]` do
`audit_data.json` é uma camada narrativa paralela, sem campo `nature`. Esta OS **não estende
`ExecutiveSummary`/`total_ltv_risk`/`action_plan`** para incluir E1: fazer isso somaria risco
de evasão de vendedor com risco de churn de cliente sob um único `total_ltv_risk`, violando a
própria regra da casa ("naturezas nunca são somadas entre si") e quebrando o invariante
documentado de "até 3 itens fixos". `carteira_em_risco_brl` fica só na camada narrativa
(Ato 7 + `plano[]`, ver §3.4) — vínculo por `team_ref` (novo campo, espelha `sangramento_ref`),
nunca por `nature`.

### 3.2. E2 — `detect_incentive_misalignment` (prioridade #2)

Não recalcula margem — **anota** achados que já existem. Fato de negócio declarado na config
(não planilha), no espírito de `service_category_label`/`promo_payment_label`:
```python
commission_basis: str = "unknown"   # "gross_revenue" | "contribution_margin" | "mixed"
```
`"unknown"` (default) → detector retorna vazio e emite `DiscardedAlarm(category=
"commission_basis_unknown", reason="estrutura de comissão não informada — ponto cego não
avaliado")`. Nunca adivinha a base a partir de receita/custo.

Quando `commission_basis == "gross_revenue"` E um vendedor tem `is_margin_destructive=True`
(E3/Mix) OU `is_corrosive=True` (corrosão), emite `IncentiveMisalignmentAlert` referenciando o
achado original + explicação estrutural fixa. `mixed`/`contribution_margin` não geram alerta.

**Contrato `IncentiveMisalignmentAlert`:** `salesperson, store, commission_basis,
linked_finding_type: "margin_mix"|"margin_corrosion", linked_finding_summary, recommended_fix`
(string fixa por `commission_basis`). **Sem R$ próprio** — não entra nos totais.

**Dependência de ordem em `run_audit` (achado de revisão — bloqueante se ignorado):**
`seller_margin_corrosion` é MUTADO in-place depois de calculado — o bloco de absolvição por
triagem (`commercial_auditor.py:2192-2202`, "Fase C, culpa exige referência confiável") seta
`alert.is_corrosive = False`/`tainted_by_triage = True` para pares `(loja, vendedor)` cuja
discrepância veio de erro cadastral. Só DEPOIS disso a lista mutada entra em `AdvancedMetrics`
(linha ~2205). `detect_incentive_misalignment` deve ser chamado **depois** desse bloco de
absolvição, consumindo a mesma lista já mutada (nunca uma cópia pré-taint) — senão acusa de
incentivo mal desenhado um vendedor que o motor já absolveu por cadastro errado, exatamente a
dessincronia que o taint existe para evitar (§15.5 da lei). Mesma exigência vale por
transitividade para `is_margin_destructive` (Mix/E3): não sofre taint hoje, então não tem
esse risco, mas o teste de E2 deve cobrir explicitamente o caso `is_corrosive=True→False` por
taint para travar a ordem certa por regressão.

### 3.3. E3-v1 — `SkillGapDiagnosis` proxy (prioridade #3)

Nova leitura sobre `SellerCategoryMixEntry` (já existe, com `mix_deviation_pp` e
`category_margin_pct`). Para cada categoria onde o vendedor vende **menos** que o padrão da
loja (`mix_deviation_pp < -skill_gap_avoidance_pp`) E `category_margin_pct` da categoria é
**maior que `store_margin_pct`** (a margem blendada da própria loja, já em
`SellerMarginMixProfile` — decisão fechada nesta revisão: reusa um número que já existe no
relatório em vez de um corte posicional como "top-1"/"top-quartil", que exigiria threshold
novo e se comporta mal em lojas com poucas categorias) → `SkillGapDiagnosis` com
`hypothesis="possível déficit de treinamento/segurança técnica em <categoria>"`, **rotulado
explicitamente como hipótese derivada de padrão de mix**, nunca "diagnóstico confirmado"
(vocabulário obrigatório, mesma disciplina de `latent_revenue`). `is_proxy=True` sempre;
`data_gap="conversao_real_requer_aba_orcamentos"` (a v2 com conversão real via aba Orçamentos
fica na planta-mãe, não bloqueia a v1).

**Contrato `SkillGapDiagnosis`:** `salesperson, store, category, mix_deviation_pp,
category_margin_pct, hypothesis, is_proxy: bool = True, data_gap: str | None`. **Sem R$.**
Threshold: `skill_gap_avoidance_pp: float`.

### 3.4. Ato 7 — Física da Equipe (template + validador)

- Template: novo **Ato 7 · A Física da Equipe**, no mesmo padrão `<details>` recolhido do Ato
  6 (Anexo), guardado por `if (D.team) { ... }`. Retrocompatível: AUDIT_DATA sem `team` gera
  Atos 1-6 sem erro. Subseções: Evasão (E1, com `carteira_em_risco_brl` e `risk_flags`
  nomeadas), Comissionamento (E2), Habilidade (E3, sempre rotulado "hipótese").
- Vocabulário: E1/E2/E3 passam por `VOCAB_PROIBIDO`/`caca_vocabulario` como qualquer campo
  narrativo. "risco de evasão" e "hipótese" são permitidos; nada de score opaco único.
- `build_anexo`/novo `build_team`: formatador burro que lê só `report.team_diagnostics`
  congelado — zero recálculo. Injeta `dados["team"]` quando `--report` presente. Cada item de
  `team.flight_risk` ganha uma chave estável (`"<vendedor>@<loja>"`, mesmo padrão de
  identidade usado no resto do anexo) para ser referenciável de fora.
- **Novo campo `team_ref` em `plano[]`** (audit_data.json) — espelha `sangramento_ref`
  (§16.2), mas resolve contra `team.flight_risk` em vez de `anexo`. Necessário porque
  `_sangramento_por_ref`/Z1-Z6 só resolvem contra o bloco `anexo` (Ato 6); `team` (Ato 7) é
  um bloco novo e separado — não dá pra reusar `anexo_ref` para isto. Nova função
  `_item_por_team_ref(dados, anexo_ref_da_secao, chave)` espelhando `_sangramento_por_ref`.
- **Zero Contradição estendido (não duplicado):** `valida_zero_contradicao` ganha:
  - **Z7** — E1: `plano[].impacto` com `team_ref` vinculado a um item de `team.flight_risk`
    ≡ `carteira_em_risco_brl` daquele item (mesma regra de igualdade monetária de Z5, mesma
    tolerância, só que resolvendo contra `team` em vez de `anexo`). Só aciona quando
    `team_ref` está presente — retrocompatível com `plano[]` que não referencia evasão.
  - **Z8** — resolução de menção: **escopo restrito a esta OS (achado de revisão)** — só
    "evasão"/"incentivo"/"hipótese"/"habilidade" (vocabulário de E1/E2/E3). "Capacidade" e
    "escalonamento" são E4/E5, fora desta OS — nenhum item de ocupação/escala existe em
    `team` ainda, então uma menção a esses termos NUNCA resolveria e reprovaria o build por
    engano. `caca_vocabulario`/Z8 não varrem "capacidade"/"escalonamento" até a parte 2 da
    Fase E (quando E4/E5 forem implementados). Toda menção a "evasão"/"incentivo"/"hipótese"
    que prometa o Ato 7 resolve para um item real de `team` (mesmo espírito do Z-sintático de
    `valida_anexo_sintatico`: promessa sem item = reprovado). E2/E3 não têm R$, então Z8 é
    resolução referencial, não igualdade numérica.

### 3.5. TDD do MVP — correção de provisionamento (achado desta revisão)

Verificado no repo: `rede_oticas_beta_test.xlsx` (a fixture com o Gabarito oculto) **não tem
gerador versionado** — é um binário `.gitignore`d sem script de reconstrução rastreável no
projeto; e o script `create_otica_test_workbook.py` gera `otica_test_bom/ruim.xlsx`, um par
de fixtures não relacionado (usado em testes de robustez/completude, não no golden Beta).
Editar qualquer um dos dois para "plantar um vendedor em evasão" seria ou impossível
(Beta) ou contaminaria testes de outra tese (otica_test_bom/ruim).

**Correção:** E1/E2/E3 seguem o padrão real de TDD por detector já em uso nesta casa (ver
`tests/test_seller_margin_mix_phase_d.py`) — DataFrame sintético construído inline no teste
(`_sales()`/`_line()`), sem tocar nenhuma fixture `.xlsx`. O "gabarito" de E1 é o próprio
teste de regressão: um vendedor com captura caindo + desconto subindo nos meses sintéticos
plantados na função de teste, e um vendedor em rampa (tenure curta) que NÃO deve disparar.
v3/Beta continuam servindo só para a verificação end-to-end de que os campos novos fluem
sem erro pelo pipeline real (Acceptance Criteria §5.5) — nunca para plantar o caso de teste.

---

## 4. Arquivos-Alvo

| Arquivo | Mudança |
|---|---|
| `src/product_b/oracle/forensic_contracts.py` | `below_cost_loss_brl`/`below_cost_total_brl` (Z3); `TeamDiagnostics`, `FlightRiskAlert`, `IncentiveMisalignmentAlert`, `SkillGapDiagnosis`; `commission_basis` (str) + `flight_risk_trend_window_months`/`flight_risk_trend_sigma`/`flight_risk_min_flags`/`skill_gap_avoidance_pp` (4 thresholds novos); `team_diagnostics` em `ExecutiveAuditReport` |
| `src/product_b/oracle/commercial_auditor.py` | perda abaixo-do-custo em `detect_discrepancy_triage`; `detect_seller_flight_risk`, `detect_incentive_misalignment`, `detect_skill_gaps`; fiação no builder do relatório |
| `laudo_executivo/build_laudo.py` | Z3 + guarda `anexo_ref` duplicado; `build_team`; injeção de `dados["team"]`; Z7/Z8 |
| `laudo_executivo/EXRS_Template_Laudo_Executivo_v4.html` | Ato 7 (`<details>`, guardado por `D.team`); `perda_abaixo_custo`/`total_abaixo_custo` no Ato 6 |
| `laudo_executivo/EXRS_Spec_Laudo_Executivo_v4.md` | §16: Z3 executado + Z7/Z8; nova seção §17 "Ato 7 · Física da Equipe" (lei do vocabulário/tetos do bloco) |
| `tests/` | `test_flight_risk_e_team_diagnostics.py` (novo, DataFrame sintético — mesmo padrão de `test_seller_margin_mix_phase_d.py`, não a fixture xlsx); extensão de `test_anexo_and_zero_contradicao.py` (Z3/Z7/Z8/ref duplicado); goldens auditados |
| `laudo_executivo/rodadas/` | v3 e Beta regenerados com Ato 7 (fixtures reais existentes — NÃO editadas, ver §3.5) |

---

## 5. Acceptance Criteria (Gate de Saída — Parte B)

1. **Gabarito sintético (não a fixture xlsx, ver §3.5):** teste de regressão com 1 vendedor
   sintético em evasão (captura↓ + desconto↑ nos meses plantados) → o motor detecta com ≥2
   `risk_flags` nomeadas e `carteira_em_risco_brl` = `total_revenue` dele. Vendedor em ramp
   sintético (tenure curta) **não** dispara (gate de tenure).
2. **E2 sem config = ponto cego honesto:** sem `commission_basis`, `incentive_misalignment`
   vazio + `DiscardedAlarm` explicando; com `"gross_revenue"`, o vendedor destruidor de margem
   já existente vira `IncentiveMisalignmentAlert` referenciando o achado original (não um novo
   número).
3. **E3 é hipótese, nunca fato:** todo `SkillGapDiagnosis` sai rotulado "hipótese" e com
   `is_proxy=True`/`data_gap` preenchido; nenhuma menção a "diagnóstico confirmado".
4. **Nenhum R$ inventado em `ExecutiveSummary`:** `total_operational_loss`/`_capital_frozen`/
   `_ltv_risk`/`action_plan` do relatório congelado **não mudam nesta OS** — E1/E2/E3 vivem
   inteiramente em `team_diagnostics` (bloco novo, fora do ES) e na camada narrativa
   (`plano[]`/Ato 7 via `team_ref`), nunca em `ExecutiveSummary` — verificado por diff de
   golden (os únicos campos novos no JSON congelado são `team_diagnostics` e, na Parte A,
   `below_cost_loss_brl`/`below_cost_total_brl`).
5. **Ato 7 no laudo + Zero Contradição:** v3 e Beta regenerados injetam `team_diagnostics` sem
   erro (seções vazias se nenhum vendedor real disparar E1/E2/E3 — fallback honesto, mesmo
   padrão do anexo; não há garantia de que os dados reais/adversariais existentes acionem os
   novos detectores). Z7/Z8 são testados por sabotagem sintética (§3.5): Z7 reprova `impacto`
   de evasão divergente de `carteira_em_risco_brl`; Z8 reprova menção a "evasão/incentivo" sem
   item real em `team`. Retrocompat: AUDIT_DATA sem `team` gera Atos 1-6 limpo.
6. **Suíte completa verde**; goldens novos (`team_diagnostics`) das duas rodadas com diff
   auditado; regressões por caso (uma asserção por perna Z, um teste por gate).

**Risco declarado (achado de revisão, não bloqueia, mas precisa de decisão consciente):** a
regeneração de `golden_laudo_beta.json`/`audit_report_beta.json` (critério 5-6) depende de
`tests/fixtures/rede_oticas_beta_test.xlsx`, um binário gitignored sem gerador versionado no
repo (§3.5). Num clone limpo ou CI sem esse arquivo local, `test_golden_laudo_beta.py` e a
regeneração desta OS não são reproduzíveis. Esta OS aceita a regeneração do golden Beta como
tarefa que só roda na máquina que já tem o xlsx (mesma situação de hoje, não piora nem
resolve) — criar um gerador versionado para `rede_oticas_beta_test.xlsx` fica registrado como
débito técnico separado, fora do escopo desta OS.

---

## 6. Fora de escopo (declarado)

- **E4 (Escalas/ocupação) e E5 (Escalonamento×Tráfego)** — exigem abas novas de ingestão;
  cada um vira sua própria OS (planta-mãe §5/§6), com extensão de `column_mapper` e fixture
  própria. E5 só sob demanda de cliente com dado horário.
- **E3-v2 (conversão real via aba Orçamentos)** — precisa do denominador de tentativas que
  Vendas não captura; fica registrada como extensão, a v1-proxy não a bloqueia.
- Prescrição de plano de comissão ideal (E2) e otimização automática de escala (E5) — o motor
  diagnostica, não desenha a política (planta-mãe §9).
- Qualquer inferência de intenção de saída além dos 3 sinais transacionais de E1 — observação
  de padrão, não predição de RH.

---

## 7. Ordem de implementação

1. **Parte A primeiro** — Z3 (motor `below_cost_loss_brl` → anexo → validador, TDD, golden
   diff) + guarda de `anexo_ref` duplicado. Fecha a dívida de QA e o validador Zero
   Contradição fica completo ANTES de o Ato 7 passar a depender dele (Z7/Z8).
2. **E1** — zero dado novo, maior alavancagem; `TeamDiagnostics` + `FlightRiskAlert` nascem
   aqui, com a fixture plantada e o gate de tenure testado.
3. **E2** — um campo de config, reusa achados existentes; `DiscardedAlarm` no caminho vazio.
4. **E3-v1** — leitura proxy sobre o mix existente, rótulo "hipótese" obrigatório.
5. **Ato 7 + Z7/Z8** no template/validador; regeneração v3 + Beta; critérios 1-6 verificados
   um a um contra os artefatos reais; Spec v4 §16/§17 marcadas.

> Cada pilar acima é um commit próprio na branch `feat/fase-e-fisica-da-equipe` (nova, a
> partir de `feat/fase-d-camada-evidencia`), com goldens versionados — a Fase E não pula a
> disciplina de TDD + gabarito que rege o resto do motor.

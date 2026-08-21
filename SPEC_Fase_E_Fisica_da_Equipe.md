# ENGENHARIA: EXRS Data Oracle — Fase E: A Física da Equipe

> **Status:** PROPOSTA (redigida 20/07/2026, não executada). Documento de planejamento —
> nenhum código foi alterado. Segue o mesmo paradigma das Fases B/C/D já executadas
> (`SPEC_Fase_B_Formulas_Avancadas.md`, `SPEC_Fase_C_Fila_Auditoria_Manual.md`,
> `SPEC_Fase_D2_Anexo_Vivo_e_Zero_Contradicao.md`): esta Fase E é a planta-mãe; cada pilar
> vira sua própria OS (`PLAN.md` + `CRITERIA.md`, padrão `docs/os/<slug>/`) no momento em que
> for autorizada para execução.
> **Origem:** diagnóstico do usuário (20/07/2026) — o motor atual (EXRS Data Oracle) e o
> Framework Elysian julgam o RESULTADO do funcionário (captura A1, corrosão de margem Ato 3,
> rampa de vendedor, Mix de Margem D-Pilar-1) mas ignoram a FÍSICA da operação por trás do
> resultado: 5 pontos cegos — incentivo, capacidade, habilidade, escalonamento, evasão.
> **Subordinada a:** `docs/os/exrs-v2-goal-loop/SPEC.md` (motor honesto), Fase D
> (`SellerMarginMixProfile`, `SellerMarginCorrosionAlert`, `SalespersonPerformance`/SEV) e
> `laudo_executivo/EXRS_Spec_Laudo_Executivo_v4.md` (vocabulário, tetos, procedência).

---

## 0. Princípio arquitetural (por que isto não é "mais 5 detectores")

Tudo que o motor faz hoje responde **"o que o vendedor fez"**. Os 5 pontos do diagnóstico
perguntam **"o que o SISTEMA em volta do vendedor permite, premia ou impede"**. Isso muda o
tom de cada achado de acusação para causa-raiz — mas as regras de engenharia da casa não
mudam nem um pouco:

1. **Nenhum detector infere o que não está no dado.** Se o cliente não informa a estrutura
   de comissão, o motor NUNCA assume "provavelmente é sobre receita bruta" — reporta a
   lacuna e segue sem o achado (mesmo padrão de `detect_contribution_margin` sem coluna de
   custo).
2. **Todo threshold novo vive em `AuditThresholdsConfig`** — zero número mágico dentro de
   função (regra já documentada no topo do contrato atual).
3. **Pseudo-entidade continua excluída** (`is_pseudo_entity`/`_PSEUDO_ENTITY_IDS`) em
   qualquer detector novo que agrupe por vendedor.
4. **`benchmark_population` é reutilizado**, nunca reimplementado, para qualquer régua de
   referência entre pares (mesma trava que já corrigiu 3 bugs reais em churn/RFM/SEV).
5. **Procedência obrigatória** (Pilar 2 da Fase D): todo achado novo carrega
   `sample_source_rows`, mesmo teto `provenance_sample_cap`.
6. **Nunca inventa R$.** Um achado sem base numérica defensável NÃO entra em
   `total_operational_loss`/`total_capital_frozen`/`total_ltv_risk` — vira uma seção
   narrativa própria (ver §7). Isso é decisão explícita desta Fase, detalhada abaixo.

---

## 1. Mapa de viabilidade — o que já temos vs. o que falta

| # | Pilar | Dado novo necessário | Base já existente no motor | Nível de esforço |
|---|---|---|---|---|
| E1 | Evasão de Talentos (Churn de Vendedor) | **Nenhum** — só reprocessa Vendas como série temporal por vendedor | `detect_salesperson_performance` (SEV), `detect_seller_margin_corrosion`, `detect_revenue_leaks` (padrão de série+sigma) | 🟢 Baixo |
| E2 | Conflito de Comissionamento | **1 campo de configuração** (fato de negócio, não planilha) | `SellerMarginMixProfile`, `SellerMarginCorrosionAlert` (já dizem QUEM corrói margem) | 🟢 Baixo |
| E3 | Matriz de Habilidade vs. Viés | Nenhum para v1 (proxy); **aba opcional "Orçamentos"** para v2 (conversão real) | `SellerCategoryMixEntry`/`mix_deviation_pp` (já mede o desvio de mix) | 🟡 Médio |
| E4 | Física do Tempo e Capacidade | **Aba nova "Escalas"** (horas trabalhadas por vendedor/dia) | `SalespersonPerformance.sample_size` (proxy de atendimento) | 🟠 Médio-alto |
| E5 | Escalonamento × Tráfego | **Aba "Escalas" (E4) + aba "Tráfego" ou timestamp horário em Vendas** | `StorePerformance`, ranking de vendedor por receita | 🔴 Alto |

A ordem de implementação (§8) segue este mapa, não a ordem do diagnóstico original — o que
não pede dado novo entra primeiro e já entrega valor no próximo laudo.

---

## 2. E1 — Risco de Evasão de Talentos (prioridade de implementação #1)

**Problema:** o motor mede R$ 92 mil evaporados em clientes, mas não vê o vendedor que está
saindo e vai levar a carteira. Padrão clássico: captura cai, desconto sobe, ticket cai —
tudo isso já é calculável a partir de Vendas, só falta olhar como SÉRIE por vendedor em vez
de foto única.

**Novo detector:** `detect_seller_flight_risk(df, estoque_df, thresholds)` — reaproveita a
MESMA mecânica de `detect_revenue_leaks` (série mensal + desvio sobre a própria história do
vendedor, nunca contra a rede) para 3 pernas independentes, cada uma opcional conforme o
dado disponível:

1. **Captura em queda:** série mensal de `capture_rate_pct` do vendedor (mesma fórmula de
   `detect_salesperson_performance`); queda sustentada nos últimos
   `flight_risk_trend_window_months` meses vs. a média histórica do PRÓPRIO vendedor.
2. **Desconto em alta:** série mensal de `discount_pct` (mesma reconstrução de
   `detect_seller_margin_corrosion`) subindo — requer `list_price` em Estoque; sem ela, esta
   perna simplesmente não é avaliada (nunca inventa preço de tabela).
3. **Ticket em queda:** série mensal de ticket médio do vendedor caindo.

Vendedor em rampa (`has_sufficient_tenure=False`, mesmo gate do SEV) nunca entra — sem
histórico suficiente, tendência não tem base. `risk_flags: list[str]` lista quais das 3
pernas dispararam, cada uma com o número que a sustenta (nunca um score opaco único) —
mesma filosofia de "o mix, nunca só o rótulo" do `SellerMarginMixProfile`.

**Novo contrato:** `FlightRiskAlert` (salesperson, store, months_evaluated,
capture_trend_pct, discount_trend_pp, ticket_trend_pct, risk_flags, carteira_em_risco_brl,
sample_source_rows). `carteira_em_risco_brl` = `total_revenue` do vendedor no período (já
existe em `SalespersonPerformance` — nenhum número novo inventado) — é o valor legítimo para
entrar no plano de ação como `nature="ltv_risk"` (mesma natureza que já existe para receita
latente/concentração), porque é o que evapora SE o vendedor sair, não uma perda já ocorrida.

**Thresholds novos:** `flight_risk_trend_window_months: int = 3`,
`flight_risk_min_flags: int = 2` (de 3 pernas precisa disparar para virar achado — mesmo
espírito de exigir 2 evidências simultâneas do Mix de Margem).

---

## 3. E2 — Conflito de Comissionamento (prioridade #2)

**Problema:** o laudo manda o vendedor proteger margem; o contracheque manda vender
qualquer coisa. O motor já SABE quem corrói margem (`SellerMarginMixProfile`,
`SellerMarginCorrosionAlert`) — só não sabe se isso é vontade própria ou incentivo mal
desenhado.

**Decisão de dado:** não criar uma planilha nova para isto — é um FATO DE NEGÓCIO declarado
pelo consultor na configuração da rodada, no mesmo espírito de `service_category_label` e
`promo_payment_label` (já são strings de vocabulário de negócio dentro de
`AuditThresholdsConfig`, não dado derivado). Novo campo:

```python
commission_basis: str = "unknown"  # "gross_revenue" | "contribution_margin" | "mixed"
```

Sem esse campo (`"unknown"`, default), o detector retorna vazio e o motivo aparece em
`DiscardedAlarm` ("estrutura de comissão não informada — ponto cego não avaliado"). Nunca
adivinha a partir do dado de vendas (não há como inferir % de comissão a partir de receita e
custo sozinhos).

**Novo detector:** `detect_incentive_misalignment(mix_profiles, corrosion_alerts,
thresholds)` — NÃO recalcula margem; ANOTA achados que já existem. Quando
`commission_basis == "gross_revenue"` e um vendedor tem `is_margin_destructive=True` OU
`is_corrosive=True`, emite `IncentiveMisalignmentAlert` referenciando o achado original +
uma explicação estrutural fixa por tipo de base ("comissiona sobre receita bruta — vender
com desconto ou empurrar produto de entrada não reduz o contracheque dele, mesmo destruindo
a margem da loja"). `mixed`/`contribution_margin` não geram este alerta (o incentivo já está
alinhado ou parcialmente alinhado — não é o ponto cego).

**Novo contrato:** `IncentiveMisalignmentAlert` (salesperson, store, commission_basis,
linked_finding_type: "margin_mix" | "margin_corrosion", linked_finding_summary,
recommended_fix: str fixo por `commission_basis`). Sem R$ próprio — é um achado
estrutural/qualitativo (ver §7), não entra nos totais monetários.

---

## 4. E3 — Matriz de Habilidade vs. Viés (prioridade #3)

**Problema:** `SellerMarginMixProfile.mix` já mede que um vendedor empurra categoria de
margem baixa acima do padrão da loja — mas o rótulo hoje é `is_margin_destructive`, que soa
a "vontade"/preguiça. O diagnóstico do usuário pede reclassificar isso como possível déficit
de treinamento quando o padrão é "foge de categoria de margem/ticket alto", não só "empurra
categoria de margem baixa" (duas leituras diferentes do mesmo `mix_deviation_pp`).

**v1 (sem dado novo, proxy honesto):** nova camada de leitura sobre
`SellerCategoryMixEntry` já existente — para cada categoria onde
`mix_deviation_pp < -thresholds.skill_gap_avoidance_pp` (o vendedor vende
MENOS que o padrão da loja) E `category_margin_pct` daquela categoria está no topo do
ranking de margem da loja, gera `SkillGapDiagnosis` com
`hypothesis="possível déficit de treinamento/segurança técnica em <categoria>"` — rotulado
explicitamente como **hipótese derivada de padrão de mix**, nunca apresentado como fato
medido (vocabulário obrigatório: "hipótese", nunca "diagnóstico confirmado" — mesma disciplina
de `latent_revenue_conversion_pct`, que já é rotulado cenário assumido).

**v2 (condicional a dado novo):** taxa de conversão REAL por categoria (o "80% em visão
simples, 12% em multifocal" do diagnóstico) exige saber TENTATIVAS, não só vendas
concluídas — Vendas não captura orçamento recusado. Requer aba opcional **Orçamentos**
(`orcamento_id`, `data`, `cliente`, `categoria`, `convertido: bool`). Sem essa aba, o motor
NUNCA calcula "taxa de conversão" (seria inventar o denominador) — fica só no proxy de mix
do v1, com essa limitação declarada no próprio achado (`data_gap: "conversao_real_requer_aba_orcamentos"`).

**Novo contrato:** `SkillGapDiagnosis` (salesperson, store, category, mix_deviation_pp,
category_margin_pct, hypothesis, is_proxy: bool = True, data_gap: str | None). Novo threshold:
`skill_gap_avoidance_pp: float` (piso de quanto o vendedor precisa evitar a categoria para
virar hipótese, mesma unidade de `seller_margin_gap_pct`).

---

## 5. E4 — Física do Tempo e Capacidade (prioridade #4)

**Problema:** a fila de reativação (churn) manda "ligar para 47 clientes" sem saber se o
vendedor de balcão tem 5 minutos livres no dia. Isso não é calculável a partir de Vendas
sozinha — Vendas só registra o que VIROU venda, não o tempo gasto em atendimento/vitrine/
tráfego de porta.

**Dado novo obrigatório:** aba opcional **Escalas** — papéis novos em `column_mapper.py`:

```python
_ESCALAS_ROLE_KEYWORDS = {
    "salesperson": [...], "store": [...], "date": [...], "hours_worked": [...],
}
_ESCALAS_REQUIRED_ROLES = ("salesperson", "store", "date", "hours_worked")
```

Sem esta aba, `detect_seller_occupancy` retorna vazio — nunca estima horas trabalhadas a
partir de volume de venda (seria inventar o denominador da ocupação).

**Novo detector:** `detect_seller_occupancy(vendas_df, escalas_df, thresholds)` — ocupação
proxy = `sample_size` (nº de vendas, já existe em `SalespersonPerformance`) ÷ horas
trabalhadas no mesmo período, por (loja, vendedor). Declarado explicitamente como PROXY
(atendimentos que não viraram venda — walk-in que saiu sem comprar — não entram; a
ocupação real é maior que a medida). Vendedor no quartil de maior ocupação da própria loja
(`benchmark_population`, nunca a rede) recebe `capacity_constrained=True`.

**Integração com o plano de ação existente:** `ActionPlanItem` de fila de reativação
(churn) ganha checagem cruzada — se o(s) vendedor(es) responsável(is) pela carteira do
cliente em churn está `capacity_constrained=True`, o item do plano inclui uma nota
("vendedor sem folga operacional — considerar redistribuir ou reforçar horário de balcão"
em vez de simplesmente instruir "ligar"). Isto NÃO cria um novo total monetário — é uma
anotação de viabilidade sobre um achado que já existe.

**Novo contrato:** `SellerOccupancyProfile` (salesperson, store, sample_size, hours_worked,
attendances_per_hour, is_high_occupancy, sample_source_rows). Threshold:
`occupancy_high_percentile: float = 75.0`.

---

## 6. E5 — Escalonamento × Tráfego (prioridade #5, mais arriscado)

**Problema:** o dono pode escalar os 3 piores vendedores no pico de sábado e deixar o
melhor na terça vazia. Medir isso exige DUAS coisas que a maioria dos ERPs de PME não
exporta com granularidade suficiente: (a) a escala (E4, já um dado novo) e (b) tráfego por
horário/dia — hoje `Vendas.date` normalmente é só data, sem hora.

**Dado novo obrigatório (o maior risco de viabilidade de toda a Fase E):**
- Escalas (E4, reaproveitada).
- Ou (i) coluna de horário em Vendas (`hora` — role novo, opcional), ou (ii) aba dedicada
  **Tráfego** (`loja`, `data`, `hora`, `contagem_movimento` — de sensor de porta/PDV, quando
  existir). **Risco declarado:** muitas óticas de PME não têm nenhuma das duas — este pilar
  deve ser oferecido como "mediante disponibilidade de dado horário", nunca prometido no
  laudo padrão.

**Novo detector (condicional):** `detect_scheduling_traffic_mismatch` — cruza o índice de
tráfego por (dia-da-semana, faixa-horária) por loja com a escala de cada vendedor,
ponderado pelo `TMI`/ticket médio dele (mesmo `SalespersonPerformance`/futuro TMI ponderado
por mix, ver Gabarito da fixture de ótica) — sinaliza quando o vendedor de maior ticket
médio está sistematicamente escalado nas faixas de MENOR tráfego (e vice-versa para o de
pior desempenho no pico).

**Novo contrato:** `SchedulingTrafficMismatch` (store, salesperson, traffic_weighted_slot_score,
seller_performance_rank, mismatch_severity, sample_source_rows).

**Decisão explícita:** este pilar só é implementado quando um cliente concreto tiver os dois
dados de origem — não faz parte do MVP da Fase E. Fica especificado aqui para não perder o
raciocínio, mas entra em execução por último e sob demanda.

---

## 7. Onde estes achados vivem no laudo (decisão de arquitetura)

Os 5 pilares NÃO entram nos 3 totais monetários existentes
(`total_operational_loss`/`total_capital_frozen`/`total_ltv_risk`) exceto E1
(`carteira_em_risco_brl`, que é um número já existente reaproveitado, não inventado). E2,
E3, E4 e E5 são diagnósticos estruturais/organizacionais sem R$ direto defensável — forçá-los
em `impact_brl` violaria a regra "nunca inventa número" que rege todo o motor hoje.

Proposta: novo bloco no `ExecutiveAuditReport`, `team_diagnostics: TeamDiagnostics`
(incentive_misalignment, skill_gaps, occupancy_profiles, scheduling_mismatches — cada lista
tipada, todas opcionais/vazias quando o dado de origem falta). No laudo (`laudo_executivo`),
vira um **Ato 7 · Física da Equipe**, no mesmo padrão `<details>` recolhido do Ato 6
(Anexo), com o mesmo validador de Zero Contradição (D3) estendido para checar que toda menção
a "incentivo"/"capacidade"/"escalonamento" no corpo resolve para um item real deste bloco —
mesma disciplina, sem duplicar a "lei" da Spec v4, só estendê-la.

---

## 8. Ordem de implementação recomendada

1. **E1 — Evasão de Talentos.** Zero dado novo, maior alavancagem imediata (o R$ mais alto e
   mais defensável dos cinco, reaproveita 100% de infraestrutura existente).
2. **E2 — Conflito de Comissionamento.** Um campo de config, reaproveita achados já
   existentes — segunda menor barreira de entrada.
3. **E3 — Matriz de Habilidade vs. Viés (v1 proxy).** Reaproveita `SellerMarginMixProfile`;
   v2 (conversão real via Orçamentos) fica registrada como extensão futura, não bloqueia v1.
4. **E4 — Física do Tempo e Capacidade.** Primeira a exigir ingestão de aba nova (Escalas) —
   maior esforço de engenharia (novo `column_mapper` role set + testes de fixture), mas
   dado unidimensional e razoavelmente disponível (planilha de horário é comum).
5. **E5 — Escalonamento × Tráfego.** Maior risco de viabilidade (2 fontes de dado novas,
   uma delas rara em PME) — implementar sob demanda, quando um cliente real tiver o dado.

Cada item acima vira sua própria OS (`docs/os/<slug>/PLAN.md` + `CRITERIA.md`) no padrão
Mestre/Aprendiz já em uso, com fixture de teste plantada (extensão de
`create_otica_test_workbook.py` com as novas abas/anomalias) e golden masters próprios —
esta Fase E não pula a disciplina de TDD + gabarito versionado que já rege o resto do motor.

## 9. Fora de escopo (declarado)

- Cálculo automático de plano de comissão ideal (prescrição de RH) — o motor diagnostica o
  desalinhamento, não desenha a política nova.
- Otimização automática de escala (E5) — o motor aponta o descasamento, a decisão de
  realocar continua humana.
- Qualquer inferência de intenção de saída (E1) além dos 3 sinais declarados — não é
  predição de RH, é observação de padrão em dado transacional.
- Integração com sistemas de ponto/RH externos — toda ingestão continua via planilha
  (.xlsx/.csv), mesmo modelo do resto do motor.

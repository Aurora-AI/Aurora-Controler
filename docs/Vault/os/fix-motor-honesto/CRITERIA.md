# CRITERIA.md — OS `fix-motor-honesto` (Doc B)

**Paradigma:** Spec-Driven Motor (Mestre-Aprendiz). Este documento é a **constituição de
auditoria binária**. O `qa-review` carrega este arquivo e emite **PASS** (100% dos critérios
atendidos) ou **FAIL** (qual critério falhou + evidência), **sem sugerir correção**. Uma vez
assinado, NÃO é alterado durante a execução.

**Escopo da OS:** tornar o detector de vazamento de receita HONESTO — matar os dois falsos
positivos (sazonalidade + ruído esparso) que a fixture de ótica expôs, sem perder o sinal
real. É o incremento de **credibilidade** (Fix 1 + Fix 2 da spec do motor honesto). Fix 3
(série B) é OS separada.

**Insumo:** `docs/superpowers/specs/2026-07-06-exrs-audit-motor-honesto-design.md` +
`docs/os/fix-motor-honesto/PLAN.md`. Fixture: `tests/fixtures/otica_test_bom.xlsx`
(regenerável por `create_otica_test_workbook.py`, seed fixa).

---

## Critérios de aceite (binários — cada um PASS ou FAIL)

### C1 · Materialidade mata o ruído esparso
- **Regra implementada:** um produto só entra na detecção por-produto se sua receita no
  período for **≥ `materiality_revenue_pct`** (default **1.0%**) da receita total do período.
  A regra antiga da spec ("≥12 vendas OU ≥1% receita") é **substituída** por esta — o "OU
  vendas" deixava passar SKU esparso de 13 vendas.
- **PASS se:** rodando `run_audit` em `otica_test_bom.xlsx`, NENHUM destes SKUs esparsos
  aparece em `revenue_leaks`: `ARM-059`, `LEN-071`, `LEN-074`, `LEN-076`, `LEN-083`,
  `LEN-118` (todos < 1% da receita).
- **FAIL se:** qualquer um dos 6 acima ainda aparece.

### C2 · Sinal real preservado
- **PASS se:** `AG-12` (2,66% da receita, não sazonal) CONTINUA em `revenue_leaks` no período
  `2024-05` com `severity == "high"`.
- **FAIL se:** AG-12 some da lista, ou muda de severidade.

### C3 · Sazonalidade (YoY) mata o falso positivo sazonal
- **Regra implementada:** o desvio é medido sobre o **resíduo YoY**, não sobre a série crua.
  Como esta é uma auditoria RETROSPECTIVA (histórico fechado), o esperado de um mês M =
  **média do mesmo mês-do-ano em TODOS os OUTROS anos** (leave-one-out — inclui anos
  posteriores, legítimo num diagnóstico histórico, não num alerta ao vivo). Se houver
  **menos de 2 observações** daquele mês-do-ano em outros anos → sem base → no máximo
  `low_confidence`, nunca hard-flag. Racional registrado: a regra "só anos anteriores"
  suprimiria o AG-12 (plantado no 1º maio do dataset); leave-one-out sobre todos os anos
  resolve mantendo a supressão sazonal.
- **PASS se:** `SOLAR-SEASONAL` (pico regular dez-fev) NÃO aparece em `revenue_leaks` em
  NENHUM período de março (`2024-03`, `2025-03`, `2026-03`).
- **FAIL se:** SOLAR-SEASONAL aparece flagrado em qualquer março.

### C4 · Nenhuma regressão no motor determinístico da OS 1
- **PASS se:** `tests/test_commercial_auditor.py` passa 100% (os 4 detectores contra
  `sales_history_test.xlsx`, incluindo o vazamento e o churn plantados da OS 1).
- **FAIL se:** qualquer teste da OS 1 quebra.

### C5 · Thresholds sem número mágico
- **PASS se:** `materiality_revenue_pct` é campo de `AuditThresholdsConfig` (com default 1.0),
  e o detector o consome de lá — nenhum literal de materialidade dentro de `detect_revenue_leaks`.
- **FAIL se:** o valor 1.0 (ou qualquer limiar) aparece hardcoded no detector.

### C6 · Suíte completa verde
- **Baseline (Docker no ar, confirmado nesta OS):** `pytest tests/ -q` = **0 falhas**. As 2
  antes-instáveis de `test_phase_a4` (sandbox Docker) agora passam.
- **PASS se:** `pytest tests/ -q` termina com **0 falhas**. Única tolerância: as 2 de
  `test_phase_a4` (`test_execute_in_sandbox`, `test_signature_handshake`) SÓ se o Docker
  estiver comprovadamente fora no momento do run (`SANDBOX_UNAVAILABLE`) — caso contrário
  contam como falha.
- **FAIL se:** qualquer falha com o Docker no ar.

### C7 · Regressão explícita dos dois falsos positivos
- **PASS se:** existe teste novo que asserta C1 (os 6 esparsos = 0 flags) e C3 (SOLAR-SEASONAL
  = 0 flags nos marços) contra a fixture, além de C2 (AG-12 mantido) — para travar o
  comportamento contra regressão futura.
- **FAIL se:** o comportamento é obtido mas não há teste que o trave.

---

## Veredito
`qa-review` retorna **PASS** apenas se C1..C7 todos PASS. Qualquer FAIL → devolve ao Aprendiz
com o critério e a evidência (sem projetar o fix). Sem "quase": aprovação é binária.

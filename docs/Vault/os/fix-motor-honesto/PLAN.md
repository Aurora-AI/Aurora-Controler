# PLAN.md — OS `fix-motor-honesto` (Doc A)

**Paradigma:** Spec-Driven Motor. Este é a planta da obra. Assinado pelo humano, NÃO muda
durante a execução. O Aprendiz (subagente Sonnet) executa cada tarefa atômica; o Mestre
(Opus) audita contra `CRITERIA.md` via `qa-review` binário.

**Goal:** tornar `detect_revenue_leaks` honesto — piso de materialidade (Fix 2) + resíduo
YoY de sazonalidade (Fix 1) — matando os 2 falsos positivos sem perder o AG-12.

**Arquivos:**
- Modificar: `src/oracle/forensic_contracts.py` (novo campo em `AuditThresholdsConfig` +
  novo campo em `RevenueLeakAnomaly`).
- Modificar: `src/oracle/commercial_auditor.py` (`detect_revenue_leaks`).
- Teste: `tests/test_revenue_leak_honesty.py` (novo).

**Global constraints:** Python ≥3.14; sem dependência nova; thresholds só em
`AuditThresholdsConfig` (zero número mágico); fixture regenerável por
`create_otica_test_workbook.py` (rodar antes dos testes — o `.xlsx` é gitignored).

---

## Task 1 — Piso de materialidade (Fix 2 → satisfaz C1, C2, C5 parcial)

**Objetivo:** produto só é escaneado pelo detector por-produto se sua receita ≥
`materiality_revenue_pct`% da receita total do período.

**Passos:**
1. Em `forensic_contracts.py`, adicionar a `AuditThresholdsConfig`:
   `materiality_revenue_pct: float = 1.0`.
2. Em `detect_revenue_leaks` (`commercial_auditor.py`): antes do loop `for product, group in
   df.groupby("product")`, calcular `total_revenue = df["value"].sum()` e o piso
   `floor = total_revenue * thresholds.materiality_revenue_pct / 100.0`. Dentro do loop, se
   `group["value"].sum() < floor`, `continue` (pula o produto — não entra na detecção
   por-produto; a série total não é afetada).
3. Escrever teste em `tests/test_revenue_leak_honesty.py` que roda `run_audit` na fixture
   `otica_test_bom.xlsx` e asserta: nenhum de `{ARM-059, LEN-071, LEN-074, LEN-076, LEN-083,
   LEN-118}` aparece em `revenue_leaks`; e `AG-12` AINDA aparece.
4. Rodar `pytest tests/test_revenue_leak_honesty.py -v` → deve passar as asserções de
   materialidade. (SOLAR-SEASONAL ainda flagará neste ponto — Task 2 resolve.)
5. Rodar `pytest tests/test_commercial_auditor.py -q` → sem regressão (C4).
6. Commit.

**Nota de calibração (dado da fixture pós-fix de moeda):** AG-12 = 2,66% da receita (fica
acima do piso de 1%); os 6 SKUs de ruído = 0,28–0,58% (ficam abaixo). A separação é limpa
com 1,0%.

---

## Task 2 — Resíduo YoY de sazonalidade (Fix 1 → satisfaz C3, C2, C7)

**Objetivo:** medir o desvio sobre o resíduo YoY (leave-one-out sobre todos os anos), não
sobre a série crua. Ver C3 do CRITERIA para a regra exata.

**Passos:**
1. Em `forensic_contracts.py`, adicionar a `RevenueLeakAnomaly`:
   `low_confidence: bool = False`.
2. Em `detect_revenue_leaks`, na varredura por-produto (após o piso de materialidade),
   substituir a lógica de "queda mês-a-mês sobre a série crua" por:
   - Para a série mensal do produto (`period → valor`), computar, para cada período P
     (mês-do-ano `mo = P.month`), o esperado YoY = média dos valores dos OUTROS períodos com
     o mesmo `mo` (leave-one-out; exclui o próprio P). Contar quantos outros-ano existem.
   - `residual = valor_P − esperado_P`. Computar `std_res` = desvio-padrão dos resíduos de
     todos os períodos do produto que TÊM base (≥1 outro-ano).
   - Se `std_res` for 0/NaN → pular o produto (sem sinal).
   - Para cada P com base: `sigma = -residual / std_res`. Se `sigma >= revenue_drop_sigma`:
     - Se o nº de outros-ano do mês de P for **< 2** → registrar com `low_confidence=True` e
       `severity` no máximo `"medium"` (nunca hard-flag sem base).
     - Senão → `severity = "high" if sigma >= revenue_drop_sigma*1.5 else "medium"`,
       `low_confidence=False`.
     - `expected_value = esperado_P`, `actual_value = valor_P`, `drop_sigma = sigma`.
   - A varredura da série TOTAL (`scope="total"`) pode manter a lógica atual mês-a-mês (não
     é alvo dos falsos positivos por-produto) — não alterar, para não introduzir regressão.
3. No teste `test_revenue_leak_honesty.py`, adicionar asserções: `SOLAR-SEASONAL` NÃO aparece
   em `revenue_leaks` em nenhum período de março (2024-03, 2025-03, 2026-03); `AG-12` aparece
   em `2024-05` com `severity=="high"` e `low_confidence==False`.
4. Rodar `pytest tests/test_revenue_leak_honesty.py -v` → todas as asserções (C1+C2+C3).
5. Rodar `pytest tests/test_commercial_auditor.py -q` → sem regressão (C4). Atenção: o
   vazamento plantado da OS 1 (`sales_history_test.xlsx`, "Adaptador USB"/queda 2024-08) é
   detectado no `scope="total"` OU num produto com base YoY — confirmar que continua
   detectado; se o resíduo YoY suprimir por falta de base (a OS1 tem só 24 meses = 2 anos),
   verificar que o total ainda pega, senão é FAIL de C4 e volta ao Mestre.
6. Commit.

---

## Task 3 — Suíte completa + fechamento (satisfaz C6, C7)

**Passos:**
1. Regenerar fixtures: `python tests/fixtures/create_otica_test_workbook.py` +
   `create_audit_test_workbook.py` + `create_test_workbook.py`.
2. Rodar `pytest tests/ -q`. Confirmar: sem falhas novas além das 2 pré-existentes de Docker
   (`test_phase_a4`).
3. Confirmar que `test_revenue_leak_honesty.py` cobre C1 (6 esparsos=0), C2 (AG-12 mantido),
   C3 (SOLAR-SEASONAL=0 nos marços) — o trava-regressão do C7.
4. Commit final.

---

## Ordem e dependências
Task 1 → Task 2 → Task 3 (sequencial; Task 2 depende do piso da Task 1 estar no lugar). Cada
task termina com deliverable testável e commit próprio.

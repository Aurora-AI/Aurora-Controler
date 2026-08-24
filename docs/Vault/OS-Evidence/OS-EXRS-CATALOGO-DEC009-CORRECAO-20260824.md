# Evidence — Correção Pós-Certificação: OS-EXRS-CATALOGO-DEC009-20260818-001

**Data:** 2026-08-24
**OS Original:** `OS-EXRS-CATALOGO-DEC009-20260818-001` (`OS-EXRS-CATALOGO-DEC009-evidence.md`)
**Natureza:** Complemento, não correção do registro original — o registro histórico do
que foi declarado em 2026-08-18 permanece intocado (Doutrina, item 5: Vault é
append-only). Este documento registra o que foi encontrado depois da certificação e
o que foi feito a respeito.
**Origem do achado:** `/engineering:code-review` sobre o diff então não commitado dos
3 artefatos novos, seguido de correção via decisão explícita do Decisor (Rodrigo) para
cada item de comportamento em aberto.

---

## 1. O que a certificação original declarou que nem sempre era verdade

`OS-EXRS-CATALOGO-DEC009-evidence.md` (seção 1, itens 3 e 6) certificou sob o selo
`AURORA_TRUSTWARE`:
- `ART-COC-001`: "Blindagens: REG-SEV-004 (zero nomes de vendedores), REG-NUM-001 (4
  KPIs em SEM_BASE)."
- `ART-PER-001`: "Blindagens: REG-SEV-004 (zero nomes), REG-NUM-002 (amostra reduzida)."

Nenhuma das duas afirmações era falsa nos testes que existiam — os 62 testes de
sabotagem citados passavam de fato (100%). Eram falsas nos cenários que os testes
existentes nunca tentaram. "O gate roda e passa" não é a mesma pergunta que "o gate
pega o cenário que ele existe para pegar" (Doutrina, Regra 13).

## 2. Achados, prova de reprodução, e correção — mapeamento 1:1

### 2.1 `ART-PER-001` — vazamento de identificação individual via campo `store`
- **Estado:** `feito`
- **Achado:** `store` (originado de `SellerMarginCorrosionAlert.store`/`...MixProfile.store`,
  dado externo não controlado) passava só por `_sanitize_single_line` (normaliza espaço/quebra
  de linha), nunca pelo filtro de token `_sanitize_text_no_seller` — que existia no
  arquivo, mas sem nenhum ponto de chamada.
- **Decisão:** nenhuma — correção mecânica (religar a função já escrita ao ponto de uso).
- **Correção:** [band_performance.py:266](../../../src/product_b/oracle/band_performance.py) —
  troca de `_sanitize_single_line` por `_sanitize_text_no_seller`.
- **Prova:** `test_reprova_seller_token_in_store_name` (novo) + reprodução independente
  fora da suíte do time: `'Joao'/'Silva' present = False`, `'equipe_restringida' present = True`.

### 2.2 `ART-COC-001` — GMROI consolidado fabricado a partir de metades de linhas diferentes
- **Estado:** `feito`
- **Achado:** `tot_margin`/`tot_inv` filtravam `math.isfinite` em duas compreensões
  independentes sobre `report.gmroi` — uma linha com `gross_margin` NaN e outra com
  `avg_inventory_value` NaN combinavam margem de uma categoria com estoque de outra,
  selando o resultado como `CONFIRMADO`.
- **Decisão:** nenhuma — correção mecânica (o próprio código já demonstrava a intenção
  de nunca combinar dado não-finito; o filtro só precisava ser pareado por linha).
- **Correção:** [owner_cockpit.py:213-215](../../../src/product_b/oracle/owner_cockpit.py) —
  filtro conjunto (`valid_rows`) antes de somar os dois campos.
- **Prova:** `test_reprova_mixed_row_nan_for_gmroi` (novo) + reprodução independente:
  `status_selo = SEM_BASE`, `value = None` (era `CONFIRMADO` / `2.0` fabricado).

### 2.3 `ART-FIL-002` — `practiced_price` não finito exibido como `"R$ nan"`
- **Estado:** `feito`
- **Achado:** único campo obrigatório do item sem guarda `math.isfinite`, ao contrário
  de todos os campos irmãos na mesma função.
- **Decisão do Decisor (Rodrigo, 2026-08-24):** manter o item na fila normal de
  revisão humana, substituindo o valor fabricado por `[SEM DADO]` — mesma convenção
  `SEM_BASE` já usada no resto do sistema. Rejeitadas as alternativas de separar o
  item num grupo à parte ou de não corrigir agora.
- **Correção:** [manual_audit_queue.py](../../../src/product_b/oracle/manual_audit_queue.py) —
  `practiced_price` vira `float | None`; guarda na conversão; `[SEM DADO]` na renderização.
- **Prova:** `test_reprova_practiced_price_nao_finito_nunca_fabrica_numero` (novo, 3 casos:
  nan/inf/-inf) + reprodução independente: `fabricated 'R$ nan/inf' present = False`.

### 2.4 Achado adicional (twin-check, não fazia parte da OS original) — engine `commercial_auditor.py`
- **Estado:** `feito`
- **Como foi encontrado:** ao verificar se `practiced_price` tinha outros consumidores
  antes de mudar o schema do item 2.3, a mesma assimetria de guarda apareceu um andar
  abaixo, na função que gera o dado bruto (`detect_discrepancy_triage`, linha ~2040).
- **Prova de que era alcançável de verdade (não hipotética):** rodando a função real
  (não um objeto Pydantic montado à mão) com dado de entrada corrompido:
  - `value = inf` direto → `practiced_price = inf` no item gerado pela engine real.
  - `value = NaN` → linha descartada antes mesmo de existir `unit_price` (já protegido
    pelo filtro pré-existente de `value > 0`; hipótese original de que NaN vazava
    igual a Inf estava errada, e a prova por execução foi o que corrigiu essa hipótese).
  - `value` grande porém individualmente finito ÷ quantidade implausivelmente pequena
    → estouro de ponto flutuante para `inf` (caminho mais realista que um `Infinity`
    literal na planilha de origem).
- **Decisão do Decisor (Rodrigo, 2026-08-24):** descartar a venda da análise antes de
  ela virar candidata a triagem — mesmo critério já usado hoje para `value <= 0`.
  Rejeitadas as alternativas de propagar `SEM_BASE` até a engine ou de não corrigir agora.
- **Correção:** [commercial_auditor.py](../../../src/product_b/oracle/commercial_auditor.py) —
  filtro de `value` finito antes de calcular `unit_price`; segundo filtro no próprio
  `unit_price` calculado (necessário porque a primeira tentativa de correção só
  guardava `value`, não pegando o caso de estouro por divisão — a correção completa
  levou duas iterações, cada uma provada por execução antes de seguir para a próxima).
- **Prova:** `test_reprova_value_nao_finito_nunca_vira_practiced_price_fabricado` (novo,
  2 casos) + `test_reprova_overflow_de_preco_unitario_por_quantidade_minuscula` (novo)
  + reprodução independente confirmando `triggered_count = 0` nos 3 cenários adversariais.

## 3. Evidência de execução (Gate)

```
$ pytest tests/test_discrepancy_triage_phase_c.py tests/test_golden_laudo_v3.py \
    tests/test_golden_laudo_beta.py tests/test_anexo_and_zero_contradicao.py \
    tests/test_art_fil_002_manual_audit_queue.py tests/test_art_per_001_band_performance.py \
    tests/test_art_coc_001_owner_cockpit.py tests/test_art_fil_001_rescue_queue.py -q

138 passed in 71.70s (0:01:11)
```

Nenhum arquivo golden/zero-contradição mudou de resultado — os dados de fixture
reais (`Consultoria.xlsx` e os JSONs golden) não continham nenhuma linha degenerada,
então a correção na engine não deslocou nenhum número já certificado.

## 4. O que este documento não cobre

Não reabre nem invalida o restante da certificação original (`ART-LAU-001`,
`ART-ANX-001`, `ART-FIL-001` fora do escopo acima, `ART-FIL-002` fora do campo
`practiced_price`) — esses seguem cobertos pelo evidence doc de 2026-08-18. Não
constitui nova rodada de `alvaro:check`/`repo:check` (não executados nesta sessão).

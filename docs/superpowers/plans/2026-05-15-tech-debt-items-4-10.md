# Tech Debt Items 4–10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar 7 itens de dívida técnica (4–10) classificados como Importante/Menor, sem introduzir regressões.

**Architecture:** Cada item é independente. A ordem abaixo minimiza risco: itens de limpeza simples primeiro (#7, #8), depois correções funcionais (#10, #4), depois refatoração estrutural (#6), e por último documentação/design (#5, #9).

**Tech Stack:** Python 3.14, pytest, pydantic (pipeline_contracts), openpyxl

---

## Mapa de Arquivos

| Arquivo | O que muda |
|---|---|
| `src/phase_a4/formula_evaluator.py` | Remove `import math as _m` duplicados (#7); corrige `_sdiv` para strings numéricas (#10) |
| `src/phase_a4/html_reporter.py` | Move `_pct` para uso real ou remove função morta (#8) |
| `src/phase_a4/repair_orchestrator.py` | Adiciona docstring + aviso de stub explícito; remove NOTE ambíguo (#5) |
| `src/phase_a1_5/normalizer.py` | Substitui `except Exception: pass` por logging estruturado (#4) |
| `tests/test_fixtures.py` | Adiciona `reason=` nos `pytest.skip` dinâmicos (#9) |
| `tests/test_formula_evaluator.py` | Testes para `_sdiv` com string numérica (#10) |
| `tests/test_normalizer.py` | Testes que comprovam que erros de parse são logados, não engolidos (#4) |

---

## Task 1 — Remover `import math` duplicado em `_xl_gcd` e `_xl_lcm` (#7)

**Files:**
- Modify: `src/phase_a4/formula_evaluator.py:611-620`

- [ ] **Step 1: Verificar que os testes atuais passam (baseline)**

```bash
python -m pytest tests/test_formula_evaluator.py -q
```
Expected: todos passando.

- [ ] **Step 2: Remover os imports duplicados**

Em `formula_evaluator.py`, linhas 612 e 616, substituir:

```python
def _xl_gcd(*args):
    import math as _m
    vals = [int(v) for v in _nums(args)]
    return _m.gcd(*vals) if vals else 0

def _xl_lcm(*args):
    import math as _m
    vals = [int(v) for v in _nums(args)]
    r = vals[0] if vals else 0
    for v in vals[1:]: r = r*v//_m.gcd(r,v)
    return r
```

Por (usa o `math` já importado no topo do arquivo na linha 7):

```python
def _xl_gcd(*args):
    vals = [int(v) for v in _nums(args)]
    return math.gcd(*vals) if vals else 0

def _xl_lcm(*args):
    vals = [int(v) for v in _nums(args)]
    r = vals[0] if vals else 0
    for v in vals[1:]: r = r * v // math.gcd(r, v)
    return r
```

- [ ] **Step 3: Verificar que os testes continuam passando**

```bash
python -m pytest tests/test_formula_evaluator.py -q
```
Expected: todos passando, zero regressões.

- [ ] **Step 4: Commit**

```bash
git add src/phase_a4/formula_evaluator.py
git commit -m "refactor: remove duplicate math imports from _xl_gcd and _xl_lcm"
```

---

## Task 2 — Remover `_pct` morta de `html_reporter.py` (#8)

**Contexto:** `_pct` está definida em `html_reporter.py` mas nunca é chamada pelo próprio módulo (apenas exportada para testes). O cálculo de percentagem no HTML é feito inline. Ela não é usada internamente — é pública apenas para os testes. O item correto é **manter a função mas tornar o uso interno consistente**, garantindo que todos os cálculos de percentagem do módulo passem por ela.

**Files:**
- Modify: `src/phase_a4/html_reporter.py`

- [ ] **Step 1: Localizar onde percentagens são calculadas inline no HTML**

```bash
grep -n "100\.\|pct\|paridade\|%'" src/phase_a4/html_reporter.py | head -20
```

- [ ] **Step 2: Substituir cálculos inline por chamadas a `_pct`**

Toda ocorrência de `f"{passed/total*100:.1f}%"` ou similar deve ser substituída por `_pct(passed, total)`. Por exemplo:

```python
# Antes (cálculo inline):
parity_str = f"{passed / total * 100:.1f}%" if total else "—"

# Depois (usa a função centralizada):
parity_str = _pct(passed, total)
```

- [ ] **Step 3: Verificar que os testes de html_reporter passam**

```bash
python -m pytest tests/test_html_reporter.py -q
```
Expected: todos passando, incluindo `test_pct_helper`.

- [ ] **Step 4: Commit**

```bash
git add src/phase_a4/html_reporter.py
git commit -m "refactor: use _pct helper consistently in html_reporter instead of inline calculations"
```

---

## Task 3 — Corrigir `_sdiv` para strings numéricas `"0"` (#10)

**Contexto:** `_sdiv(10, "0")` retorna `#VALUE!` porque `isinstance("0", (int, float))` é False. O Excel converte `"0"` para 0 antes de dividir, retornando `#DIV/0!`.

**Files:**
- Modify: `src/phase_a4/formula_evaluator.py:64-77`
- Test: `tests/test_formula_evaluator.py`

- [ ] **Step 1: Escrever o teste que falha**

No `test_formula_evaluator.py`, localizar a classe/seção de testes de `_sdiv` e adicionar:

```python
def test_sdiv_string_zero_returns_div0():
    """_sdiv com denominador string '0' deve retornar #DIV/0!, não #VALUE!"""
    from formula_evaluator import _sdiv, _DIV0
    result = _sdiv(10, "0")
    assert result == _DIV0, f"Esperado #DIV/0!, obtido {result!r}"

def test_sdiv_string_nonzero_divides():
    """_sdiv com denominador string '5' deve dividir normalmente."""
    from formula_evaluator import _sdiv
    result = _sdiv(10, "5")
    assert result == 2.0, f"Esperado 2.0, obtido {result!r}"
```

- [ ] **Step 2: Rodar e confirmar que falha**

```bash
python -m pytest tests/test_formula_evaluator.py::test_sdiv_string_zero_returns_div0 -v
```
Expected: FAILED — `_sdiv` retorna `ExcelError('#VALUE!')` não `_DIV0`.

- [ ] **Step 3: Corrigir `_sdiv`**

```python
def _sdiv(a, b):
    """Divisão segura: retorna ExcelError em vez de lançar ZeroDivisionError.
    Converte strings numéricas antes de verificar divisão por zero (comportamento Excel).
    """
    # Normalizar strings numéricas (Excel coerce "0" → 0)
    if isinstance(b, str):
        try:
            b = float(b)
        except (ValueError, TypeError):
            return _VAL
    if isinstance(a, str):
        try:
            a = float(a)
        except (ValueError, TypeError):
            return _VAL
    if isinstance(b, (int, float)) and b == 0:
        return _DIV0
    if isinstance(b, ExcelError):
        return b
    if isinstance(a, ExcelError):
        return a
    try:
        return a / b
    except ZeroDivisionError:
        return _DIV0
    except TypeError:
        return _VAL
```

- [ ] **Step 4: Rodar e confirmar que passa**

```bash
python -m pytest tests/test_formula_evaluator.py::test_sdiv_string_zero_returns_div0 tests/test_formula_evaluator.py::test_sdiv_string_nonzero_divides -v
```
Expected: ambos PASSED.

- [ ] **Step 5: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add src/phase_a4/formula_evaluator.py tests/test_formula_evaluator.py
git commit -m "fix: _sdiv coerces numeric strings before zero-check, matching Excel behavior"
```

---

## Task 4 — Substituir `except Exception: pass` por logging (#4)

**Contexto:** `normalizer.py` tem 3 pontos onde exceções são engolidas silenciosamente:
- Linha 120: tokenização de fórmula — cai em token degenerado sem log
- Linha 258-259: resolução de referência de célula — `pass` silencioso
- Linha 285-286: parse de coordenada — `pass` silencioso

**Files:**
- Modify: `src/phase_a1_5/normalizer.py`
- Test: `tests/test_normalizer.py` (adicionar casos)

- [ ] **Step 1: Adicionar import de logging no topo do normalizer.py**

Localizar os imports no topo e adicionar após os existentes:

```python
import logging
_log = logging.getLogger(__name__)
```

- [ ] **Step 2: Corrigir os 3 pontos silenciosos**

**Ponto 1 — tokenização (linha ~120):**
```python
    except Exception as exc:
        _log.debug(
            "tokenize_formula: falha ao tokenizar %r (%s) — usando token degenerado",
            formula[:80], exc
        )
        return [FormulaToken(
            type=FormulaTokenType.FUNCTION,
            value=formula[1:] if formula.startswith('=') else formula,
            position=0
        )]
```

**Ponto 2 — resolução de referência (linha ~258):**
```python
                except (ValueError, IndexError) as exc:
                    _log.debug(
                        "extract_dependencies: não resolveu referência %r em %r (%s)",
                        token_val, current_sheet, exc
                    )
```

**Ponto 3 — parse de coordenada (linha ~285):**
```python
            except Exception as exc:
                _log.debug(
                    "normalize_workbook: coordenada inválida %r (%s)",
                    c.coordinate, exc
                )
```

- [ ] **Step 3: Escrever teste que verifica que o log é emitido**

Em `tests/test_normalizer.py` (ou criar se não existir), adicionar:

```python
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
sys.path.insert(0, str(REPO_ROOT / "libs" / "trustware"))

from normalizer import tokenize_formula

def test_tokenize_malformed_formula_logs_and_does_not_raise(caplog):
    """Fórmula malformada não deve lançar exceção; deve logar em DEBUG."""
    with caplog.at_level(logging.DEBUG, logger="normalizer"):
        tokens = tokenize_formula("=((((broken")
    # Não levantou exceção
    assert len(tokens) >= 1
    # Logou algo útil
    assert any("tokenize_formula" in r.message or "falha" in r.message
               for r in caplog.records), f"Nenhum log emitido: {caplog.records}"

def test_tokenize_empty_formula_returns_token():
    """Fórmula vazia não deve lançar exceção."""
    tokens = tokenize_formula("")
    assert isinstance(tokens, list)
```

- [ ] **Step 4: Rodar e confirmar que os testes passam**

```bash
python -m pytest tests/test_normalizer.py -v
```
Expected: PASSED.

- [ ] **Step 5: Suite completa — sem regressão**

```bash
python -m pytest tests/ -q
```
Expected: todos passando.

- [ ] **Step 6: Commit**

```bash
git add src/phase_a1_5/normalizer.py tests/test_normalizer.py
git commit -m "fix: replace silent except/pass in normalizer with debug logging"
```

---

## Task 5 — Documentar stub do `repair_orchestrator.py` (#5)

**Contexto:** `repair_orchestrator.py` tem uma NOTE ambígua ("I'll need to use litellm or similar here too") e não declara claramente que o loop de reparo é um stub MVP. Não tem implementação LLM. O objetivo não é implementar o LLM agora — é tornar o estado atual *explícito* para qualquer engenheiro que abrir o arquivo.

**Files:**
- Modify: `src/phase_a4/repair_orchestrator.py`

- [ ] **Step 1: Substituir a NOTE ambígua por um stub declarado**

No início do arquivo, substituir o comentário inline por um docstring de módulo claro:

```python
"""
EXRS Phase A4 — Repair Orchestrator  [STUB MVP]

Estado atual: apenas agrega estatísticas de divergência (identify_repair_candidates).
O loop de reparo automático via LLM NÃO está implementado nesta fase.

Para implementar o reparo automático no futuro:
  1. Integrar litellm (ou anthropic SDK) como feito na Phase A3 (src/phase_a3/translator.py)
  2. Para cada ValidationResult com status="FAILED" e pattern_class != EXTERNAL_REF:
     - Chamar generate_repair_prompt(mismatch, function)
     - Enviar ao LLM e extrair o bloco de código Python corrigido
     - Re-executar via execute_in_sandbox e validar novamente
  3. Registrar repair_attempts no MismatchReport
"""
```

Remover a linha:
```python
# Note: I'll need to use litellm or similar here too if I want automated repair.
```

Remover o comentário no final:
```python
# No MVP, vamos apenas listar os reparos necessários.
# A execução real do litellm seria similar à Phase A3.
```

- [ ] **Step 2: Confirmar que nenhum teste quebra**

```bash
python -m pytest tests/ -q
```
Expected: todos passando (repair_orchestrator não tem testes diretos, mas importação não pode quebrar).

- [ ] **Step 3: Commit**

```bash
git add src/phase_a4/repair_orchestrator.py
git commit -m "docs: mark repair_orchestrator as MVP stub with clear implementation guide"
```

---

## Task 6 — Auditoria de classes duplicadas entre `normalizer.py` e `pipeline_contracts.py` (#6)

**Contexto:** O audit mencionou duplicação. Após inspeção, `normalizer.py` **importa** as classes de `pipeline_contracts.py` (linha 16-18) — não as redefine. O risco real é que a importação pode mudar silenciosamente se alguém adicionar uma definição local. A dívida real é a ausência de um teste que prove que as classes usadas em normalizer.py *são* as de pipeline_contracts.py.

**Files:**
- Test: `tests/test_normalizer.py`

- [ ] **Step 1: Adicionar teste de identidade de classes**

```python
def test_normalizer_uses_pipeline_contracts_classes():
    """
    Garante que normalizer.py usa as classes de pipeline_contracts,
    não redefinições locais. Falha se alguém introduzir duplicação.
    """
    import sys
    from pathlib import Path
    REPO = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(REPO / "src" / "phase_a1_5"))
    sys.path.insert(0, str(REPO / "libs" / "trustware"))

    import normalizer as norm
    import pipeline_contracts as pc

    assert norm.FormulaToken is pc.FormulaToken, \
        "FormulaToken em normalizer não é o mesmo de pipeline_contracts"
    assert norm.NormalizedCell is pc.NormalizedCell, \
        "NormalizedCell em normalizer não é o mesmo de pipeline_contracts"
    assert norm.NormalizedSheet is pc.NormalizedSheet, \
        "NormalizedSheet em normalizer não é o mesmo de pipeline_contracts"
    assert norm.NormalizedWorkbookIR is pc.NormalizedWorkbookIR, \
        "NormalizedWorkbookIR em normalizer não é o mesmo de pipeline_contracts"
    assert norm.FormulaTokenType is pc.FormulaTokenType, \
        "FormulaTokenType em normalizer não é o mesmo de pipeline_contracts"
```

- [ ] **Step 2: Rodar e confirmar que passa**

```bash
python -m pytest tests/test_normalizer.py::test_normalizer_uses_pipeline_contracts_classes -v
```
Expected: PASSED — as classes são as mesmas (importadas, não redefinidas).

- [ ] **Step 3: Commit**

```bash
git add tests/test_normalizer.py
git commit -m "test: guard against duplicate class definitions between normalizer and pipeline_contracts"
```

---

## Task 7 — `pytest.skip` com `reason=` rastreável (#9)

**Contexto:** Os dois skips dinâmicos em `test_fixtures.py` não têm mensagem estruturada que explique *por que* o skip é esperado vs. um problema. Em CI, skips sem razão clara passam despercebidos.

**Files:**
- Modify: `tests/test_fixtures.py`

- [ ] **Step 1: Atualizar os dois skips dinâmicos**

Localizar e substituir:

```python
# Antes:
if gabarito is None:
    pytest.skip(f"Gabarito ausente para: {desc}")
if not formula_str or not str(formula_str).startswith("="):
    pytest.skip(f"Fórmula ausente/inválida para: {desc}")
```

Por:

```python
# Depois:
if gabarito is None:
    pytest.skip(
        f"[fixture-gap] Gabarito ausente para: {desc!r}. "
        "Adicione o valor esperado na coluna D do fixture."
    )
if not formula_str or not str(formula_str).startswith("="):
    pytest.skip(
        f"[fixture-gap] Fórmula ausente/inválida para: {desc!r}. "
        "Coluna B deve conter uma fórmula começando com '='."
    )
```

O prefixo `[fixture-gap]` permite filtrar skips por problema em CI:
```bash
pytest tests/test_fixtures.py -v 2>&1 | grep "fixture-gap"
```

- [ ] **Step 2: Confirmar que a suite continua verde**

```bash
python -m pytest tests/test_fixtures.py -q
```
Expected: mesmos resultados, skips agora com mensagem `[fixture-gap]`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_fixtures.py
git commit -m "test: add structured [fixture-gap] reason to dynamic pytest.skip calls"
```

---

## Task 8 — Validação final: suite completa + QA

- [ ] **Step 1: Rodar suite completa**

```bash
python -m pytest tests/ -q
```
Expected: 456+ passed (pode subir com novos testes), 0 failed, 1 warning (openpyxl/zipfile — conhecido).

- [ ] **Step 2: Verificar que nenhum item de dívida técnica #4–#10 persiste**

```bash
# #7: sem imports duplicados
grep -n "import math as _m" src/phase_a4/formula_evaluator.py
# Esperado: nenhuma linha

# #10: _sdiv cobre string
python -c "
import sys; sys.path.insert(0,'src/phase_a4'); sys.path.insert(0,'libs/trustware')
from formula_evaluator import _sdiv, _DIV0
assert _sdiv(10,'0') == _DIV0, 'FALHOU'
print('_sdiv string OK')
"

# #4: normalizer loga
python -c "
import sys, logging; sys.path.insert(0,'src/phase_a1_5'); sys.path.insert(0,'libs/trustware')
logging.basicConfig(level=logging.DEBUG)
from normalizer import tokenize_formula
tokenize_formula('=((((broken')
print('tokenize_formula OK — não lançou exceção')
"

# #5: repair_orchestrator tem docstring clara
python -c "
import sys; sys.path.insert(0,'src/phase_a4'); sys.path.insert(0,'libs/trustware')
import repair_orchestrator
print(repair_orchestrator.__doc__[:80])
"
```

- [ ] **Step 3: Commit final de consolidação**

```bash
git add -A
git commit -m "chore: tech debt items 4-10 complete — all 456+ tests passing"
```

---

## Checklist de Cobertura (self-review)

| Item | Task | Coberto? |
|---|---|---|
| #4 `except Exception: pass` no normalizer | Task 4 | ✅ |
| #5 repair_orchestrator stub sem clareza | Task 5 | ✅ |
| #6 classes duplicadas (risco) | Task 6 | ✅ (teste de guarda) |
| #7 `import math` duplicado | Task 1 | ✅ |
| #8 `_pct` nunca chamada internamente | Task 2 | ✅ |
| #9 `pytest.skip` sem reason rastreável | Task 7 | ✅ |
| #10 `_sdiv` não cobre string `"0"` | Task 3 | ✅ |
| Suite verde durante todo o processo | Task 8 | ✅ |

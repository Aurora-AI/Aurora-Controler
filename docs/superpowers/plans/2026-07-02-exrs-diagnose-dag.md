# EXRS `diagnose` — Diagnóstico DAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar `exrs diagnose <arquivo.xlsx>` — comando que roda só A0→A2.5 (sem LLM, sem Docker) e entrega um relatório HTML com o grafo visual de dependências + uma tabela de riscos (referências externas, fórmulas não classificadas, células órfãs, valores hardcoded).

**Architecture:** Dois módulos novos e puros (`risk_analysis.py` detecta os riscos, `diagnose_report.py` renderiza o HTML final) mais um novo subcomando em `src/cli/main.py` que orquestra as fases A0→A2.5 diretamente (não via `orchestrate_pipeline`, que sempre avança até A4/Docker) e reaproveita `phase_b2/graph_assembler.py` + `phase_b2/html_visualizer.py` já existentes, sem modificá-los.

**Tech Stack:** Python 3.14, Pydantic (contratos existentes), stdlib apenas nos módulos novos.

## Global Constraints

- Nenhuma dependência nova.
- `phase_b2/html_visualizer.py` e `phase_b2/graph_assembler.py` **não são modificados** — só consumidos.
- `libs/trustware/pipeline_contracts.py` **não é modificado** — `RiskFinding` é um modelo local a `src/cli/risk_analysis.py`, não um contrato compartilhado.
- Saída de `exrs diagnose`: só `<nome>_diagnostico/relatorio.html`. Sem `.py`, sem JSONs técnicos (isso é escopo de `exrs compile`).
- Sem LLM, sem Docker — só as fases determinísticas A0→A2.5.
- Segue o padrão de `sys.path.insert` já usado em `src/cli/main.py` para imports entre módulos.

---

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/cli/risk_analysis.py` | 4 detectores de risco + `RiskFinding` + `analyze_risks` agregador |
| `src/cli/diagnose_report.py` | Renderiza o HTML final (grafo + tabela de riscos) |
| `src/cli/main.py` | Modificado: novo subcomando `diagnose` + `run_diagnose_cli` |
| `tests/test_risk_analysis.py` | Testa os 4 detectores isoladamente |
| `tests/test_diagnose_report.py` | Testa `render_diagnose_report` |
| `tests/test_cli_diagnose.py` | Testa `exrs diagnose` ponta-a-ponta |

---

### Task 1: Detectores de risco (`risk_analysis.py`)

**Files:**
- Create: `src/cli/risk_analysis.py`
- Test: `tests/test_risk_analysis.py`

**Interfaces:**
- Consumes: `ExecutionDAG` (`libs/trustware/pipeline_contracts.py:89`, campos `nodes: list[DAGNode]`,
  `edges: list[DAGEdge]`), `DAGNode` (campos `id`, `formula_raw`), `DAGEdge` (campos `source`,
  `target`), `FormulaRegistryMap` (`pipeline_contracts.py:276`, campo `patterns: list[FormulaPattern]`),
  `FormulaPattern` (campos `node_id`, `pattern_class: PatternClass`, `formula_raw`), `PatternClass`
  (`pipeline_contracts.py:244`, valores `EXTERNAL_REF`, `UNRESOLVED`), `NormalizedWorkbookIR`
  (campo `sheets: list[NormalizedSheet]`), `NormalizedSheet` (campos `name`, `cells: list[NormalizedCell]`),
  `NormalizedCell` (campos `coordinate`, `formula_tokens: list[FormulaToken]`), `FormulaToken`
  (`pipeline_contracts.py:121`, campos `type: FormulaTokenType`, `value: str`), `FormulaTokenType`
  (`pipeline_contracts.py:110`, valor `CONSTANT`).
- Produces: `RiskFinding` (Pydantic `BaseModel`, campos `node_id: str`, `category: str`,
  `description: str`); `find_external_refs(fmap: FormulaRegistryMap) -> list[RiskFinding]`;
  `find_unresolved(fmap: FormulaRegistryMap) -> list[RiskFinding]`;
  `find_orphan_cells(dag: ExecutionDAG) -> list[RiskFinding]`;
  `find_hardcoded_values(norm_ir: NormalizedWorkbookIR) -> list[RiskFinding]`;
  `analyze_risks(dag: ExecutionDAG, fmap: FormulaRegistryMap, norm_ir: NormalizedWorkbookIR) ->
  list[RiskFinding]` — usado por `main.py` (Task 3) e testado isoladamente por `diagnose_report.py`
  (Task 2, via fixtures de teste, não import direto).

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_risk_analysis.py`:

```python
"""Testes de src/cli/risk_analysis.py — detectores de risco do diagnóstico DAG."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline_contracts import (
    DAGEdge, DAGNode, ExecutionDAG, FormulaPattern, FormulaRegistryMap,
    FormulaToken, FormulaTokenType, NormalizedCell, NormalizedSheet,
    NormalizedWorkbookIR, PatternClass,
)
from cli.risk_analysis import (
    analyze_risks, find_external_refs, find_hardcoded_values,
    find_orphan_cells, find_unresolved,
)


def test_find_external_refs_returns_finding_per_external_ref_pattern():
    fmap = FormulaRegistryMap(
        file_path="p.xlsx",
        patterns=[
            FormulaPattern(node_id="Sheet1!A1", formula_raw="=[Outro.xlsx]Sheet1!A1",
                            pattern_class=PatternClass.EXTERNAL_REF),
            FormulaPattern(node_id="Sheet1!A2", formula_raw="=A1+1",
                            pattern_class=PatternClass.ARITHMETIC),
        ],
        registry_used=[],
    )
    findings = find_external_refs(fmap)
    assert len(findings) == 1
    assert findings[0].node_id == "Sheet1!A1"
    assert findings[0].category == "external_ref"


def test_find_unresolved_returns_finding_per_unresolved_pattern():
    fmap = FormulaRegistryMap(
        file_path="p.xlsx",
        patterns=[
            FormulaPattern(node_id="Sheet1!B1", formula_raw="=COMPLEXFUNC(A1)",
                            pattern_class=PatternClass.UNRESOLVED),
        ],
        registry_used=[],
    )
    findings = find_unresolved(fmap)
    assert len(findings) == 1
    assert findings[0].node_id == "Sheet1!B1"
    assert findings[0].category == "unresolved"


def test_find_orphan_cells_detects_formula_node_with_no_edges():
    dag = ExecutionDAG(
        nodes=[
            DAGNode(id="Sheet1!A1", sheet="Sheet1", coordinate="A1", formula_raw=None, dependencies=[]),
            DAGNode(id="Sheet1!A2", sheet="Sheet1", coordinate="A2", formula_raw="=A1+1", dependencies=["Sheet1!A1"]),
            DAGNode(id="Sheet1!A3", sheet="Sheet1", coordinate="A3", formula_raw="=99*2", dependencies=[]),
        ],
        edges=[DAGEdge(source="Sheet1!A1", target="Sheet1!A2")],
        topological_order=["Sheet1!A1", "Sheet1!A2", "Sheet1!A3"],
    )
    findings = find_orphan_cells(dag)
    assert len(findings) == 1
    assert findings[0].node_id == "Sheet1!A3"
    assert findings[0].category == "orphan_cell"


def test_find_orphan_cells_ignores_static_cells_without_formula():
    dag = ExecutionDAG(
        nodes=[DAGNode(id="Sheet1!A1", sheet="Sheet1", coordinate="A1", formula_raw=None, dependencies=[])],
        edges=[], topological_order=["Sheet1!A1"],
    )
    assert find_orphan_cells(dag) == []


def test_find_hardcoded_values_detects_numeric_constant_token():
    norm_ir = NormalizedWorkbookIR(
        file_path="p.xlsx",
        sheets=[NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[
            NormalizedCell(
                coordinate="A1", formula_raw="=A2*1.15", data_type="n",
                formula_tokens=[
                    FormulaToken(type=FormulaTokenType.OPERAND, value="A2"),
                    FormulaToken(type=FormulaTokenType.OPERATOR, value="*"),
                    FormulaToken(type=FormulaTokenType.CONSTANT, value="1.15"),
                ],
            ),
        ])],
    )
    findings = find_hardcoded_values(norm_ir)
    assert len(findings) == 1
    assert findings[0].node_id == "Sheet1!A1"
    assert findings[0].category == "hardcoded_value"


def test_find_hardcoded_values_ignores_string_constants():
    norm_ir = NormalizedWorkbookIR(
        file_path="p.xlsx",
        sheets=[NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[
            NormalizedCell(
                coordinate="A1", formula_raw='=IF(A2="sim",1,0)', data_type="n",
                formula_tokens=[
                    FormulaToken(type=FormulaTokenType.FUNCTION, value="IF"),
                    FormulaToken(type=FormulaTokenType.CONSTANT, value='"sim"'),
                ],
            ),
        ])],
    )
    assert find_hardcoded_values(norm_ir) == []


def test_analyze_risks_aggregates_all_four_detectors():
    dag = ExecutionDAG(
        nodes=[DAGNode(id="Sheet1!A3", sheet="Sheet1", coordinate="A3", formula_raw="=99*2", dependencies=[])],
        edges=[], topological_order=["Sheet1!A3"],
    )
    fmap = FormulaRegistryMap(
        file_path="p.xlsx",
        patterns=[FormulaPattern(node_id="Sheet1!A1", formula_raw="=[X.xlsx]Sheet1!A1",
                                  pattern_class=PatternClass.EXTERNAL_REF)],
        registry_used=[],
    )
    norm_ir = NormalizedWorkbookIR(
        file_path="p.xlsx",
        sheets=[NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[])],
    )
    findings = analyze_risks(dag, fmap, norm_ir)
    categories = {f.category for f in findings}
    assert "external_ref" in categories
    assert "orphan_cell" in categories
```

- [ ] **Step 2: Rodar o teste e confirmar falha**

Run: `.venv/Scripts/python.exe -m pytest tests/test_risk_analysis.py -v`
Expected: `ModuleNotFoundError: No module named 'cli.risk_analysis'`

- [ ] **Step 3: Implementar `src/cli/risk_analysis.py`**

```python
"""
EXRS CLI — Detectores de risco do diagnóstico DAG (`exrs diagnose`).

Cada detector é uma função pura sobre os artefatos já produzidos por A0→A2.5 (nenhum
parser de fórmula novo — reaproveita a classificação da Fase A2.5 e a tokenização da
Fase A1.5). `RiskFinding` é local a este módulo, não um contrato compartilhado com o SaaS.
"""
from pydantic import BaseModel

from pipeline_contracts import (
    ExecutionDAG, FormulaRegistryMap, FormulaTokenType, NormalizedWorkbookIR, PatternClass,
)


class RiskFinding(BaseModel):
    """Um risco individual detectado na planilha."""
    node_id: str
    category: str  # "external_ref" | "unresolved" | "orphan_cell" | "hardcoded_value"
    description: str


def find_external_refs(fmap: FormulaRegistryMap) -> list[RiskFinding]:
    """Referências a outros arquivos (`[Outro.xlsx]`) — dependência externa frágil."""
    return [
        RiskFinding(
            node_id=p.node_id, category="external_ref",
            description=f"Referência externa a outro arquivo: {p.formula_raw}",
        )
        for p in fmap.patterns if p.pattern_class == PatternClass.EXTERNAL_REF
    ]


def find_unresolved(fmap: FormulaRegistryMap) -> list[RiskFinding]:
    """Fórmulas que o classificador determinístico não conseguiu entender."""
    return [
        RiskFinding(
            node_id=p.node_id, category="unresolved",
            description=f"Fórmula não classificada (lógica de caixa-preta): {p.formula_raw}",
        )
        for p in fmap.patterns if p.pattern_class == PatternClass.UNRESOLVED
    ]


def find_orphan_cells(dag: ExecutionDAG) -> list[RiskFinding]:
    """Células com fórmula mas sem nenhuma aresta (nem entrada nem saída) no DAG —
    possível célula morta ou hardcoding disfarçado de fórmula."""
    touched = {e.source for e in dag.edges} | {e.target for e in dag.edges}
    return [
        RiskFinding(
            node_id=n.id, category="orphan_cell",
            description="Célula com fórmula isolada do grafo — não depende de nada nem é usada por outra fórmula.",
        )
        for n in dag.nodes if n.formula_raw and n.id not in touched
    ]


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def find_hardcoded_values(norm_ir: NormalizedWorkbookIR) -> list[RiskFinding]:
    """Valores numéricos fixados diretamente dentro de fórmulas (ex: `=A1*1.15`), em vez
    de referenciar uma célula de parâmetro — reaproveita a tokenização já feita na Fase A1.5."""
    findings: list[RiskFinding] = []
    for sheet in norm_ir.sheets:
        for cell in sheet.cells:
            for token in cell.formula_tokens:
                if token.type == FormulaTokenType.CONSTANT and _is_numeric(token.value):
                    findings.append(RiskFinding(
                        node_id=f"{sheet.name}!{cell.coordinate}", category="hardcoded_value",
                        description=f"Valor numérico fixo embutido na fórmula: {token.value}",
                    ))
                    break  # 1 achado por célula, não 1 por token
    return findings


def analyze_risks(
    dag: ExecutionDAG, fmap: FormulaRegistryMap, norm_ir: NormalizedWorkbookIR,
) -> list[RiskFinding]:
    """Agrega os 4 detectores."""
    return (
        find_external_refs(fmap)
        + find_unresolved(fmap)
        + find_orphan_cells(dag)
        + find_hardcoded_values(norm_ir)
    )
```

- [ ] **Step 4: Rodar o teste e confirmar sucesso**

Run: `.venv/Scripts/python.exe -m pytest tests/test_risk_analysis.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/cli/risk_analysis.py tests/test_risk_analysis.py
git commit -m "feat(cli): detectores de risco do diagnóstico DAG (risk_analysis.py)"
```

---

### Task 2: Relatório de diagnóstico (`diagnose_report.py`)

**Files:**
- Create: `src/cli/diagnose_report.py`
- Test: `tests/test_diagnose_report.py`

**Interfaces:**
- Consumes: `RiskFinding` (Task 1, `src/cli/risk_analysis.py`).
- Produces: `render_diagnose_report(graph_html: str, findings: list[RiskFinding], source_file: str)
  -> str` — retorna o HTML completo. Usado por `main.py` (Task 3).

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_diagnose_report.py`:

```python
"""Testes de src/cli/diagnose_report.py — relatório de diagnóstico DAG."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cli.risk_analysis import RiskFinding
from cli.diagnose_report import render_diagnose_report


def _findings():
    return [
        RiskFinding(node_id="Sheet1!A1", category="external_ref", description="ref externa"),
        RiskFinding(node_id="Sheet1!B2", category="hardcoded_value", description="valor fixo 1.15"),
    ]


def test_report_embeds_graph_html_verbatim():
    graph_html = "<html><body><div id='mynetwork'>GRAFO_MARCADOR</div></body></html>"
    report = render_diagnose_report(graph_html, _findings(), source_file="p.xlsx")
    assert "GRAFO_MARCADOR" in report


def test_report_lists_all_findings():
    report = render_diagnose_report("<html></html>", _findings(), source_file="p.xlsx")
    assert "Sheet1!A1" in report
    assert "Sheet1!B2" in report
    assert "external_ref" in report or "Referência" in report


def test_report_with_no_findings_shows_clean_message():
    report = render_diagnose_report("<html></html>", [], source_file="p.xlsx")
    assert "nenhum risco" in report.lower() or "0 risco" in report.lower()


def test_report_is_valid_html_structure():
    report = render_diagnose_report("<div>x</div>", _findings(), source_file="p.xlsx")
    assert report.strip().startswith("<!DOCTYPE html>")
    assert "<html" in report and "</html>" in report
```

- [ ] **Step 2: Rodar o teste e confirmar falha**

Run: `.venv/Scripts/python.exe -m pytest tests/test_diagnose_report.py -v`
Expected: `ModuleNotFoundError: No module named 'cli.diagnose_report'`

- [ ] **Step 3: Implementar `src/cli/diagnose_report.py`**

```python
"""
EXRS CLI — Relatório de diagnóstico DAG (`exrs diagnose`).

Combina o HTML do grafo (gerado por phase_b2/html_visualizer.py, embutido sem modificação)
com uma tabela de riscos abaixo dele. O destaque visual dos riscos acontece na tabela, não
por recoloração dentro do canvas do grafo — decisão registrada em
docs/superpowers/specs/2026-07-02-exrs-diagnose-dag-design.md (evita modificar
html_visualizer.py, já testado).
"""
import datetime

from cli.risk_analysis import RiskFinding

_CATEGORY_LABELS = {
    "external_ref": "Referência externa",
    "unresolved": "Fórmula não classificada",
    "orphan_cell": "Célula órfã",
    "hardcoded_value": "Valor hardcoded",
}

_CATEGORY_COLORS = {
    "external_ref": "#DC2626",
    "unresolved": "#D97706",
    "orphan_cell": "#7C3AED",
    "hardcoded_value": "#2563EB",
}


def _esc(v: str) -> str:
    return (
        str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_findings_table(findings: list[RiskFinding]) -> str:
    if not findings:
        return "<p class='clean'>✅ Nenhum risco detectado nesta planilha.</p>"
    rows = "\n".join(
        f"<tr><td>{_esc(f.node_id)}</td>"
        f"<td><span class='badge' style='background:{_CATEGORY_COLORS.get(f.category, '#64748B')}'>"
        f"{_esc(_CATEGORY_LABELS.get(f.category, f.category))}</span></td>"
        f"<td>{_esc(f.description)}</td></tr>"
        for f in findings
    )
    return f"""
    <table class="risks">
      <thead><tr><th>Célula</th><th>Categoria</th><th>Descrição</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    """


def render_diagnose_report(graph_html: str, findings: list[RiskFinding], source_file: str) -> str:
    """Retorna o HTML completo do relatório de diagnóstico."""
    now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    css = """
    body { font-family: -apple-system, sans-serif; background:#0F172A; color:#E2E8F0; margin:0; }
    .page { max-width: 1100px; margin: 0 auto; padding: 24px; }
    h1 { color:#F8FAFC; }
    .sub { color:#94A3B8; font-size:13px; margin-bottom:24px; }
    .graph-frame { border:1px solid #334155; border-radius:8px; overflow:hidden; margin-bottom:24px; }
    table.risks { width:100%; border-collapse:collapse; margin-top:12px; }
    table.risks th, table.risks td { text-align:left; padding:8px 12px; border-bottom:1px solid #334155; font-size:13px; }
    table.risks th { color:#94A3B8; font-weight:600; }
    .badge { color:#fff; padding:2px 8px; border-radius:4px; font-size:11px; }
    .clean { color:#4ADE80; }
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <title>EXRS — Diagnóstico de {_esc(source_file)}</title>
  <style>{css}</style>
</head>
<body>
<div class="page">
  <h1>🔍 Diagnóstico DAG — {_esc(source_file)}</h1>
  <div class="sub">Gerado em {now} · {len(findings)} risco(s) detectado(s)</div>
  <div class="graph-frame">{graph_html}</div>
  <h2>Riscos Detectados</h2>
  {_build_findings_table(findings)}
</div>
</body>
</html>"""
```

- [ ] **Step 4: Rodar o teste e confirmar sucesso**

Run: `.venv/Scripts/python.exe -m pytest tests/test_diagnose_report.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/cli/diagnose_report.py tests/test_diagnose_report.py
git commit -m "feat(cli): relatório HTML do diagnóstico DAG (grafo + tabela de riscos)"
```

---

### Task 3: Comando `exrs diagnose`

**Files:**
- Modify: `src/cli/main.py`
- Test: `tests/test_cli_diagnose.py`

**Interfaces:**
- Consumes: `classify_workbook(filepath: Path) -> CompatibilityReport` (`src/phase_a0/classifier.py:62`),
  `extract_structure(filepath: Path) -> WorkbookIR` (`src/phase_a1/extractor.py:60`),
  `normalize_workbook(raw_ir: WorkbookIR) -> NormalizedWorkbookIR` (`src/phase_a1_5/normalizer.py:281`),
  `build_dag(normalized_ir: NormalizedWorkbookIR) -> ExecutionDAG` (`src/phase_a2/graph_builder.py:27`),
  `classify_workbook(normalized_ir, registry) -> FormulaRegistryMap` (aliasing necessário — mesmo
  nome que a função de A0 — importar `as classify_patterns`, `src/phase_a2_5/pattern_registry.py:455`),
  `build_registry() -> list[PatternRegistryEntry]` (`src/phase_a2_5/pattern_registry.py:21`),
  `route(workbook_class: WorkbookClass, compile_decision: CompileDecision, filepath: Path) -> str`
  (`src/orchestrator/pipeline_orchestrator.py:38`, retorna `"escalate"|"track_c"|"track_a"`),
  `build_graph(dag: dict, norm_ir: dict, intent: IntentCapture) -> StagedRuleGraph`
  (`src/phase_b2/graph_assembler.py:63`), `generate_html(graph: StagedRuleGraph) -> str`
  (`src/phase_b2/html_visualizer.py:85`), `IntentCapture` (`libs/trustware/pipeline_contracts.py:177`,
  campos `workbook_name: str`, `user_goal: str`, `input_parameters: list`, `output_metrics: list`),
  `analyze_risks` (Task 1), `render_diagnose_report` (Task 2).
- Produces: `run_diagnose_cli(xlsx_path: Path, dest_dir: Path | None) -> int` — reaproveitável por
  testes e por uma futura tela de diagnóstico na UI web (fora de escopo desta OS).

- [ ] **Step 1: Adicionar `phase_b2` ao `sys.path` de `main.py`**

Em `src/cli/main.py`, editar o bloco de `sys.path.insert` (linhas 13-21) para incluir
`phase_b2`:

```python
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (
    _REPO_ROOT / "libs" / "trustware", _REPO_ROOT / "src" / "orchestrator",
    _REPO_ROOT / "src" / "phase_a0", _REPO_ROOT / "src" / "phase_a1",
    _REPO_ROOT / "src" / "phase_a1_5", _REPO_ROOT / "src" / "phase_a2",
    _REPO_ROOT / "src" / "phase_a2_5", _REPO_ROOT / "src" / "phase_a3",
    _REPO_ROOT / "src" / "phase_a4", _REPO_ROOT / "src" / "phase_b2",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
```

- [ ] **Step 2: Escrever o teste que falha**

Criar `tests/test_cli_diagnose.py`:

```python
"""Testes de src/cli/main.py — comando `exrs diagnose`."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"


def test_diagnose_produces_report_by_default(tmp_path):
    from cli.main import main

    dest = tmp_path / "coverage_test_diagnostico"
    exit_code = main(["diagnose", str(FIXTURE), "--out", str(dest)])

    assert exit_code == 0
    report = dest / "relatorio.html"
    assert report.exists()
    html = report.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html


def test_diagnose_report_flags_external_ref_from_fixture(tmp_path):
    """A fixture coverage_test.xlsx tem uma aba 'ExternalRef' com 3 fórmulas — o relatório
    deve conter pelo menos um achado da categoria external_ref."""
    from cli.main import main

    dest = tmp_path / "coverage_test_diagnostico"
    main(["diagnose", str(FIXTURE), "--out", str(dest)])

    html = (dest / "relatorio.html").read_text(encoding="utf-8")
    assert "Referência externa" in html


def test_diagnose_output_has_no_python_module_or_json(tmp_path):
    from cli.main import main

    dest = tmp_path / "coverage_test_diagnostico"
    main(["diagnose", str(FIXTURE), "--out", str(dest)])

    names = {f.name for f in dest.iterdir()}
    assert not any(n.endswith(".py") for n in names)
    assert not any(n.endswith(".json") for n in names)


def test_diagnose_missing_file_returns_error(tmp_path):
    from cli.main import main

    exit_code = main(["diagnose", str(tmp_path / "nao_existe.xlsx")])
    assert exit_code == 1


def test_diagnose_no_args_returns_usage_error():
    from cli.main import main

    exit_code = main(["diagnose"])
    assert exit_code == 2
```

- [ ] **Step 3: Rodar o teste e confirmar falha**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli_diagnose.py -v`
Expected: `argparse` erro de subcomando desconhecido (`diagnose` ainda não existe) ou
`AttributeError`/falha de asserção — o subcomando `diagnose` ainda não foi adicionado.

- [ ] **Step 4: Implementar `run_diagnose_cli` e o subcomando em `src/cli/main.py`**

Adicionar após os imports existentes (linha 27, após `from cli.output import write_clean_output`):

```python
from classifier import classify_workbook as classify_a0
from extractor import extract_structure
from normalizer import normalize_workbook
from graph_builder import build_dag
from pattern_registry import classify_workbook as classify_patterns, build_registry
from pipeline_orchestrator import route
from pipeline_contracts import IntentCapture
from graph_assembler import build_graph
from html_visualizer import generate_html

from cli.risk_analysis import analyze_risks
from cli.diagnose_report import render_diagnose_report
```

Adicionar a função `run_diagnose_cli` (após `run_compile_cli`, antes de `def main`):

```python
def run_diagnose_cli(xlsx_path: Path, dest_dir: Path | None) -> int:
    if not xlsx_path.exists():
        print(f"Erro: arquivo não encontrado: {xlsx_path}", file=sys.stderr)
        return 1

    stem = xlsx_path.stem

    report = classify_a0(xlsx_path)
    track = route(report.workbook_class, report.compile_decision, xlsx_path)
    if track != "track_a":
        print(f"[EXRS] Diagnóstico não aplicável a este arquivo (classificação: {track}).",
              file=sys.stderr)
        if report.escalate_reasons:
            print(f"       Motivos: {', '.join(report.escalate_reasons)}", file=sys.stderr)
        return 1

    raw_ir = extract_structure(xlsx_path)
    norm_ir = normalize_workbook(raw_ir)
    dag = build_dag(norm_ir)
    fmap = classify_patterns(norm_ir, build_registry())

    findings = analyze_risks(dag, fmap, norm_ir)

    intent = IntentCapture(workbook_name=stem, user_goal="", input_parameters=[], output_metrics=[])
    graph = build_graph(dag.model_dump(), norm_ir.model_dump(), intent)
    graph_html = generate_html(graph)

    report_html = render_diagnose_report(graph_html, findings, source_file=xlsx_path.name)

    dest = dest_dir or Path.cwd() / f"{stem}_diagnostico"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "relatorio.html").write_text(report_html, encoding="utf-8")

    print(f"[EXRS] Diagnóstico concluído: {len(findings)} risco(s) detectado(s).")
    print(f"[EXRS] Relatório: {dest / 'relatorio.html'}")
    return 0
```

Modificar `def main` para adicionar o subcomando `diagnose` (após o bloco `compile_parser`,
antes de `sub.add_parser("ui", ...)`):

```python
    diagnose_parser = sub.add_parser("diagnose", help="Gera um relatório de diagnóstico (grafo + riscos)")
    diagnose_parser.add_argument("xlsx", nargs="?", type=Path, help="Caminho para o arquivo .xlsx")
    diagnose_parser.add_argument("--out", type=Path, default=None, help="Pasta de saída (padrão: ./<nome>_diagnostico)")
```

E adicionar o roteamento do subcomando (após o bloco `if args.command == "compile":`, antes
de `if args.command == "ui":`):

```python
    if args.command == "diagnose":
        if args.xlsx is None:
            diagnose_parser.print_usage(sys.stderr)
            return 2
        return run_diagnose_cli(args.xlsx, args.out)
```

- [ ] **Step 5: Rodar o teste e confirmar sucesso**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli_diagnose.py -v`
Expected: `5 passed`

- [ ] **Step 6: Rodar a suíte completa (regressão)**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: nenhuma falha nova em relação ao baseline anterior a esta OS.

- [ ] **Step 7: Smoke test real do comando `exrs diagnose` instalado via pip**

Run: `exrs diagnose tests/fixtures/coverage_test.xlsx --out /tmp/diag_smoke_test`
Expected: exit 0; `/tmp/diag_smoke_test/relatorio.html` existe e contém `Referência externa`
(a fixture tem a aba `ExternalRef`).

- [ ] **Step 8: Commit**

```bash
git add src/cli/main.py tests/test_cli_diagnose.py
git commit -m "feat(cli): comando 'exrs diagnose' — grafo + riscos, sem LLM/Docker"
```

---

## Self-Review (registrado)

- **Cobertura da spec:** 4 detectores de risco (Task 1), grafo + tabela combinados no relatório
  (Task 2), subcomando `diagnose` reaproveitando A0→A2.5 sem `orchestrate_pipeline` (Task 3),
  `IntentCapture` vazio para reaproveitar `build_graph`/`generate_html` sem modificá-los (Task 3),
  saída limpa sem `.py`/JSONs (Task 3, testado em `test_diagnose_output_has_no_python_module_or_json`),
  tratamento de erro para `track_c`/`ESCALATE` (Task 3). Endpoint web e score agregado ficaram
  de fora — coerentes com o "Fora de escopo" da spec.
- **Placeholders:** nenhum "TBD"/"implementar depois" — todo código de cada step está completo.
- **Consistência de tipos:** `RiskFinding(node_id, category, description)` (Task 1) é usado com
  os mesmos nomes de campo em `diagnose_report.py` (Task 2, `_build_findings_table`) e nos testes
  de `main.py` (Task 3, via `analyze_risks`). `render_diagnose_report(graph_html, findings,
  source_file)` (Task 2) é chamado com a mesma assinatura em `run_diagnose_cli` (Task 3).

# EXRS CLI + UI Web Local — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empacotar o EXRS como CLI instalável (`exrs compile` / `exrs ui`) para desenvolvedores/TIs freelancer, gerando um módulo Python "replay" real (sem depender de LLM) + relatório HTML, com uma interface web local opcional.

**Architecture:** Novo pacote `src/cli/` (importável via o `.pth` de editable-install já existente, que expõe `src/` no `sys.path`). `codegen.py` renderiza um módulo Python standalone que reproduz o grafo de cálculo usando o mesmo motor de fórmulas (`formula_evaluator.py`) já validado pela Fase A4 — sem transpilar fórmula por fórmula, sem LLM obrigatório. `output.py` monta a pasta de entrega limpa. `main.py` é o entry point CLI. `web_app.py` é uma casca FastAPI local (execução síncrona em memória, sem Celery/Redis) para quem prefere navegador.

**Tech Stack:** Python 3.14, FastAPI (já é dependência), argparse (stdlib), pytest + TestClient.

## Global Constraints

- Python `>=3.14` (já fixado em `pyproject.toml`).
- Nenhuma dependência nova além das já presentes (`fastapi`, `uvicorn`, `python-multipart`, `httpx` para testes) — o design travou "FastAPI + HTML simples" para evitar dependência nova (Streamlit foi descartado).
- Sandbox A4 continua exigindo Docker (decisão travada no design) — este plano não mexe em `runner.py`/sandbox.
- Saída limpa por padrão (`.py` + `.html`); JSONs técnicos só com `--debug` (decisão travada).
- Sem licenciamento/billing nesta fase (decisão travada) — nenhuma lógica de chave/ativação neste plano.
- Seguir o padrão de `sys.path.insert` já usado em todo o repo (`run_pipeline.py`, `src/api/main.py`) — não introduzir um sistema de import diferente.

---

## Mapa de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/cli/__init__.py` | Marcador de pacote (vazio) |
| `src/cli/codegen.py` | Renderiza o módulo Python "replay" a partir de `ExecutionDAG` + `FormulaRegistryMap` + `NormalizedWorkbookIR` |
| `src/cli/output.py` | Monta a pasta de saída limpa: `.py` + engine vendorizado + relatório `.html` (+ JSONs se `--debug`) |
| `src/cli/main.py` | Entry point `exrs` — subcomandos `compile` e `ui` |
| `src/cli/web_app.py` | App FastAPI para `exrs ui` — upload, status em memória, resultado |
| `pyproject.toml` | Modificado: `[project.scripts]` |
| `tests/test_codegen.py` | Testa `render_replay_module` |
| `tests/test_cli_output.py` | Testa `write_clean_output` (limpo vs `--debug`) |
| `tests/test_cli_compile.py` | Testa `exrs compile` ponta-a-ponta (via chamada de função, não subprocess) |
| `tests/test_cli_ui.py` | Testa `web_app` via `TestClient` |

---

### Task 1: Renderizador do módulo Python "replay" (`codegen.py`)

**Files:**
- Create: `src/cli/__init__.py`
- Create: `src/cli/codegen.py`
- Test: `tests/test_codegen.py`

**Interfaces:**
- Consumes: `ExecutionDAG` (`libs/trustware/pipeline_contracts.py:89`, campos `nodes: list[DAGNode]`, `topological_order: list[str]`), `DAGNode` (campos `id`, `sheet`, `coordinate`, `formula_raw`, `dependencies`), `FormulaRegistryMap` (`pipeline_contracts.py:276`, campo `patterns: list[FormulaPattern]`), `FormulaPattern` (campos `node_id`, `pattern_class: PatternClass`), `PatternClass` (`pipeline_contracts.py:244`, valores `EXTERNAL_REF`, `UNRESOLVED` a excluir do replay; demais valores são avaliáveis), `NormalizedWorkbookIR` (`pipeline_contracts.py:145`, campo `sheets: list[NormalizedSheet]`), `NormalizedSheet` (campos `name`, `cells: list[NormalizedCell]`), `NormalizedCell` (campos `coordinate`, `formula_raw`, `value_static`).
- Produces: `render_replay_module(dag: ExecutionDAG, fmap: FormulaRegistryMap, norm_ir: NormalizedWorkbookIR, source_file: str) -> str` — retorna o texto-fonte Python completo do módulo replay. Usado por `output.py` (Task 2).

- [ ] **Step 1: Criar `src/cli/__init__.py` vazio**

```bash
mkdir -p src/cli
touch src/cli/__init__.py
```

- [ ] **Step 2: Escrever o teste que falha**

Criar `tests/test_codegen.py`:

```python
"""Testes de src/cli/codegen.py — renderizador do módulo Python 'replay'."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline_contracts import (
    DAGEdge, DAGNode, ExecutionDAG, FormulaPattern, FormulaRegistryMap,
    NormalizedCell, NormalizedSheet, NormalizedWorkbookIR, PatternClass,
)
from cli.codegen import render_replay_module


def _fixture():
    dag = ExecutionDAG(
        nodes=[
            DAGNode(id="Sheet1!A1", sheet="Sheet1", coordinate="A1", formula_raw=None, dependencies=[]),
            DAGNode(id="Sheet1!A2", sheet="Sheet1", coordinate="A2", formula_raw=None, dependencies=[]),
            DAGNode(id="Sheet1!A3", sheet="Sheet1", coordinate="A3", formula_raw="=A1+A2", dependencies=["Sheet1!A1", "Sheet1!A2"]),
        ],
        edges=[
            DAGEdge(source="Sheet1!A1", target="Sheet1!A3"),
            DAGEdge(source="Sheet1!A2", target="Sheet1!A3"),
        ],
        topological_order=["Sheet1!A1", "Sheet1!A2", "Sheet1!A3"],
    )
    fmap = FormulaRegistryMap(
        file_path="planilha.xlsx",
        patterns=[
            FormulaPattern(node_id="Sheet1!A3", formula_raw="=A1+A2", pattern_class=PatternClass.ARITHMETIC),
        ],
        registry_used=[],
    )
    norm_ir = NormalizedWorkbookIR(
        file_path="planilha.xlsx",
        sheets=[
            NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[
                NormalizedCell(coordinate="A1", formula_raw=None, value_static=10, data_type="n"),
                NormalizedCell(coordinate="A2", formula_raw=None, value_static=32, data_type="n"),
                NormalizedCell(coordinate="A3", formula_raw="=A1+A2", value_static=None, data_type="n"),
            ]),
        ],
    )
    return dag, fmap, norm_ir


def test_render_produces_valid_python_syntax():
    dag, fmap, norm_ir = _fixture()
    source = render_replay_module(dag, fmap, norm_ir, source_file="planilha.xlsx")
    compile(source, "<generated>", "exec")  # levanta SyntaxError se inválido


def test_render_includes_static_values_and_formula():
    dag, fmap, norm_ir = _fixture()
    source = render_replay_module(dag, fmap, norm_ir, source_file="planilha.xlsx")
    assert "'Sheet1!A1': 10" in source
    assert "'Sheet1!A2': 32" in source
    assert "'Sheet1!A3': '=A1+A2'" in source
    assert "def compute(" in source


def test_render_excludes_external_ref_and_unresolved():
    dag, fmap, norm_ir = _fixture()
    fmap.patterns.append(
        FormulaPattern(node_id="Sheet1!A4", formula_raw="=[Other.xlsx]Sheet1!A1", pattern_class=PatternClass.EXTERNAL_REF)
    )
    dag.nodes.append(DAGNode(id="Sheet1!A4", sheet="Sheet1", coordinate="A4", formula_raw="=[Other.xlsx]Sheet1!A1", dependencies=[]))
    dag.topological_order.append("Sheet1!A4")
    norm_ir.sheets[0].cells.append(
        NormalizedCell(coordinate="A4", formula_raw="=[Other.xlsx]Sheet1!A1", value_static=None, data_type="n")
    )
    source = render_replay_module(dag, fmap, norm_ir, source_file="planilha.xlsx")
    assert "Sheet1!A4" not in source.split("FORMULAS = ")[1].split("}")[0]


def test_render_executes_and_computes_correct_result():
    """O módulo gerado, quando executado, calcula A3 = A1 + A2 = 42 — usando o mesmo
    motor (formula_evaluator/normalizer) que já valida a Fase A4."""
    dag, fmap, norm_ir = _fixture()
    source = render_replay_module(dag, fmap, norm_ir, source_file="planilha.xlsx")
    namespace = {"__name__": "generated_module"}
    # Simula a presença dos módulos vendorizados no sys.path (Task 2 os copia de verdade;
    # aqui expomos evaluate_formula/expand_range reais para validar a lógica do compute()).
    import types
    fake_engine = types.ModuleType("_exrs_formula_engine")
    fake_range = types.ModuleType("_exrs_range_utils")
    sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a4"))
    sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a1_5"))
    from formula_evaluator import evaluate_formula as real_evaluate_formula
    from normalizer import expand_range as real_expand_range
    fake_engine.evaluate_formula = real_evaluate_formula
    fake_range.expand_range = real_expand_range
    sys.modules["_exrs_formula_engine"] = fake_engine
    sys.modules["_exrs_range_utils"] = fake_range
    try:
        exec(compile(source, "<generated>", "exec"), namespace)
        result = namespace["compute"]()
        assert result["Sheet1!A3"] == 42
    finally:
        del sys.modules["_exrs_formula_engine"]
        del sys.modules["_exrs_range_utils"]
```

- [ ] **Step 3: Rodar o teste e confirmar falha**

Run: `.venv/Scripts/python.exe -m pytest tests/test_codegen.py -v`
Expected: `ModuleNotFoundError: No module named 'cli.codegen'` (ou `cli`)

- [ ] **Step 4: Implementar `src/cli/codegen.py`**

```python
"""
EXRS CLI — Codegen do módulo Python 'replay'.

Gera um .py standalone que reproduz o grafo de cálculo de uma planilha sem depender de
Excel nem de LLM: usa o MESMO motor (evaluate_formula + expand_range) que a Fase A4 já usa
para validar o workbook (src/phase_a4/runner.py::validate_workbook), só que emitido como
código-fonte estático em vez de executado inline. Fórmulas EXTERNAL_REF e UNRESOLVED são
excluídas (não avaliáveis deterministicamente — mesma regra do validador).
"""
from pipeline_contracts import (
    ExecutionDAG, FormulaRegistryMap, NormalizedWorkbookIR, PatternClass,
)

_EXCLUDED = {PatternClass.EXTERNAL_REF, PatternClass.UNRESOLVED}


def render_replay_module(
    dag: ExecutionDAG,
    fmap: FormulaRegistryMap,
    norm_ir: NormalizedWorkbookIR,
    source_file: str,
) -> str:
    """Retorna o texto-fonte Python completo do módulo replay."""
    excluded_nodes = {p.node_id for p in fmap.patterns if p.pattern_class in _EXCLUDED}

    static_values: dict[str, object] = {}
    formulas: dict[str, str] = {}
    sheet_of: dict[str, str] = {}

    for sheet in norm_ir.sheets:
        for cell in sheet.cells:
            node_id = f"{sheet.name}!{cell.coordinate}"
            sheet_of[node_id] = sheet.name
            if node_id in excluded_nodes:
                continue
            if cell.formula_raw:
                formulas[node_id] = cell.formula_raw
            else:
                static_values[node_id] = cell.value_static

    topo_order = [nid for nid in dag.topological_order if nid not in excluded_nodes]

    lines = [
        '"""',
        f"Módulo gerado automaticamente pelo EXRS — reproduz {source_file} sem Excel.",
        "Motor de fórmulas vendorizado em _exrs_formula_engine.py / _exrs_range_utils.py",
        "(cópia exata dos módulos já validados pela Fase A4 do EXRS).",
        '"""',
        "from _exrs_formula_engine import evaluate_formula",
        "from _exrs_range_utils import expand_range",
        "",
        f"STATIC_VALUES = {static_values!r}",
        "",
        f"FORMULAS = {formulas!r}",
        "",
        f"SHEET_OF = {sheet_of!r}",
        "",
        f"TOPOLOGICAL_ORDER = {topo_order!r}",
        "",
        "",
        "def compute(overrides: dict | None = None) -> dict:",
        '    """Recalcula todas as células na ordem topológica. `overrides` permite',
        '    substituir valores de entrada, ex: compute({"Sheet1!A1": 42})."""',
        "    state = dict(STATIC_VALUES)",
        "    if overrides:",
        "        state.update(overrides)",
        "    for node_id in TOPOLOGICAL_ORDER:",
        "        if node_id in state:",
        "            continue",
        "        formula = FORMULAS.get(node_id)",
        "        if formula is None:",
        "            continue",
        "        state[node_id] = evaluate_formula(formula, state, SHEET_OF[node_id], expand_range)",
        "    return state",
        "",
        "",
        'if __name__ == "__main__":',
        "    for _node_id, _value in compute().items():",
        "        print(f\"{_node_id} = {_value!r}\")",
        "",
    ]
    return "\n".join(lines)
```

- [ ] **Step 5: Rodar o teste e confirmar sucesso**

Run: `.venv/Scripts/python.exe -m pytest tests/test_codegen.py -v`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add src/cli/__init__.py src/cli/codegen.py tests/test_codegen.py
git commit -m "feat(cli): codegen do módulo Python replay (sem LLM, sem Excel)"
```

---

### Task 2: Montagem da pasta de saída limpa (`output.py`)

**Files:**
- Create: `src/cli/output.py`
- Test: `tests/test_cli_output.py`

**Interfaces:**
- Consumes: `render_replay_module` (Task 1, `src/cli/codegen.py`), `generate_html_report(results: list[ValidationResult], output_path: Path, fmap: FormulaRegistryMap | None = None, source_file: str = "", title: str = "EXRS — Relatório de Paridade") -> Path` (`libs/trustware/html_reporter.py:429`, já existente e testado), `StorageManager` (`src/orchestrator/storage_manager.py`, campo `output_dir: Path`, método `write_artifact`), `CertifiedModule` (campo `validation_report: MismatchReport`, `MismatchReport.results: list[ValidationResult]`).
- Produces: `write_clean_output(job_output_dir: Path, stem: str, certified, dag, fmap, norm_ir, dest_dir: Path, debug: bool = False) -> Path` — monta `dest_dir` e retorna seu `Path`. Usado por `main.py` (Task 3) e `web_app.py` (Task 4).

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_cli_output.py`:

```python
"""Testes de src/cli/output.py — montagem da pasta de saída limpa."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline_contracts import (
    CertifiedModule, DAGEdge, DAGNode, DomainModule, ExecutionDAG,
    FormulaPattern, FormulaRegistryMap, MismatchReport, NormalizedCell,
    NormalizedSheet, NormalizedWorkbookIR, PatternClass, ValidationResult,
)
from cli.output import write_clean_output


def _fixture(job_dir: Path):
    dag = ExecutionDAG(
        nodes=[DAGNode(id="Sheet1!A1", sheet="Sheet1", coordinate="A1", dependencies=[])],
        edges=[], topological_order=["Sheet1!A1"],
    )
    fmap = FormulaRegistryMap(file_path="p.xlsx", patterns=[], registry_used=[])
    norm_ir = NormalizedWorkbookIR(
        file_path="p.xlsx",
        sheets=[NormalizedSheet(name="Sheet1", index=0, state="visible", cells=[
            NormalizedCell(coordinate="A1", value_static=1, data_type="n"),
        ])],
    )
    result = ValidationResult(node_id="Sheet1!A1", expected_value=1, actual_value=1, passed=True, status="PASSED")
    report = MismatchReport(total_nodes=1, passed=1, failed=0, results=[result])
    domain = DomainModule(file_path="p.xlsx", imports=[], functions=[], generated_at="t")
    certified = CertifiedModule(
        original_file="p.xlsx", domain_module=domain, validation_report=report,
        certification_status="PASSED", certified_at="t",
    )
    # Simula os JSONs técnicos que StorageManager já teria escrito.
    (job_dir / "p_a2_dag.json").write_text(dag.model_dump_json(), encoding="utf-8")
    (job_dir / "p_a25_fmap.json").write_text(fmap.model_dump_json(), encoding="utf-8")
    return certified, dag, fmap, norm_ir


def test_clean_output_default_has_only_py_and_html(tmp_path):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    dest = tmp_path / "p_output"
    certified, dag, fmap, norm_ir = _fixture(job_dir)

    write_clean_output(job_dir, "p", certified, dag, fmap, norm_ir, dest, debug=False)

    names = {f.name for f in dest.iterdir()}
    assert "p.py" in names
    assert "p_report.html" in names
    assert "_exrs_formula_engine.py" in names
    assert "_exrs_range_utils.py" in names
    assert not any(n.endswith(".json") for n in names)  # limpo por padrão


def test_clean_output_debug_keeps_json_artifacts(tmp_path):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    dest = tmp_path / "p_output"
    certified, dag, fmap, norm_ir = _fixture(job_dir)

    write_clean_output(job_dir, "p", certified, dag, fmap, norm_ir, dest, debug=True)

    names = {f.name for f in dest.iterdir()}
    assert "p_a2_dag.json" in names
    assert "p_a25_fmap.json" in names


def test_generated_py_is_syntactically_valid(tmp_path):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    dest = tmp_path / "p_output"
    certified, dag, fmap, norm_ir = _fixture(job_dir)

    write_clean_output(job_dir, "p", certified, dag, fmap, norm_ir, dest, debug=False)

    source = (dest / "p.py").read_text(encoding="utf-8")
    compile(source, "<generated>", "exec")
```

- [ ] **Step 2: Rodar o teste e confirmar falha**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli_output.py -v`
Expected: `ModuleNotFoundError: No module named 'cli.output'`

- [ ] **Step 3: Implementar `src/cli/output.py`**

```python
"""
EXRS CLI — Montagem da pasta de saída limpa.

Por padrão entrega só o .py (+ engine vendorizado) e o relatório .html — os JSONs técnicos
por fase continuam existindo em job_output_dir (nada se perde do rastro determinístico),
mas só são copiados para a pasta final de entrega quando debug=True.
"""
import shutil
from pathlib import Path

from html_reporter import generate_html_report

from cli.codegen import render_replay_module

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FORMULA_ENGINE_SRC = _REPO_ROOT / "src" / "phase_a4" / "formula_evaluator.py"
_RANGE_UTILS_SRC = _REPO_ROOT / "src" / "phase_a1_5" / "normalizer.py"


def write_clean_output(
    job_output_dir: Path,
    stem: str,
    certified,
    dag,
    fmap,
    norm_ir,
    dest_dir: Path,
    debug: bool = False,
) -> Path:
    """Monta dest_dir com o .py replay + engine vendorizado + relatório .html.
    Se debug=True, também copia os JSONs técnicos de job_output_dir para dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    source = render_replay_module(dag, fmap, norm_ir, source_file=f"{stem}.xlsx")
    (dest_dir / f"{stem}.py").write_text(source, encoding="utf-8")

    shutil.copy2(_FORMULA_ENGINE_SRC, dest_dir / "_exrs_formula_engine.py")
    shutil.copy2(_RANGE_UTILS_SRC, dest_dir / "_exrs_range_utils.py")

    generate_html_report(
        certified.validation_report.results,
        dest_dir / f"{stem}_report.html",
        fmap=fmap,
        source_file=f"{stem}.xlsx",
        title=f"EXRS — Relatório de {stem}",
    )

    if debug:
        for json_file in job_output_dir.glob(f"{stem}_*.json"):
            shutil.copy2(json_file, dest_dir / json_file.name)

    return dest_dir
```

- [ ] **Step 4: Rodar o teste e confirmar sucesso**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli_output.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/cli/output.py tests/test_cli_output.py
git commit -m "feat(cli): monta pasta de saída limpa (.py + relatório html, JSONs opcionais)"
```

---

### Task 3: Entry point CLI (`exrs compile`) + empacotamento `pip`

**Files:**
- Create: `src/cli/main.py`
- Modify: `pyproject.toml`
- Test: `tests/test_cli_compile.py`

**Interfaces:**
- Consumes: `orchestrate_pipeline(xlsx_path: Path, storage: StorageManager, skip_llm: bool = True) -> dict` (`src/orchestrator/pipeline_orchestrator.py:45`, retorna `{"status": str, "certified": CertifiedModule | None}` no caminho normal), `StorageManager(job_id: str, output_base_dir: str | Path | None = None)` (`src/orchestrator/storage_manager.py:7`, atributo `output_dir: Path`), `write_clean_output` (Task 2).
- Produces: `main(argv: list[str] | None = None) -> int` — entry point; exit code 0 sucesso, 1 erro de pipeline, 2 uso incorreto. `run_compile_cli(xlsx_path: Path, dest_dir: Path | None, debug: bool, chat: bool) -> int` — lógica reaproveitável por testes e pela UI web (Task 4).

- [ ] **Step 1: Adicionar `[project.scripts]` ao `pyproject.toml`**

No arquivo `pyproject.toml`, após o bloco `[build-system]`, adicionar:

```toml
[project.scripts]
exrs = "cli.main:main"
```

- [ ] **Step 2: Escrever o teste que falha**

Criar `tests/test_cli_compile.py`:

```python
"""Testes de src/cli/main.py — comando `exrs compile`."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"


def test_compile_produces_clean_output_by_default(tmp_path, monkeypatch):
    from cli.main import main

    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    dest = tmp_path / "coverage_test_output"

    exit_code = main(["compile", str(FIXTURE), "--out", str(dest)])

    assert exit_code == 0
    names = {f.name for f in dest.iterdir()}
    assert "coverage_test.py" in names
    assert "coverage_test_report.html" in names
    assert not any(n.endswith(".json") for n in names)


def test_compile_debug_keeps_json_artifacts(tmp_path, monkeypatch):
    from cli.main import main

    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    dest = tmp_path / "coverage_test_output"

    exit_code = main(["compile", str(FIXTURE), "--out", str(dest), "--debug"])

    assert exit_code == 0
    names = {f.name for f in dest.iterdir()}
    assert any(n.endswith(".json") for n in names)


def test_compile_missing_file_returns_error(tmp_path, monkeypatch):
    from cli.main import main

    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    exit_code = main(["compile", str(tmp_path / "nao_existe.xlsx")])
    assert exit_code == 1


def test_compile_no_args_returns_usage_error():
    from cli.main import main

    exit_code = main(["compile"])
    assert exit_code == 2
```

- [ ] **Step 3: Rodar o teste e confirmar falha**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli_compile.py -v`
Expected: `ModuleNotFoundError: No module named 'cli.main'`

- [ ] **Step 4: Implementar `src/cli/main.py`**

```python
"""
EXRS CLI — entry point `exrs`.

`exrs compile <arquivo.xlsx>` roda a Trilha A (A0→A4) local, sem servidor, sem
Celery/Redis, e monta uma pasta de saída limpa com o .py replay + relatório .html.
`exrs ui` sobe uma interface web local (ver src/cli/web_app.py, Task 4).
"""
import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (
    _REPO_ROOT / "libs" / "trustware", _REPO_ROOT / "src" / "orchestrator",
    _REPO_ROOT / "src" / "phase_a0", _REPO_ROOT / "src" / "phase_a1",
    _REPO_ROOT / "src" / "phase_a1_5", _REPO_ROOT / "src" / "phase_a2",
    _REPO_ROOT / "src" / "phase_a2_5", _REPO_ROOT / "src" / "phase_a3",
    _REPO_ROOT / "src" / "phase_a4",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipeline_contracts import ExecutionDAG, FormulaRegistryMap, NormalizedWorkbookIR
from storage_manager import StorageManager
from pipeline_orchestrator import orchestrate_pipeline

from cli.output import write_clean_output


def run_compile_cli(xlsx_path: Path, dest_dir: Path | None, debug: bool, chat: bool) -> int:
    if not xlsx_path.exists():
        print(f"Erro: arquivo não encontrado: {xlsx_path}", file=sys.stderr)
        return 1

    stem = xlsx_path.stem
    storage = StorageManager(job_id=stem)
    result = orchestrate_pipeline(xlsx_path, storage, skip_llm=not chat)

    status = result.get("status")
    if status in {"ESCALATED", "NOT_IMPLEMENTED", "SKIPPED_NO_CACHE", "GATE_REJECTED"}:
        print(f"[EXRS] Não foi possível gerar código: {status}", file=sys.stderr)
        reason = result.get("reason")
        if reason:
            print(f"       Motivo: {reason}", file=sys.stderr)
        return 1

    certified = result.get("certified")
    if certified is None:
        print("[EXRS] Erro interno: pipeline concluiu sem CertifiedModule.", file=sys.stderr)
        return 1

    dag = ExecutionDAG.model_validate_json(
        (storage.output_dir / f"{stem}_a2_dag.json").read_text(encoding="utf-8")
    )
    fmap = FormulaRegistryMap.model_validate_json(
        (storage.output_dir / f"{stem}_a25_fmap.json").read_text(encoding="utf-8")
    )
    norm_ir = NormalizedWorkbookIR.model_validate_json(
        (storage.output_dir / f"{stem}_a15_norm.json").read_text(encoding="utf-8")
    )

    dest = dest_dir or Path.cwd() / f"{stem}_output"
    write_clean_output(storage.output_dir, stem, certified, dag, fmap, norm_ir, dest, debug=debug)

    print(f"[EXRS] Status: {status}")
    print(f"[EXRS] Saída: {dest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="exrs", description="EXRS — Reversão de planilhas Excel para Python")
    sub = parser.add_subparsers(dest="command")

    compile_parser = sub.add_parser("compile", help="Reverte uma planilha .xlsx em código Python")
    compile_parser.add_argument("xlsx", nargs="?", type=Path, help="Caminho para o arquivo .xlsx")
    compile_parser.add_argument("--out", type=Path, default=None, help="Pasta de saída (padrão: ./<nome>_output)")
    compile_parser.add_argument("--debug", action="store_true", help="Mantém os JSONs técnicos por fase na saída")
    compile_parser.add_argument("--chat", action="store_true", help="Ativa captura de intenção via LLM (Trilha B)")

    sub.add_parser("ui", help="Abre a interface web local")

    args = parser.parse_args(argv)

    if args.command == "compile":
        if args.xlsx is None:
            compile_parser.print_usage(sys.stderr)
            return 2
        return run_compile_cli(args.xlsx, args.out, args.debug, args.chat)

    if args.command == "ui":
        from cli.web_app import serve
        serve()
        return 0

    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 5: Rodar o teste e confirmar sucesso**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli_compile.py -v`
Expected: `4 passed`

- [ ] **Step 6: Reinstalar o pacote editável e confirmar o entry point `exrs`**

Run: `uv sync && exrs compile tests/fixtures/coverage_test.xlsx --out C:/Users/rodri/AppData/Local/Temp/claude/C--Projetos-Aurora-AuroraControler/d72cd26f-be87-44c5-ac3d-b23cc3886afb/scratchpad/exrs_smoke_output`
Expected: exit 0, saída no diretório indicado com `coverage_test.py` e `coverage_test_report.html`

- [ ] **Step 7: Commit**

```bash
git add src/cli/main.py pyproject.toml tests/test_cli_compile.py
git commit -m "feat(cli): entry point 'exrs compile' + empacotamento pip"
```

---

### Task 4: Interface web local (`exrs ui`)

**Files:**
- Create: `src/cli/web_app.py`
- Test: `tests/test_cli_ui.py`

**Interfaces:**
- Consumes: `run_compile_cli` (Task 3, `src/cli/main.py`) — reaproveitado internamente para não duplicar a lógica de orquestração.
- Produces: `create_app() -> FastAPI` — usado pelos testes via `TestClient`. `serve(port: int = 8765) -> None` — sobe `uvicorn` e abre o navegador; usado por `main.py` (Task 3, comando `ui`).

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_cli_ui.py`:

```python
"""Testes de src/cli/web_app.py — interface web local."""
import io
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "libs" / "trustware"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "coverage_test.xlsx"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EXRS_DATA_DIR", str(tmp_path / "internal"))
    from fastapi.testclient import TestClient
    from cli.web_app import create_app
    return TestClient(create_app())


def test_upload_page_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_upload_and_poll_reaches_done(client):
    with open(FIXTURE, "rb") as fh:
        resp = client.post("/upload", files={"file": ("coverage_test.xlsx", fh, "application/octet-stream")})
    assert resp.status_code == 200
    token = resp.json()["token"]

    deadline = time.time() + 30
    status = None
    while time.time() < deadline:
        status_resp = client.get(f"/status/{token}")
        assert status_resp.status_code == 200
        status = status_resp.json()["status"]
        if status in {"DONE", "ERROR"}:
            break
        time.sleep(0.2)

    assert status == "DONE"


def test_result_page_serves_report_and_download_links(client):
    with open(FIXTURE, "rb") as fh:
        resp = client.post("/upload", files={"file": ("coverage_test.xlsx", fh, "application/octet-stream")})
    token = resp.json()["token"]

    deadline = time.time() + 30
    while time.time() < deadline:
        if client.get(f"/status/{token}").json()["status"] in {"DONE", "ERROR"}:
            break
        time.sleep(0.2)

    result_resp = client.get(f"/result/{token}")
    assert result_resp.status_code == 200
    assert "coverage_test.py" in result_resp.text
    assert "coverage_test_report.html" in result_resp.text


def test_unknown_token_returns_404(client):
    resp = client.get("/status/token-que-nao-existe")
    assert resp.status_code == 404
```

- [ ] **Step 2: Rodar o teste e confirmar falha**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli_ui.py -v`
Expected: `ModuleNotFoundError: No module named 'cli.web_app'`

- [ ] **Step 3: Implementar `src/cli/web_app.py`**

```python
"""
EXRS CLI — Interface web local (`exrs ui`).

Servidor FastAPI 100% local, sem Celery/Redis: execução em BackgroundTasks, status em
memória (dict). Adequado a uso single-user local — não é a infraestrutura multi-tenant
do SaaS (OS-EXRS-SAAS), que continua existindo separadamente em src/api/main.py.
"""
import shutil
import tempfile
import uuid
import webbrowser
from pathlib import Path
from threading import Lock

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse

from cli.main import run_compile_cli

_JOBS: dict[str, dict] = {}
_LOCK = Lock()


def _process(token: str, xlsx_path: Path, dest_dir: Path) -> None:
    try:
        exit_code = run_compile_cli(xlsx_path, dest_dir, debug=False, chat=False)
        with _LOCK:
            _JOBS[token]["status"] = "DONE" if exit_code == 0 else "ERROR"
    except Exception as e:  # noqa: BLE001 — status do job NUNCA é silencioso
        with _LOCK:
            _JOBS[token]["status"] = "ERROR"
            _JOBS[token]["detail"] = str(e)


def create_app() -> FastAPI:
    app = FastAPI(title="EXRS — Interface Local")

    @app.get("/", response_class=HTMLResponse)
    async def upload_page():
        return (
            "<html><body>"
            "<h1>EXRS — Reversão de Planilhas</h1>"
            "<form action='/upload' method='post' enctype='multipart/form-data'>"
            "<input type='file' name='file' accept='.xlsx'>"
            "<button type='submit'>Processar</button>"
            "</form></body></html>"
        )

    @app.post("/upload")
    async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
        token = uuid.uuid4().hex
        work_dir = Path(tempfile.mkdtemp(prefix=f"exrs_ui_{token}_"))
        xlsx_path = work_dir / file.filename
        xlsx_path.write_bytes(await file.read())
        dest_dir = work_dir / "output"

        with _LOCK:
            _JOBS[token] = {"status": "RUNNING", "dest_dir": dest_dir}

        background_tasks.add_task(_process, token, xlsx_path, dest_dir)
        return {"token": token}

    @app.get("/status/{token}")
    async def status(token: str):
        with _LOCK:
            job = _JOBS.get(token)
        if job is None:
            raise HTTPException(status_code=404, detail="job não encontrado")
        return {"status": job["status"]}

    @app.get("/result/{token}", response_class=HTMLResponse)
    async def result(token: str):
        with _LOCK:
            job = _JOBS.get(token)
        if job is None:
            raise HTTPException(status_code=404, detail="job não encontrado")
        if job["status"] != "DONE":
            raise HTTPException(status_code=409, detail=f"job ainda não concluído: {job['status']}")
        dest_dir: Path = job["dest_dir"]
        files = sorted(f.name for f in dest_dir.iterdir())
        links = "".join(f"<li>{name}</li>" for name in files)
        return f"<html><body><h1>Resultado</h1><ul>{links}</ul></body></html>"

    return app


def serve(port: int = 8765) -> None:
    import uvicorn

    url = f"http://127.0.0.1:{port}"
    webbrowser.open(url)
    uvicorn.run(create_app(), host="127.0.0.1", port=port)
```

- [ ] **Step 4: Rodar o teste e confirmar sucesso**

Run: `.venv/Scripts/python.exe -m pytest tests/test_cli_ui.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/cli/web_app.py tests/test_cli_ui.py
git commit -m "feat(cli): interface web local (exrs ui) via FastAPI"
```

---

### Task 5: Mensagem de erro acionável quando Docker está indisponível

**Files:**
- Modify: `src/phase_a4/runner.py` (ponto onde `SANDBOX_UNAVAILABLE` é gerado — usar `Grep` para localizar antes de editar, já que a lacuna exata não foi mapeada linha a linha nesta sessão)
- Test: `tests/test_sandbox_error_message.py`

**Interfaces:**
- Consumes: comportamento existente de `_docker_available()` (`src/phase_a4/runner.py:116`) e do sentinela `RUNTIME_ERROR: SANDBOX_UNAVAILABLE` já emitido por `execute_in_sandbox`.
- Produces: nenhuma nova função pública — apenas melhora a mensagem já existente para incluir instrução acionável.

- [ ] **Step 1: Localizar o texto exato do sentinela atual**

Run: `grep -n "SANDBOX_UNAVAILABLE" src/phase_a4/runner.py`

- [ ] **Step 2: Escrever o teste que falha**

Criar `tests/test_sandbox_error_message.py`:

```python
"""Verifica que a mensagem de Docker indisponível é acionável (não só um sentinela técnico)."""
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src" / "phase_a4"))

from runner import execute_in_sandbox


def test_docker_unavailable_message_is_actionable():
    with patch("runner._docker_available", return_value=False):
        result = execute_in_sandbox("def f(): return 1", "f", {})
    assert "docker.com" in result.lower() or "docker desktop" in result.lower()
```

- [ ] **Step 3: Rodar o teste e confirmar falha**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sandbox_error_message.py -v`
Expected: `AssertionError` (mensagem atual não contém instrução de instalação)

- [ ] **Step 4: Editar a mensagem em `src/phase_a4/runner.py`**

Localizar a linha onde `execute_in_sandbox` retorna o sentinela `RUNTIME_ERROR: SANDBOX_UNAVAILABLE` quando `_docker_available()` é `False`, e adicionar a instrução ao texto retornado (formato exato depende do código encontrado no Step 1 — anexar `" Instale Docker Desktop: https://www.docker.com/products/docker-desktop/"` à string do sentinela existente, preservando o prefixo `RUNTIME_ERROR: SANDBOX_UNAVAILABLE` para não quebrar `_ERROR_MARKERS` do `certification_gate.py`).

- [ ] **Step 5: Rodar o teste e confirmar sucesso**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sandbox_error_message.py -v`
Expected: `1 passed`

- [ ] **Step 6: Rodar a suíte completa (regressão)**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q`
Expected: nenhuma falha nova em relação ao baseline (658 passed, 1 skipped antes desta task — Docker pode estar disponível ou não neste host, conferir se os 2 testes históricos de sandbox real ainda se comportam igual)

- [ ] **Step 7: Commit**

```bash
git add src/phase_a4/runner.py tests/test_sandbox_error_message.py
git commit -m "fix(a4): mensagem acionável quando Docker está indisponível"
```

---

### Task 6: README do produto MVP

**Files:**
- Modify: `README.md`

**Interfaces:**
- Nenhuma (documentação).

- [ ] **Step 1: Adicionar seção "Uso rápido (CLI)" ao `README.md`**

Adicionar, após a seção "Setup Rápido" existente:

```markdown
## Uso Rápido (CLI)

Instale o pacote em modo editável e use o comando `exrs`:

\`\`\`bash
uv sync
exrs compile planilha.xlsx
\`\`\`

Isso gera a pasta `planilha_output/` com:
- `planilha.py` — módulo Python que reproduz o cálculo da planilha (sem precisar de Excel nem de LLM)
- `planilha_report.html` — relatório de paridade e cobertura

Flags:
- `--out <pasta>` — customiza o destino da saída (padrão: `./<nome>_output`)
- `--debug` — mantém os JSONs técnicos por fase (rastro de auditoria completo)
- `--chat` — ativa captura de intenção via LLM (requer chave configurada, ver `.env.example`)

Para a interface web local:

\`\`\`bash
exrs ui
\`\`\`

**Requisito:** a Fase A4 (validação) exige Docker Desktop instalado e rodando.
\`\`\`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: seção de uso rápido do CLI exrs no README"
```

---

## Self-Review (registrado)

- **Cobertura da spec:** trilha A (Task 1-3), trilha B opcional `--chat` (Task 3, flag já passa `skip_llm=not chat` para `orchestrate_pipeline`), saída limpa vs `--debug` (Task 2-3), CLI via pip (Task 3), UI web local FastAPI (Task 4), erro de Docker acionável (Task 5), documentação (Task 6). Licenciamento/billing e Trilha C ficaram de fora — coerente com o escopo travado no design.
- **Placeholders:** nenhum "TBD"/"implementar depois" — todo código de cada step está completo e executável.
- **Consistência de tipos:** `render_replay_module(dag, fmap, norm_ir, source_file)` (Task 1) é chamado com a mesma assinatura em `write_clean_output` (Task 2); `write_clean_output(job_output_dir, stem, certified, dag, fmap, norm_ir, dest_dir, debug)` (Task 2) é chamado com a mesma assinatura em `run_compile_cli` (Task 3); `run_compile_cli(xlsx_path, dest_dir, debug, chat)` (Task 3) é reaproveitado por `_process` em `web_app.py` (Task 4) com os mesmos nomes posicionais.

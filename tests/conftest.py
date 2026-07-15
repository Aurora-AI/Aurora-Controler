import os
import subprocess
from pathlib import Path

# Testes rodam o Celery em modo EAGER (execução inline, sem broker externo) — determinístico
# e sem exigir Redis/worker no CI. O fluxo com broker real (ME-6) é validado fora da suíte,
# contra o container `exrs-redis`.
os.environ.setdefault("EXRS_CELERY_EAGER", "1")

def pytest_configure(config):
    """Gera as fixtures binárias (.xlsx) automaticamente antes da coleta de testes —
    todas gitignored (exceto consultoria_real_test.xlsx), então um checkout limpo não
    as tem. Os 3 scripts cobrem toda a superfície de fixtures binárias usada pela
    suíte: coverage_test.xlsx (compilador), sales_history_test.xlsx (audit) e
    otica_test_bom/ruim.xlsx (audit, completude boa/ruim).

    Precisa ser um hook `pytest_configure` (roda ANTES da coleta), não uma fixture
    `autouse` de sessão (roda DEPOIS da coleta, no setup do primeiro teste): a
    parametrização de tests/test_fixtures.py::test_gabarito_match lê coverage_test.xlsx
    diretamente durante a coleta (`_collect_params()`), com uma guarda silenciosa
    (`if not FIXTURE_PATH.exists(): return []`) — sem o arquivo já presente ANTES da
    coleta, esses ~142 casos de teste somem da suíte sem gerar nenhuma falha visível."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    for script_name in (
        "create_test_workbook.py",
        "create_audit_test_workbook.py",
        "create_otica_test_workbook.py",
    ):
        script_path = fixtures_dir / script_name
        if script_path.exists():
            print(f"\n[conftest] Gerando fixture binária: {script_path.name}...")
            subprocess.run(["python", str(script_path)], check=True)

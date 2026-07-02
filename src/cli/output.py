"""
EXRS CLI — Montagem da pasta de saída limpa.

Por padrão entrega só o .py (+ engine vendorizado) e o relatório .html — os JSONs técnicos
por fase continuam existindo em job_output_dir (nada se perde do rastro determinístico),
mas só são copiados para a pasta final de entrega quando debug=True.
"""
import shutil
from pathlib import Path

from phase_a4.html_reporter import generate_html_report

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

import sys
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
for mod_path in [
    REPO_ROOT / "libs" / "trustware",
    REPO_ROOT / "src" / "phase_a0",
    REPO_ROOT / "src" / "phase_a1",
    REPO_ROOT / "src" / "phase_a1_5",
    REPO_ROOT / "src" / "phase_a2",
    REPO_ROOT / "src" / "phase_a2_5",
    REPO_ROOT / "src" / "phase_a3",
    REPO_ROOT / "src" / "phase_a4",
    REPO_ROOT / "src" / "orchestrator",
]:
    p = str(mod_path)
    if p not in sys.path:
        sys.path.insert(0, p)

from storage_manager import StorageManager
from classifier import classify_workbook
from extractor import extract_structure
from normalizer import normalize_workbook
from graph_builder import build_dag
from pattern_registry import classify_workbook as classify_patterns, build_registry
from gabarito_extractor import extract_gabarito
from runner import validate_workbook
from repair_orchestrator import identify_repair_candidates
from pipeline_contracts import CertifiedModule, CompileDecision, DomainModule, WorkbookClass
from certification_gate import verify_certification, CertificationGateError
from factory_events import trace, set_job

class UnsupportedInAsyncMode(Exception):
    pass

def route(workbook_class: WorkbookClass, compile_decision: CompileDecision, filepath: Path) -> str:
    if compile_decision == CompileDecision.ESCALATE or workbook_class == WorkbookClass.UNSUPPORTED:
        return "escalate"
    if filepath.suffix.lower() == ".csv":
        return "track_c"
    return "track_a"

def orchestrate_pipeline(xlsx_path: Path, storage: StorageManager, skip_llm: bool = True):
    stem = xlsx_path.stem
    jid = storage.job_id
    set_job(jid)  # correlaciona eventos do fundo da cadeia (ex.: sandbox A4) a este job

    # A0
    report = classify_workbook(xlsx_path)
    storage.write_artifact(stem, "a0_report", report)
    trace(jid, "a0_classify", workbook_class=report.workbook_class.value)

    track = route(report.workbook_class, report.compile_decision, xlsx_path)
    trace(jid, "route", track=track)

    if track == "escalate":
        trace(jid, "terminal", status="ESCALATED")
        return {"status": "ESCALATED", "reason": report.escalate_reasons}

    if track == "track_c":
        # C0-C3 (engine de dashboard) ainda não integrado ao orquestrador unificado.
        # Production First / Zero Dívida Técnica: NUNCA reportar PASSED para trabalho não
        # executado — declarar explicitamente o estado não-implementado.
        trace(jid, "terminal", status="NOT_IMPLEMENTED", track="track_c")
        return {"status": "NOT_IMPLEMENTED", "track": "track_c",
                "reason": "Integração C0→C3 pendente (ver OS-EXRS-SAAS ME futura)."}

    # track_a = A1 -> A4
    raw_ir = extract_structure(xlsx_path)
    storage.write_artifact(stem, "a1_ir", raw_ir)
    trace(jid, "a1_extract")

    # A1.5
    norm_ir = normalize_workbook(raw_ir)
    storage.write_artifact(stem, "a15_norm", norm_ir)
    trace(jid, "a15_normalize")

    # A2
    dag = build_dag(norm_ir)
    storage.write_artifact(stem, "a2_dag", dag)
    trace(jid, "a2_dag", nodes=len(dag.nodes))

    # A2.5
    fmap = classify_patterns(norm_ir, build_registry())
    storage.write_artifact(stem, "a25_fmap", fmap)
    trace(jid, "a25_patterns")

    # A3
    counts = {}
    for p in fmap.patterns:
        counts[p.pattern_class.value] = counts.get(p.pattern_class.value, 0) + 1
    unresolved_count = counts.get("unresolved", 0)

    if unresolved_count == 0 or skip_llm:
        domain = DomainModule(
            file_path=str(xlsx_path),
            imports=[],
            functions=[],
            generated_at=datetime.now().isoformat(),
            translation_metadata={"total_unresolved": unresolved_count, "total_functions": 0}
        )
    else:
        from translator import translate_workbook
        domain = translate_workbook(norm_ir, fmap)

    storage.write_artifact(stem, "a3_domain", domain)
    trace(jid, "a3_translate", functions=len(domain.functions))

    # A4
    gabarito, missing_cache = extract_gabarito(xlsx_path)
    if not gabarito:
        trace(jid, "terminal", status="SKIPPED_NO_CACHE")
        return {"status": "SKIPPED_NO_CACHE", "certified": None, "domain": domain}

    results = validate_workbook(dag, domain, fmap, norm_ir, gabarito, missing_cache)
    passed = [r for r in results if r.passed]
    skipped = [r for r in results if r.status == "SKIPPED_NO_CACHE"]
    evaluated = len(results) - len(skipped)
    parity = len(passed) / evaluated if evaluated > 0 else 1.0

    validation_report = identify_repair_candidates(results, fmap)
    status = "PASSED" if parity >= 1.0 else ("PARTIAL" if parity > 0 else "FAILED")
    
    certified = CertifiedModule(
        original_file=xlsx_path.name,
        domain_module=domain,
        validation_report=validation_report,
        certification_status=status,
        certified_at=datetime.now().isoformat(),
    )
    # Trustware gate determinístico (não-LLM): selo fraudulento NÃO é persistido.
    try:
        verify_certification(certified)
    except CertificationGateError as e:
        trace(jid, "trustware_gate", status="GATE_REJECTED", reason=str(e))
        return {"status": "GATE_REJECTED", "reason": str(e), "certified": None}

    storage.write_artifact(stem, "a4_certified", certified)
    trace(jid, "terminal", status=status, parity=parity)

    return {"status": status, "certified": certified}

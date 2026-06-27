"""
EXRS Trustware — Certification Gate (Fase A4)

Gate determinístico NÃO-LLM que valida a integridade de um CertifiedModule antes da
persistência. Princípio Trustware (CLAUDE.md): nenhuma mutação de estado crítico — aqui, a
gravação de um selo de certificação — acontece sem um gate determinístico independente.

O gate NÃO confia no campo `certification_status` reportado: ele recomputa a verdade a partir
dos `validation_report.results` e rejeita selos inconsistentes. Isso impede que um status
"PASSED" seja persistido sobre resultados que contêm falhas ou sentinelas de erro.
"""
import math

from pipeline_contracts import CertifiedModule

# Sentinelas de erro que JAMAIS podem aparecer em um nó marcado como passed=True.
_ERROR_MARKERS = ("RUNTIME_ERROR", "#ERROR!", "#EXT!", "SANDBOX_UNAVAILABLE", "ERROR:")


class CertificationGateError(Exception):
    """Levantada quando o selo de certificação é inconsistente com a evidência real."""


def _contains_error_marker(value) -> bool:
    """Detecta sentinela de erro recursivamente — não só em str escalar (dict/list/tuple)."""
    if isinstance(value, str):
        return any(m in value for m in _ERROR_MARKERS)
    if isinstance(value, dict):
        return any(_contains_error_marker(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_error_marker(v) for v in value)
    return False


def _recompute_pass(expected, actual) -> bool:
    """
    Recomputa pass/fail a partir dos VALORES, espelhando a comparação de validate_workbook
    (numérico → math.isclose; senão → igualdade textual). É isto que torna o gate uma
    SEGUNDA fonte de verdade, independente do booleano `passed` que o executor gravou.
    """
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(actual, expected, rel_tol=1e-7)
    return str(actual) == str(expected)


def _expected_status(parity: float) -> str:
    if parity >= 1.0:
        return "PASSED"
    if parity > 0.0:
        return "PARTIAL"
    return "FAILED"


def verify_certification(certified: CertifiedModule) -> None:
    """
    Valida deterministicamente a integridade do selo. Levanta CertificationGateError em
    qualquer inconsistência. Retorna None silenciosamente quando o selo é íntegro.
    """
    results = certified.validation_report.results

    # Nós efetivamente avaliados (cache ausente não conta para paridade).
    evaluated = [r for r in results if r.status != "SKIPPED_NO_CACHE"]
    passed = [r for r in evaluated if r.passed]
    failed = [r for r in evaluated if not r.passed]
    parity = (len(passed) / len(evaluated)) if evaluated else 1.0

    # 1. Consistência entre status declarado e paridade real recomputada.
    expected = _expected_status(parity)
    if certified.certification_status != expected:
        raise CertificationGateError(
            f"Status '{certified.certification_status}' inconsistente com a paridade real "
            f"{parity:.4f} ({len(passed)}/{len(evaluated)} aprovados) — esperado '{expected}'."
        )

    # 2. Um selo PASSED não pode coexistir com qualquer nó falho.
    if certified.certification_status == "PASSED" and failed:
        raise CertificationGateError(
            f"Selo PASSED com {len(failed)} nó(s) falho(s): "
            f"{[r.node_id for r in failed[:5]]}"
        )

    # 3. Recompute independente: o booleano `passed` do executor deve bater com os VALORES.
    #    Fecha o gap Byzantino — o gate não herda a confiança no cálculo de pass/fail.
    for r in evaluated:
        if r.passed != _recompute_pass(r.expected_value, r.actual_value):
            raise CertificationGateError(
                f"Nó '{r.node_id}': flag passed={r.passed} inconsistente com os valores "
                f"(expected={r.expected_value!r}, actual={r.actual_value!r})."
            )

    # 4. Nenhum nó marcado passed=True pode carregar sentinela de erro (recursivo).
    for r in passed:
        if _contains_error_marker(r.actual_value):
            raise CertificationGateError(
                f"Nó '{r.node_id}' marcado passed=True contém sentinela de erro: "
                f"{r.actual_value!r}"
            )

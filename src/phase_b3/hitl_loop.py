"""Phase B3 — HITL loop interativo.

Exibe resultados de simulacao, captura overrides do usuario
e grava entrada de auditoria por cada intervencao.
"""
from __future__ import annotations

import uuid
from typing import Any

from pipeline_contracts import SimulationAudit, StagedRuleGraph
from simulation_engine import make_step, run_simulation

# Tokens que encerram o loop
_DONE_TOKENS = {"", "ok", "done", "confirmar", "pronto", "sair", "exit", "quit"}


def _print_step(step, graph: StagedRuleGraph) -> None:
    """Exibe resumo de uma rodada de simulacao."""
    node_labels = {n.id: n.label for n in graph.nodes}
    print(f"\n=== Rodada {step.run_number} ===")
    print("  Entradas:")
    for nid, val in step.input_values.items():
        print(f"    {node_labels.get(nid, nid)}: {val}")
    print("  Saidas:")
    for nid, val in step.output_values.items():
        label = node_labels.get(nid, nid)
        suffix = " (nao avaliado)" if nid in step.unevaluated_nodes else ""
        print(f"    {label}: {val}{suffix}")
    if step.unevaluated_nodes:
        print(f"  [{len(step.unevaluated_nodes)} formula(s) complexa(s) mantida(s) do Excel]")


def _ask_overrides(graph: StagedRuleGraph, current_values: dict[str, Any]) -> dict[str, Any] | None:
    """Solicita um override de input ao usuario.

    Returns:
        {nid: val} com exatamente um override quando o usuario fornece uma entrada valida.
        None quando o usuario digita um done-token para encerrar.
    """
    input_ids = {n.id for n in graph.nodes if n.is_user_input}
    node_labels = {n.id: n.label for n in graph.nodes}
    print("\nDigite um override (ex: S!A1=100) ou ENTER para encerrar:")

    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            return None
        if raw.lower() in _DONE_TOKENS:
            return None
        if "=" not in raw:
            print("  Formato invalido. Use: NODE_ID=valor (ex: S!A1=50.0)")
            continue
        parts = raw.split("=", 1)
        nid, val_str = parts[0].strip(), parts[1].strip()
        if nid not in input_ids:
            valid = ", ".join(f"{n} ({node_labels.get(n, n)})" for n in input_ids)
            print(f"  '{nid}' nao e um no de entrada. Validos: {valid}")
            continue
        try:
            val: Any = float(val_str)
        except ValueError:
            val = val_str  # accept string values (e.g. categories, dates)
        print(f"  Registrado: {node_labels.get(nid, nid)} = {val}")
        return {nid: val}


def run_hitl(graph: StagedRuleGraph) -> SimulationAudit:
    """Executa o loop HITL ate o usuario encerrar.

    Returns:
        SimulationAudit com todos os steps e intervencoes.
    """
    simulation_id = str(uuid.uuid4())
    node_map = {n.id: n for n in graph.nodes}
    current_values: dict[str, Any] = {n.id: n.current_value for n in graph.nodes}
    steps = []
    interventions: list[dict] = []
    run_number = 1

    pending_overrides: dict[str, Any] = {}

    while True:
        new_values, unevaluated = run_simulation(graph, pending_overrides)
        current_values.update(new_values)

        step = make_step(run_number, pending_overrides, current_values, unevaluated, graph)
        steps.append(step)
        _print_step(step, graph)
        pending_overrides = {}

        overrides = _ask_overrides(graph, current_values)
        if overrides is None:
            break

        # Gravar entrada de auditoria por intervencao
        for nid, new_val in overrides.items():
            old_val = current_values.get(nid, node_map[nid].current_value)
            interventions.append({
                "node_id": nid,
                "old_value": old_val,
                "new_value": new_val,
                "reason": "HITL override by user",
            })

        current_values.update(overrides)
        pending_overrides = overrides
        run_number += 1

    # Calcular outcome final a partir dos outputs
    output_nodes = [n for n in graph.nodes if n.is_user_output]
    outcome_parts = [
        f"{n.label}={current_values.get(n.id, n.current_value)}"
        for n in output_nodes
    ]
    final_outcome = "; ".join(outcome_parts) if outcome_parts else "Simulacao concluida"

    return SimulationAudit(
        simulation_id=simulation_id,
        steps=steps,
        hitl_interventions=interventions,
        final_outcome=final_outcome,
    )

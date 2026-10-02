"""
EXRS Phase A2 — Graph Builder
Constrói ExecutionDAG a partir do NormalizedWorkbookIR.
Determinístico. Sem LLM.
"""
import sys
from pathlib import Path
from collections import deque

# Setup path for pipeline_contracts


from libs.trustware.pipeline_contracts import (
    NormalizedWorkbookIR, NormalizedSheet, NormalizedCell,
    ExecutionDAG, DAGNode, DAGEdge, CycleInfo, CycleType
)

# Constantes para DFS
WHITE = 0  # não visitado
GRAY = 1   # em exploração
BLACK = 2  # finalizado

def make_node_id(sheet: str, coordinate: str) -> str:
    """Cria identificador canônico para um nó."""
    return f"{sheet}!{coordinate}"

def build_dag(normalized_ir: NormalizedWorkbookIR) -> ExecutionDAG:
    """
    Constrói o grafo de dependências a partir do IR normalizado.
    """
    nodes: list[DAGNode] = []
    edges: list[DAGEdge] = []
    seen_nodes: set[str] = set()
    
    # 1. Mapear todos os nós explícitos no IR
    for sheet in normalized_ir.sheets:
        for cell in sheet.cells:
            node_id = make_node_id(sheet.name, cell.coordinate)
            if node_id in seen_nodes:
                continue
            seen_nodes.add(node_id)
            
            nodes.append(DAGNode(
                id=node_id,
                sheet=sheet.name,
                coordinate=cell.coordinate,
                formula_raw=cell.formula_raw,
                data_type=cell.data_type
            ))
            
            # 2. Criar arestas para cada dependência
            for dep in cell.dependencies:
                # dep pode ser "B1" (mesma sheet) ou "Sheet2!B1" (cross-sheet)
                if "!" not in dep:
                    dep_id = make_node_id(sheet.name, dep)
                else:
                    dep_id = dep  # já está no formato canônico
                
                edges.append(DAGEdge(source=dep_id, target=node_id))
    
    # 3. Adicionar nós de dependência que podem não estar explicitamente no IR
    # (ex: células referenciadas que são valores estáticos não listados em 'cells')
    for edge in edges:
        if edge.source not in seen_nodes:
            parts = edge.source.split("!", 1)
            if len(parts) == 2:
                s, c = parts
                nodes.append(DAGNode(
                    id=edge.source,
                    sheet=s,
                    coordinate=c,
                    formula_raw=None,
                    data_type="n"  # inferido como valor estático
                ))
                seen_nodes.add(edge.source)
    
    # Preencher dag_node.dependencies a partir das arestas (source → target significa target depende de source)
    deps_by_target: dict[str, list[str]] = {}
    for edge in edges:
        deps_by_target.setdefault(edge.target, []).append(edge.source)
    for node in nodes:
        node.dependencies = deps_by_target.get(node.id, [])

    dag = ExecutionDAG(
        nodes=nodes,
        edges=edges,
        topological_order=[],
        has_cycles=False,
        cycles=[],
        graph_metadata={
            "num_nodes": len(nodes),
            "num_edges": len(edges),
            "num_sheets": len(normalized_ir.sheets)
        }
    )

    # 4. Detecção de Ciclos
    cycles = detect_cycles(dag)
    dag.has_cycles = len(cycles) > 0
    dag.cycles = cycles
    
    # 5. Ordenação Topológica
    dag.topological_order = topological_sort(dag)
    
    return dag

def detect_cycles(dag: ExecutionDAG) -> list[CycleInfo]:
    """
    Detecta e classifica ciclos no grafo usando DFS com path-stack.
    A pilha explícita garante que apenas nós na recursão atual sejam
    considerados para reconstrução do ciclo — eliminando falsos positivos
    em grafos acíclicos com caminhos convergentes.
    """
    adj: dict[str, list[str]] = {node.id: [] for node in dag.nodes}
    for edge in dag.edges:
        if edge.source in adj:
            adj[edge.source].append(edge.target)
    
    color: dict[str, int] = {node.id: WHITE for node in dag.nodes}
    cycles: list[CycleInfo] = []
    seen_signatures: set[str] = set()
    
    def dfs(node_id: str, path_stack: list[str]):
        color[node_id] = GRAY
        path_stack.append(node_id)
        
        for neighbor in adj.get(node_id, []):
            if color.get(neighbor) == GRAY:
                # Ciclo detectado — neighbor está na pilha atual
                try:
                    cycle_start_idx = path_stack.index(neighbor)
                    cycle_nodes = list(path_stack[cycle_start_idx:])
                    cycle_nodes.append(neighbor)  # fechar o ciclo para visualização
                    
                    # Assinatura única para evitar duplicar o mesmo ciclo detectado de pontos diferentes
                    cycle_signature = "|".join(sorted(set(cycle_nodes)))
                    
                    if cycle_signature not in seen_signatures:
                        seen_signatures.add(cycle_signature)
                        cycle_type = _classify_cycle(cycle_nodes)
                        cycles.append(CycleInfo(
                            cycle_type=cycle_type,
                            nodes_involved=cycle_nodes,
                            description=f"Cycle: {' -> '.join(cycle_nodes)}"
                        ))
                except ValueError:
                    pass # Caso raro onde index falha
            elif color.get(neighbor) == WHITE:
                dfs(neighbor, path_stack)
        
        path_stack.pop()
        color[node_id] = BLACK
    
    for node_id in adj:
        if color.get(node_id) == WHITE:
            dfs(node_id, [])
    
    return cycles

def _classify_cycle(cycle_nodes: list[str]) -> CycleType:
    """Classifica o tipo de ciclo."""
    unique_nodes = list(dict.fromkeys(cycle_nodes))
    n = len(unique_nodes)
    if n == 1:
        return CycleType.SELF_REFERENCE
    elif n == 2:
        return CycleType.DIRECT
    else:
        return CycleType.INDIRECT

def topological_sort(dag: ExecutionDAG) -> list[str]:
    """
    Gera ordenação topológica usando algoritmo de Kahn (BFS).
    Se houver ciclos, retorna ordenação parcial: nós acíclicos primeiro,
    seguidos dos nós cíclicos (não ordenáveis deterministicamente).
    """
    in_degree: dict[str, int] = {node.id: 0 for node in dag.nodes}
    adj: dict[str, list[str]] = {node.id: [] for node in dag.nodes}
    
    for edge in dag.edges:
        if edge.target in in_degree:
            in_degree[edge.target] += 1
        if edge.source in adj:
            adj[edge.source].append(edge.target)
    
    queue: deque[str] = deque()
    for node_id, deg in in_degree.items():
        if deg == 0:
            queue.append(node_id)
    
    order: list[str] = []
    processed: set[str] = set()
    
    while queue:
        if len(queue) > 500000:  # Safety break
            break
        node_id = queue.popleft()
        if node_id in processed:
            continue
        processed.add(node_id)
        order.append(node_id)
        
        for neighbor in adj.get(node_id, []):
            if neighbor in in_degree:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0 and neighbor not in processed:
                    queue.append(neighbor)
    
    # Nós restantes: participam de ciclos ou estão isolados em clusters cíclicos
    if len(order) < len(dag.nodes):
        remaining = [n.id for n in dag.nodes if n.id not in processed]
        # Ordenar estavelmente para previsibilidade
        order.extend(sorted(remaining))
    
    return order

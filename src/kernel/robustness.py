"""
EXRS Kernel — Robustez genérica: deduplicação por chave e régua de referência
cross-entidade que nunca é contaminada por pseudo-entidade.

Nada aqui sabe o que é um "cliente", um "CPF" ou uma "loja não identificada" — quem
chama fornece a chave de agrupamento, o normalizador dela, e o predicado que decide
o que é uma entidade sintética (pseudo-entidade) no próprio domínio. É esse
parâmetro que mantém o mecanismo reutilizável por qualquer domínio (Produto B usa
CPF/SEM_CADASTRO; um segundo consumidor real usaria outra chave, outros sentinelas).
"""


def dedup_by_key(
    ids: list[str], keys: list[str], key_normalizer=lambda k: k,
) -> dict[str, str]:
    """Agrupa `ids` que compartilham o mesmo valor de `keys` (normalizado por
    `key_normalizer`) — duas identidades diferentes com a mesma chave são a MESMA
    entidade. `ids`/`keys` são paralelos (mesmo índice = mesmo registro); id ou key
    ausente/vazio (após normalização) nunca entra em um grupo — ausência de chave
    não é uma chave, é a ausência de uma.

    ID canônico do grupo = o menor id em ordem lexicográfica — escolha arbitrária
    mas determinística e estável (mesma entrada sempre produz o mesmo canônico).

    Retorna {id_bruto -> id_canônico} contendo só os ids que de fato pertencem a um
    grupo de >= 2 identidades (grupos singulares não entram no mapa —
    `dict.get(id, id)` já resolve identidade pra quem não está aqui). Sem entradas,
    retorna {} — nunca inventa dedupe."""
    groups: dict[str, list[str]] = {}
    for id_val, key_val in zip(ids, keys):
        if id_val is None or key_val is None:
            continue
        id_clean = str(id_val).strip()
        key_norm = key_normalizer(key_val)
        if not id_clean or not key_norm:
            continue
        groups.setdefault(key_norm, []).append(id_clean)

    canonical_map: dict[str, str] = {}
    for members in groups.values():
        unique_members = sorted(set(members))
        if len(unique_members) < 2:
            continue
        canonical = unique_members[0]
        for member in unique_members:
            canonical_map[member] = canonical
    return canonical_map


def benchmark_population(
    entity_stats: dict[str, dict], is_pseudo_entity, predicate=lambda stats: True,
) -> list[dict]:
    """Filtra `entity_stats` (dict entity_id -> métricas) para uma régua de
    referência cross-entidade (mediana, percentil, quantil, etc.) — SEMPRE exclui
    pseudo-entidades via `is_pseudo_entity` (fornecido pelo chamador — o kernel não
    sabe o que é uma entidade sintética no domínio de quem chama), e aceita um
    `predicate` extra por cima (ex. "só quem tem tenure suficiente"). Uso
    OBRIGATÓRIO em qualquer detector que compute estatística de referência entre
    entidades reais — nunca um filtro ad-hoc inline de novo."""
    return [
        stats for entity_id, stats in entity_stats.items()
        if not is_pseudo_entity(entity_id) and predicate(stats)
    ]

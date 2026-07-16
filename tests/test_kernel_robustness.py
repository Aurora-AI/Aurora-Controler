"""
Testes de src/kernel/robustness.py — deduplicação genérica por chave + régua de
referência cross-entidade que nunca é contaminada por pseudo-entidade.

Deliberadamente usa vocabulário genérico (widget/tag) em vez de CPF/cliente — a
cobertura do uso real de CPF (dedupe de cliente) mora em
tests/test_customer_cpf_dedupe.py, que testa através do wrapper de domínio do
Produto B (build_cpf_canonical_map). Aqui o objetivo é provar que o mecanismo em si
não depende de nada específico de varejo.
"""
from kernel.robustness import benchmark_population, dedup_by_key


# ── dedup_by_key ────────────────────────────────────────────────────────────────────

def test_dedup_by_key_groups_ids_sharing_same_normalized_key():
    ids = ["W1", "W2", "W3"]
    keys = ["AAA", "AAA", "BBB"]
    result = dedup_by_key(ids, keys)
    assert result == {"W1": "W1", "W2": "W1"}  # W3 fica de fora (grupo singular)


def test_dedup_by_key_canonical_is_lexicographically_smallest_member():
    result = dedup_by_key(["W9", "W2", "W5"], ["X", "X", "X"])
    assert result == {"W2": "W2", "W5": "W2", "W9": "W2"}


def test_dedup_by_key_singleton_groups_are_never_included():
    """Grupo de 1 membro não é dedupe de nada — não entra no mapa. dict.get(id, id)
    já resolve identidade pra quem não está aqui."""
    result = dedup_by_key(["W1", "W2"], ["AAA", "BBB"])
    assert result == {}


def test_dedup_by_key_none_id_or_key_is_skipped_not_the_whole_group():
    """id ou key None quebra só o PAR (linha suja isolada) — os outros membros do
    mesmo grupo continuam agrupando normalmente entre si."""
    result = dedup_by_key(["W1", None, "W3"], ["AAA", "AAA", "AAA"])
    assert result == {"W1": "W1", "W3": "W1"}
    result2 = dedup_by_key(["W1", "W2", "W3"], ["AAA", None, "AAA"])
    assert result2 == {"W1": "W1", "W3": "W1"}


def test_dedup_by_key_empty_or_whitespace_key_never_forms_a_group():
    """Ausência de chave (vazio após normalização) não é uma chave — é a ausência de
    uma. Regra inegociável herdada do dedupe de CPF original."""
    result = dedup_by_key(["W1", "W2"], ["", ""])
    assert result == {}


def test_dedup_by_key_applies_custom_key_normalizer():
    """key_normalizer é o que mantém o kernel agnóstico — quem chama decide o que
    'normalizar' significa no próprio domínio (ex. Produto B usa só-dígitos pra CPF;
    este teste usa upper-case)."""
    result = dedup_by_key(
        ["W1", "W2"], ["abc", "ABC"], key_normalizer=lambda k: k.upper(),
    )
    assert result == {"W1": "W1", "W2": "W1"}


def test_dedup_by_key_id_whitespace_is_stripped():
    result = dedup_by_key(["  W1  ", "W2"], ["AAA", "AAA"])
    assert result == {"W1": "W1", "W2": "W1"}


def test_dedup_by_key_multiple_independent_groups():
    ids = ["A", "B", "C", "D", "E"]
    keys = ["111", "111", "222", "222", "333"]  # E fica sozinho
    result = dedup_by_key(ids, keys)
    assert result == {"A": "A", "B": "A", "C": "C", "D": "C"}


def test_dedup_by_key_empty_input_returns_empty_map():
    assert dedup_by_key([], []) == {}


# ── benchmark_population ────────────────────────────────────────────────────────────

def test_benchmark_population_excludes_pseudo_entities():
    stats = {"real-1": {"v": 10}, "PSEUDO": {"v": 999}, "real-2": {"v": 20}}
    result = benchmark_population(stats, is_pseudo_entity=lambda eid: eid == "PSEUDO")
    assert result == [{"v": 10}, {"v": 20}]


def test_benchmark_population_applies_extra_predicate_on_top_of_pseudo_exclusion():
    stats = {"a": {"v": 1, "ok": True}, "b": {"v": 2, "ok": False}}
    result = benchmark_population(
        stats, is_pseudo_entity=lambda eid: False, predicate=lambda s: s["ok"],
    )
    assert result == [{"v": 1, "ok": True}]


def test_benchmark_population_empty_dict_returns_empty_list():
    assert benchmark_population({}, is_pseudo_entity=lambda eid: False) == []


def test_benchmark_population_all_pseudo_returns_empty_list():
    stats = {"PSEUDO-1": {"v": 1}, "PSEUDO-2": {"v": 2}}
    result = benchmark_population(stats, is_pseudo_entity=lambda eid: True)
    assert result == []


def test_benchmark_population_default_predicate_accepts_everything_not_pseudo():
    stats = {"a": {"v": 1}, "b": {"v": 2}}
    result = benchmark_population(stats, is_pseudo_entity=lambda eid: False)
    assert len(result) == 2

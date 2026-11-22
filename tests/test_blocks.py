from vera.blocks import (
    DETERMINISTIC,
    STATISTICAL,
    expand_block,
    load_tasks,
    seed_for,
)
from vera.models import MODELS
from vera.prompts import PROMPT_VERSION
from vera.types import Condition


def _segments_by_model(configs):
    segments = []
    for c in configs:
        if not segments or segments[-1][0] != c.model.name:
            segments.append((c.model.name, []))
        segments[-1][1].append(c)
    return segments


def test_models_registry_ports():
    assert MODELS["llama3.1:8b"].base_url == "http://127.0.0.1:11435"
    assert MODELS["gemma4:e4b"].base_url == "http://127.0.0.1:11435"
    assert MODELS["qwen2.5-coder:7b"].base_url == "http://127.0.0.1:11434"
    assert MODELS["qwen3:8b"].base_url == "http://127.0.0.1:11434"


def test_deterministic_expands_to_80_runs():
    tasks = load_tasks("java")
    configs = expand_block(DETERMINISTIC, tasks)
    assert len(configs) == 2 * 10 * 2 * 2
    assert {c.task.id for c in configs} == {t.id for t in tasks[:10]}
    assert all(c.task.container == "StringUtils" for c in configs)
    assert all(c.temperature == 0.0 and c.seed == 42 for c in configs)
    assert all(c.prompt_version == PROMPT_VERSION for c in configs)


def test_statistical_expands_to_2400_runs():
    configs = expand_block(STATISTICAL, load_tasks("java"))
    assert len(configs) == 4 * 20 * 2 * 15
    assert all(c.temperature == 0.7 for c in configs)
    assert all(c.seed == seed_for(c.run_id) for c in configs)


def test_runs_grouped_by_model():
    configs = expand_block(STATISTICAL, load_tasks("java"))
    names = [name for name, _ in _segments_by_model(configs)]
    assert names == STATISTICAL.models


def test_conditions_interleaved_within_model():
    configs = expand_block(STATISTICAL, load_tasks("java"))
    for _, segment in _segments_by_model(configs):
        conds = [c.condition for c in segment]
        assert all(a != b for a, b in zip(conds, conds[1:]))
        # Las repeticiones no se agotan por tarea: la primera vuelta recorre las 20 tareas.
        assert len({c.task.id for c in segment[:40]}) == 20
        assert {c.repetition for c in segment[:40]} == {1}


def test_seed_is_stable_and_differs_between_conditions():
    configs = expand_block(STATISTICAL, load_tasks("java"))
    base = next(c for c in configs if c.condition is Condition.BASELINE)
    rep = next(c for c in configs if c.condition is Condition.REPAIR
               and c.task.id == base.task.id and c.repetition == base.repetition
               and c.model.name == base.model.name)
    assert seed_for(base.run_id) == seed_for(base.run_id)
    assert seed_for(base.run_id) != seed_for(rep.run_id)
    assert 0 <= seed_for(base.run_id) < 2**31
    assert seed_for("a/b") == seed_for("a/b")


def test_run_ids_are_unique():
    for block in (DETERMINISTIC, STATISTICAL):
        configs = expand_block(block, load_tasks("java"))
        assert len({c.run_id for c in configs}) == len(configs)

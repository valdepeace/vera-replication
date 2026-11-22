"""Utilidades compartidas por las pruebas."""
import pytest

from vera.types import Attempt, AuditOutcome, Condition, ModelSpec, RunConfig, RunRecord, Task


def _record(*, model="m1", condition=Condition.BASELINE, accepted=True,
            audit=AuditOutcome.REAL, valid=True, block="estadistico", task_id="t1",
            language="java", repetition=1, prompt_tokens=10, completion_tokens=5):
    task = Task(id=task_id, language=language, project="p", focal_name="f", focal_source="s",
                container="C", test_name="CTest", import_hint="")
    config = RunConfig(block=block, model=ModelSpec(name=model, engine="ollama", base_url="u"),
                       task=task, condition=condition, repetition=repetition, seed=1,
                       temperature=0.0, prompt_version="v")
    attempt = Attempt(index=0, kind="generate", prompt="", raw_response="", parse_ok=True,
                      parse_error=None, code="", truncated=False, validation=None,
                      prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                      seconds=0.0)
    return RunRecord(config=config, attempts=[attempt], accepted=accepted,
                     stop_reason="accepted" if accepted else "budget_exhausted",
                     audit=audit if accepted else None, valid=valid,
                     infra_error=None if valid else "TimeoutError: maven")


@pytest.fixture
def make_record():
    """Fábrica de RunRecord mínimos, con valores por omisión razonables."""
    return _record

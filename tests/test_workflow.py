from vera.adapters.base import LanguageAdapter
from vera.engines.base import ChatResult, EngineError
from vera.prompts import OUTPUT_SCHEMA, generation_messages
from vera.types import (
    AuditOutcome,
    Condition,
    ModelSpec,
    RunConfig,
    Task,
    ValidationResult,
)
from vera.workflow import run_workflow

TASK = Task(
    id="java-isBlank",
    language="java",
    project="commons-lang",
    focal_name="isBlank",
    focal_source="public static boolean isBlank(CharSequence cs) { return true; }",
    container="org.apache.commons.lang3.StringUtils",
    test_name="StringUtils_isBlank_Test",
    import_hint="",
)
MODEL = ModelSpec(name="m", engine="ollama", base_url="http://127.0.0.1:11434")


def config(condition):
    return RunConfig(
        block="det", model=MODEL, task=TASK, condition=condition,
        repetition=1, seed=7, temperature=0.0, prompt_version="vera01-p1",
    )


def ok(code="class T {}", prompt_tokens=10, completion_tokens=20, truncated=False, text=None):
    body = text if text is not None else '{"code": "' + code + '", "note": "n"}'
    return ChatResult(text=body, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                      load_seconds=0.0, total_seconds=0.1, truncated=truncated)


class FakeEngine:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, *, model, options, json_schema):
        self.calls.append({"messages": messages, "model": model,
                           "options": options, "json_schema": json_schema})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeAdapter:
    def __init__(self, results, audit=AuditOutcome.REAL):
        self.results = list(results)
        self.audit_outcome = audit
        self.validated = []
        self.audited = []

    def validate(self, task, code):
        self.validated.append(code)
        return self.results.pop(0)

    def audit(self, task, code):
        self.audited.append(code)
        return self.audit_outcome


PASS = ValidationResult(passed=True, diagnostic="", seconds=1.0)


def fail(msg="assertion failed"):
    return ValidationResult(passed=False, diagnostic=msg, seconds=1.0)


def test_fake_adapter_satisfies_protocol():
    adapter: LanguageAdapter = FakeAdapter([])
    assert hasattr(adapter, "validate") and hasattr(adapter, "audit")


def test_baseline_stops_after_one_failed_attempt():
    engine = FakeEngine([ok()])
    rec = run_workflow(config(Condition.BASELINE), engine, FakeAdapter([fail()]))
    assert rec.stop_reason == "budget_exhausted"
    assert rec.accepted is False and rec.valid is True
    assert len(rec.attempts) == 1 and len(engine.calls) == 1


def test_engine_receives_config_options_and_schema():
    engine = FakeEngine([ok()])
    run_workflow(config(Condition.BASELINE), engine, FakeAdapter([PASS]))
    call = engine.calls[0]
    assert call["model"] == "m"
    assert call["json_schema"] == OUTPUT_SCHEMA
    o = call["options"]
    assert (o.num_ctx, o.num_predict, o.temperature, o.seed, o.keep_alive) == (8192, 2048, 0.0, 7, "30m")


def test_generation_prompt_same_for_both_conditions():
    e1, e2 = FakeEngine([ok()]), FakeEngine([ok()])
    run_workflow(config(Condition.BASELINE), e1, FakeAdapter([PASS]))
    run_workflow(config(Condition.REPAIR), e2, FakeAdapter([PASS]))
    assert e1.calls[0]["messages"] == e2.calls[0]["messages"] == generation_messages(TASK)


def test_workflow_uses_the_prompt_version_of_the_config_in_every_attempt():
    from dataclasses import replace

    from vera.prompts import PROMPT_VERSION_P2, repair_messages

    task = replace(TASK, container="StringUtils",
                   import_hint="import org.apache.commons.lang3.StringUtils;")
    cfg = replace(config(Condition.REPAIR), task=task, prompt_version=PROMPT_VERSION_P2)
    engine = FakeEngine([ok("a"), ok("b")])
    run_workflow(cfg, engine, FakeAdapter([fail("err-a"), PASS]))
    assert engine.calls[0]["messages"] == generation_messages(task, PROMPT_VERSION_P2)
    assert engine.calls[1]["messages"] == repair_messages(task, "a", "err-a", PROMPT_VERSION_P2)
    assert "with: import org.apache.commons.lang3.StringUtils;" in engine.calls[0]["messages"][-1]["content"]


def test_repair_succeeds_on_third_attempt():
    engine = FakeEngine([ok("a"), ok("b"), ok("c")])
    adapter = FakeAdapter([fail("err-a"), fail("err-b"), PASS])
    rec = run_workflow(config(Condition.REPAIR), engine, adapter)
    assert rec.stop_reason == "accepted" and rec.accepted is True and rec.valid is True
    assert [a.kind for a in rec.attempts] == ["generate", "repair", "repair"]
    assert [a.index for a in rec.attempts] == [0, 1, 2]
    assert adapter.validated == ["a", "b", "c"]
    second = "\n".join(m["content"] for m in engine.calls[1]["messages"])
    assert "err-a" in second and "a" in second
    assert rec.attempts[1].prompt == engine.calls[1]["messages"][-1]["content"]


def test_budget_is_one_plus_three_attempts():
    engine = FakeEngine([ok()] * 4)
    rec = run_workflow(config(Condition.REPAIR), engine, FakeAdapter([fail()] * 4))
    assert len(rec.attempts) == 4 and len(engine.calls) == 4
    assert rec.stop_reason == "budget_exhausted"
    assert rec.accepted is False and rec.audit is None


def test_parse_failure_consumes_a_repair():
    engine = FakeEngine([ok(text="not json at all"), ok("good")])
    adapter = FakeAdapter([PASS])
    rec = run_workflow(config(Condition.REPAIR), engine, adapter)
    first = rec.attempts[0]
    assert first.parse_ok is False and first.parse_error == "invalid_json"
    assert first.validation is None and first.code is None
    assert adapter.validated == ["good"]
    repair_text = "\n".join(m["content"] for m in engine.calls[1]["messages"])
    assert "invalid or truncated format" in repair_text
    assert rec.attempts[1].kind == "repair"
    assert rec.stop_reason == "accepted"


def test_parse_failure_in_baseline_exhausts_budget():
    engine = FakeEngine([ok(text='{"code": ""}')])
    rec = run_workflow(config(Condition.BASELINE), engine, FakeAdapter([]))
    assert rec.attempts[0].parse_error == "empty_code"
    assert rec.stop_reason == "budget_exhausted" and rec.valid is True


def test_truncated_output_consumes_a_repair():
    engine = FakeEngine([ok("cut", truncated=True), ok("good")])
    adapter = FakeAdapter([PASS])
    rec = run_workflow(config(Condition.REPAIR), engine, adapter)
    first = rec.attempts[0]
    assert first.truncated is True and first.parse_ok is False and first.validation is None
    assert adapter.validated == ["good"]
    repair_text = "\n".join(m["content"] for m in engine.calls[1]["messages"])
    assert "invalid or truncated format" in repair_text
    assert len(rec.attempts) == 2 and rec.stop_reason == "accepted"


def test_engine_error_marks_infra_failure():
    engine = FakeEngine([ok("a"), EngineError("timeout")])
    rec = run_workflow(config(Condition.REPAIR), engine, FakeAdapter([fail()]))
    assert rec.stop_reason == "infra_failure"
    assert rec.valid is False and rec.accepted is False and rec.audit is None


def test_adapter_infra_failure_marks_infra_failure():
    infra = ValidationResult(passed=False, diagnostic="maven timeout", seconds=600.0, infra_failure=True)
    engine = FakeEngine([ok(), ok()])
    rec = run_workflow(config(Condition.REPAIR), engine, FakeAdapter([infra]))
    assert rec.stop_reason == "infra_failure"
    assert rec.valid is False and rec.accepted is False and rec.audit is None
    assert len(engine.calls) == 1


def test_accepted_run_is_audited():
    adapter = FakeAdapter([PASS], audit=AuditOutcome.ASSERTION_FREE)
    rec = run_workflow(config(Condition.BASELINE), FakeEngine([ok("x")]), adapter)
    assert rec.audit is AuditOutcome.ASSERTION_FREE
    assert adapter.audited == ["x"]

    adapter2 = FakeAdapter([fail()])
    rec2 = run_workflow(config(Condition.BASELINE), FakeEngine([ok()]), adapter2)
    assert rec2.audit is None and adapter2.audited == []


def test_tokens_are_summed_over_attempts():
    engine = FakeEngine([ok(prompt_tokens=100, completion_tokens=7),
                         ok(prompt_tokens=200, completion_tokens=8),
                         ok(prompt_tokens=300, completion_tokens=9)])
    rec = run_workflow(config(Condition.REPAIR), engine, FakeAdapter([fail(), fail(), PASS]))
    assert [a.prompt_tokens for a in rec.attempts] == [100, 200, 300]
    assert rec.total_prompt_tokens == 600
    assert rec.total_completion_tokens == 24


def test_repair_diagnostic_is_truncated_in_workflow():
    huge = "E" * 50_000
    engine = FakeEngine([ok(), ok()])
    run_workflow(config(Condition.REPAIR), engine, FakeAdapter([fail(huge), PASS]))
    repair_text = "\n".join(m["content"] for m in engine.calls[1]["messages"])
    assert repair_text.count("E" * 4000) == 1
    assert "E" * 4001 not in repair_text


def test_engine_error_is_described_in_infra_error():
    engine = FakeEngine([EngineError("timeout", "sin respuesta")])
    rec = run_workflow(config(Condition.BASELINE), engine, FakeAdapter([]))
    assert rec.stop_reason == "infra_failure"
    assert rec.infra_error == "EngineError(timeout): sin respuesta"


def test_validation_infra_failure_is_described_in_infra_error():
    infra = ValidationResult(passed=False, diagnostic="Maven agotó el tiempo", seconds=1.0,
                             infra_failure=True)
    rec = run_workflow(config(Condition.BASELINE), FakeEngine([ok()]), FakeAdapter([infra]))
    assert rec.stop_reason == "infra_failure"
    assert rec.infra_error == "validation: Maven agotó el tiempo"

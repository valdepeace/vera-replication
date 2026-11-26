import json

import pytest

from vera.__main__ import main
from vera.blocks import DETERMINISTIC, expand_block, load_tasks
from vera.engines.base import ChatResult, EngineError
from vera.prompts import PROMPT_VERSION
from vera.runner import BlockAborted, block_dir, execute_block, run_block
from vera.store import RunStore
from vera.types import AuditOutcome, ValidationResult

TASKS = load_tasks("java")
PASS = ValidationResult(passed=True, diagnostic="", seconds=0.1)


def ok():
    return ChatResult(text='{"code": "class T {}", "note": "n"}', prompt_tokens=1,
                      completion_tokens=1, load_seconds=0.0, total_seconds=0.1, truncated=False)


class FakeEngine:
    """Responde con un guion; agotado el guion, responde siempre bien."""

    def __init__(self, script=()):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, *, model, options, json_schema):
        self.calls += 1
        item = self.script.pop(0) if self.script else ok()
        if isinstance(item, Exception):
            raise item
        return item


class FakeAdapter:
    def __init__(self):
        self.validated = 0

    def validate(self, task, code):
        self.validated += 1
        return PASS

    def audit(self, task, code):
        return AuditOutcome.REAL


class SleepRecorder:
    def __init__(self):
        self.waits = []

    def __call__(self, seconds):
        self.waits.append(seconds)


def run(configs, engine, store, **kw):
    kw.setdefault("sleep", SleepRecorder())
    return execute_block(configs, engines_for(configs, engine), {"java": FakeAdapter()}, store, **kw)


def det_configs(n):
    return expand_block(DETERMINISTIC, TASKS)[:n]


def engines_for(configs, engine):
    return {c.model.name: engine for c in configs}


def test_resume_skips_completed_runs(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(4)
    first = execute_block(configs[:2], engines_for(configs, FakeEngine()),
                          {"java": FakeAdapter()}, store)
    assert (first.executed, first.resumed) == (2, 0)
    engine = FakeEngine()
    summary = execute_block(configs, engines_for(configs, engine), {"java": FakeAdapter()}, store)
    assert (summary.total, summary.executed, summary.resumed) == (4, 2, 2)
    assert engine.calls == 2
    assert len(list(store.load_all())) == 4


def test_incomplete_tmp_files_are_not_resumed_as_complete(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(1)
    target = store._path(configs[0].run_id)
    target.parent.mkdir(parents=True)
    target.with_name(target.name + ".tmp").write_text('{"config": {"blo', encoding="utf-8")
    summary = execute_block(configs, engines_for(configs, FakeEngine()), {"java": FakeAdapter()}, store)
    assert (summary.executed, summary.resumed, summary.valid) == (1, 0, 1)
    assert store.has(configs[0].run_id)
    assert len(list(store.load_all())) == 1


def test_infra_failure_retried_twice_then_succeeds(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(1)
    engine = FakeEngine([EngineError("timeout"), EngineError("connection"), ok()])
    sleep = SleepRecorder()
    summary = run(configs, engine, store, sleep=sleep)
    assert sleep.waits == [2, 5]
    record = next(store.load_all())
    assert record.valid is True and record.accepted is True
    assert engine.calls == 3
    assert (summary.accepted, summary.valid, summary.invalid) == (1, 1, 0)


def test_unexpected_exception_is_treated_as_infra_failure(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(1)
    engine = FakeEngine([TypeError("json raro"), ok()])
    run(configs, engine, store)
    record = next(store.load_all())
    assert record.valid is True and engine.calls == 2 and record.infra_error is None


def test_infra_failure_three_times_marks_invalid(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(1)
    engine = FakeEngine([EngineError("server"), EngineError("server"), TypeError("x"), ok()])
    sleep = SleepRecorder()
    summary = run(configs, engine, store, sleep=sleep)
    record = next(store.load_all())
    assert record.valid is False and record.stop_reason == "infra_failure"
    assert record.accepted is False
    assert record.infra_error == "TypeError: x"
    assert engine.calls == 3
    assert sleep.waits == [2, 5]
    assert (summary.executed, summary.accepted, summary.valid, summary.invalid) == (1, 0, 0, 1)


def test_dry_run_executes_nothing_and_reports_count(tmp_path):
    engine = FakeEngine()
    engines = {name: engine for name in DETERMINISTIC.models}
    summary = run_block(DETERMINISTIC, "java", results_root=tmp_path / "results",
                        engines=engines, adapters={"java": FakeAdapter()}, dry_run=True,
                        env_collector=lambda names: pytest.fail("no debe recoger el entorno"))
    assert summary.total == 80 and summary.executed == 0
    assert engine.calls == 0
    assert not (tmp_path / "results").exists()
    limited = run_block(DETERMINISTIC, "java", results_root=tmp_path / "results",
                        engines=engines, adapters={"java": FakeAdapter()}, dry_run=True, limit=5)
    assert limited.total == 5
    assert engine.calls == 0


def test_block_writes_manifest_with_env_and_prompt_version(tmp_path):
    configs = det_configs(3)
    engine = FakeEngine()
    seen = []

    def env(names):
        seen.append(names)
        return {"models": {n: "sha256:x" for n in names}}

    summary = run_block(DETERMINISTIC, "java", results_root=tmp_path, limit=3,
                        engines=engines_for(configs, engine), adapters={"java": FakeAdapter()},
                        env_collector=env, harness_commit=lambda: "abc123")
    out = block_dir(tmp_path, DETERMINISTIC, "java")
    assert out == tmp_path / "runs" / "determinista" / "java"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert not (out / "records" / "manifest.json").exists()
    assert manifest["block"] == "determinista" and manifest["language"] == "java"
    assert manifest["prompt_version"] == PROMPT_VERSION
    session = manifest["sessions"][-1]
    assert session["harness_commit"] == "abc123"
    assert session["env"] == {"models": {n: "sha256:x" for n in DETERMINISTIC.models}}
    assert session["planned"] == 3
    assert seen == [DETERMINISTIC.models]
    assert summary.executed == 3
    assert len(list(RunStore(out / "records").load_all())) == 3


class RepairAdapter(FakeAdapter):
    """Adaptador cuya primera validación es un fallo de infraestructura con intentos."""

    def __init__(self, infra_first):
        super().__init__()
        self.infra_first = infra_first

    def validate(self, task, code):
        self.validated += 1
        if self.validated <= self.infra_first:
            return ValidationResult(passed=False, diagnostic="maven caído", seconds=0.1,
                                    infra_failure=True)
        return PASS


def test_exception_after_infra_record_keeps_earlier_attempts(tmp_path, capsys):
    store = RunStore(tmp_path / "records")
    configs = det_configs(1)
    engine = FakeEngine([ok(), ok(), RuntimeError("se cayó")])
    execute_block(configs, engines_for(configs, engine), {"java": RepairAdapter(2)}, store,
                  sleep=SleepRecorder())
    record = next(store.load_all())
    assert record.stop_reason == "infra_failure" and record.valid is False
    assert len(record.attempts) == 1 and record.attempts[0].validation.infra_failure
    assert record.infra_error == "RuntimeError: se cayó"
    err = capsys.readouterr().err
    assert "RuntimeError: se cayó" in err and "maven caído" in err


def test_resume_reexecutes_infra_failures(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(2)
    run(configs[:1], FakeEngine([EngineError("server")] * 3), store)
    assert next(store.load_all()).valid is False
    engine = FakeEngine()
    summary = run(configs, engine, store)
    assert (summary.executed, summary.resumed, summary.valid, summary.invalid) == (2, 0, 2, 0)
    assert engine.calls == 2
    records = list(store.load_all())
    assert len(records) == 2 and all(r.valid for r in records)


def test_skip_infra_failed_keeps_them(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(2)
    run(configs[:1], FakeEngine([EngineError("server")] * 3), store)
    engine = FakeEngine()
    summary = run(configs, engine, store, skip_infra_failed=True)
    assert (summary.executed, summary.resumed) == (1, 1)
    assert engine.calls == 1


def test_five_consecutive_infra_failures_abort_block(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(8)
    engine = FakeEngine([EngineError("connection")] * 100)
    with pytest.raises(BlockAborted) as exc:
        run(configs, engine, store)
    assert "5" in str(exc.value)
    assert exc.value.summary.executed == 5 and exc.value.summary.invalid == 5
    assert len(list(store.load_all())) == 5
    assert engine.calls == 15


def test_infra_streak_resets_after_a_valid_run(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(9)
    failing = [EngineError("connection")] * 12
    engine = FakeEngine(failing + [ok()] + failing)  # 4 inválidas, 1 válida, 4 inválidas
    summary = run(configs, engine, store)
    assert (summary.executed, summary.valid, summary.invalid) == (9, 1, 8)


def test_cli_reports_block_aborted_with_nonzero_exit(monkeypatch, capsys):
    import vera.runner

    def boom(*args, **kwargs):
        raise BlockAborted("servidor caído: 5 fallos de infraestructura seguidos", None)

    monkeypatch.setattr(vera.runner, "run_block", boom)
    code = main(["run", "--block", "determinista", "--language", "java", "--limit", "1",
                 "--skip-infra-failed"])
    assert code == 1
    assert "servidor caído" in capsys.readouterr().err


class UnloadingEngine(FakeEngine):
    """Motor falso con unload; anota en `events` las llamadas en orden."""

    def __init__(self, events, fail_unload=False):
        super().__init__()
        self.events = events
        self.fail_unload = fail_unload

    def chat(self, messages, *, model, options, json_schema):
        self.events.append(("chat", model))
        return super().chat(messages, model=model, options=options, json_schema=json_schema)

    def unload(self, model):
        self.events.append(("unload", model))
        if self.fail_unload:
            raise EngineError("connection", "servidor caído")


def two_model_configs():
    configs = expand_block(DETERMINISTIC, TASKS)
    first = configs[0].model.name
    split = next(i for i, c in enumerate(configs) if c.model.name != first)
    return configs[split - 2:split + 2]  # dos del primer modelo y dos del segundo


def test_unloads_previous_model_on_change_and_last_at_end(tmp_path):
    configs = two_model_configs()
    a, b = configs[0].model.name, configs[-1].model.name
    events = []
    engines = {a: UnloadingEngine(events), b: UnloadingEngine(events)}
    execute_block(configs, engines, {"java": FakeAdapter()}, RunStore(tmp_path / "r"),
                  sleep=SleepRecorder())
    assert events == [("chat", a), ("chat", a), ("unload", a),
                      ("chat", b), ("chat", b), ("unload", b)]
    assert engines[a].events is engines[b].events


def test_unload_goes_to_the_engine_of_the_previous_model(tmp_path):
    configs = two_model_configs()
    a, b = configs[0].model.name, configs[-1].model.name
    ev_a, ev_b = [], []
    engines = {a: UnloadingEngine(ev_a), b: UnloadingEngine(ev_b)}
    execute_block(configs, engines, {"java": FakeAdapter()}, RunStore(tmp_path / "r"),
                  sleep=SleepRecorder())
    assert ("unload", a) in ev_a and ("unload", a) not in ev_b
    assert ("unload", b) in ev_b and ("unload", b) not in ev_a


def test_resumed_runs_do_not_trigger_unload(tmp_path):
    configs = det_configs(2)
    store = RunStore(tmp_path / "r")
    execute_block(configs, engines_for(configs, FakeEngine()), {"java": FakeAdapter()}, store)
    events = []
    execute_block(configs, engines_for(configs, UnloadingEngine(events)),
                  {"java": FakeAdapter()}, store)
    assert events == []


def test_failing_unload_is_logged_and_block_continues(tmp_path, capsys):
    configs = two_model_configs()
    events = []
    engine = UnloadingEngine(events, fail_unload=True)
    summary = execute_block(configs, engines_for(configs, engine), {"java": FakeAdapter()},
                            RunStore(tmp_path / "r"), sleep=SleepRecorder())
    assert (summary.executed, summary.valid) == (4, 4)
    assert [e for e in events if e[0] == "unload"] == [
        ("unload", configs[0].model.name), ("unload", configs[-1].model.name)]
    err = capsys.readouterr().err
    assert "[unload]" in err and "servidor caído" in err


def test_aborted_block_still_unloads_current_model(tmp_path):
    configs = det_configs(6)
    events = []
    engine = UnloadingEngine(events)
    engine.script = [EngineError("connection")] * 100
    with pytest.raises(BlockAborted):
        run(configs, engine, RunStore(tmp_path / "r"))
    assert events[-1] == ("unload", configs[0].model.name)

import json

import pytest

from vera.__main__ import main
from vera.blocks import DETERMINISTIC, expand_block, load_tasks
from vera.engines.base import ChatResult, EngineError
from vera.prompts import PROMPT_VERSION
from vera.runner import block_dir, execute_block, run_block
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
    summary = execute_block(configs, engines_for(configs, engine), {"java": FakeAdapter()}, store)
    record = next(store.load_all())
    assert record.valid is True and record.accepted is True
    assert engine.calls == 3
    assert (summary.accepted, summary.valid, summary.invalid) == (1, 1, 0)


def test_unexpected_exception_is_treated_as_infra_failure(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(1)
    engine = FakeEngine([TypeError("json raro"), ok()])
    execute_block(configs, engines_for(configs, engine), {"java": FakeAdapter()}, store)
    record = next(store.load_all())
    assert record.valid is True and engine.calls == 2


def test_infra_failure_three_times_marks_invalid(tmp_path):
    store = RunStore(tmp_path / "records")
    configs = det_configs(1)
    engine = FakeEngine([EngineError("server"), TypeError("x"), EngineError("server"), ok()])
    summary = execute_block(configs, engines_for(configs, engine), {"java": FakeAdapter()}, store)
    record = next(store.load_all())
    assert record.valid is False and record.stop_reason == "infra_failure"
    assert record.accepted is False
    assert engine.calls == 3
    assert (summary.executed, summary.accepted, summary.valid, summary.invalid) == (1, 0, 0, 1)


def test_dry_run_executes_nothing_and_reports_count(tmp_path):
    engine = FakeEngine()
    summary = run_block(DETERMINISTIC, "java", results_root=tmp_path / "results",
                        engines={}, adapters={}, dry_run=True,
                        env_collector=lambda names: pytest.fail("no debe recoger el entorno"))
    assert summary.total == 80 and summary.executed == 0
    assert engine.calls == 0
    assert not (tmp_path / "results").exists()
    limited = run_block(DETERMINISTIC, "java", results_root=tmp_path / "results",
                        engines={}, adapters={}, dry_run=True, limit=5)
    assert limited.total == 5


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


def test_cli_without_adapter_exits_with_clear_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["run", "--block", "determinista", "--language", "python", "--dry-run"])
    assert exc.value.code == 2
    assert "python" in capsys.readouterr().err

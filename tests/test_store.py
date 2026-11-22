import dataclasses

from vera.store import RunStore
from vera.types import Attempt, AuditOutcome, Condition, RunRecord, ValidationResult

from test_types import make_config


def make_attempt(index=0, kind="generate", pt=100, ct=50, validated=True):
    return Attempt(
        index=index,
        kind=kind,
        prompt="p",
        raw_response="r",
        parse_ok=True,
        parse_error=None,
        code="class T {}",
        truncated=False,
        validation=ValidationResult(passed=False, diagnostic="boom", seconds=1.5) if validated else None,
        prompt_tokens=pt,
        completion_tokens=ct,
        seconds=2.0,
    )


def make_record(condition=Condition.REPAIR, repetition=0):
    return RunRecord(
        config=make_config(condition, repetition),
        attempts=[make_attempt(0), make_attempt(1, "repair", 200, 70)],
        accepted=True,
        stop_reason="accepted",
        audit=AuditOutcome.REAL,
        valid=True,
    )


def test_roundtrip_preserves_record(tmp_path):
    store = RunStore(tmp_path)
    rec = make_record()
    store.save(rec)
    loaded = list(store.load_all())
    assert loaded == [rec]
    assert dataclasses.asdict(loaded[0]) == dataclasses.asdict(rec)


def test_roundtrip_with_none_fields(tmp_path):
    store = RunStore(tmp_path)
    rec = make_record()
    rec.attempts = [make_attempt(validated=False)]
    rec.audit = None
    store.save(rec)
    assert list(store.load_all()) == [rec]


def test_has_false_until_saved(tmp_path):
    store = RunStore(tmp_path)
    rec = make_record()
    assert not store.has(rec.config.run_id)
    store.save(rec)
    assert store.has(rec.config.run_id)


def test_partial_write_is_ignored(tmp_path):
    store = RunStore(tmp_path)
    rec = make_record()
    store.save(rec)
    other = make_record(Condition.BASELINE, 3)
    (tmp_path / "half.json.tmp").write_text("{\"config\": ", encoding="utf-8")
    assert not store.has(other.config.run_id)
    assert list(store.load_all()) == [rec]


def test_save_is_atomic_and_leaves_no_tmp(tmp_path):
    store = RunStore(tmp_path)
    store.save(make_record())
    assert list(tmp_path.glob("*.tmp")) == []
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_run_id_with_slashes_and_colons_maps_to_safe_filename(tmp_path):
    store = RunStore(tmp_path)
    rec = make_record()
    store.save(rec)
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(files) == 1
    assert files[0].parent == tmp_path
    assert not any(ch in files[0].name for ch in '/\\:')
    assert store.has(rec.config.run_id)


def test_token_totals_sum_attempts():
    rec = make_record()
    assert rec.total_prompt_tokens == 300
    assert rec.total_completion_tokens == 120


def test_roundtrip_preserves_infra_error(tmp_path):
    store = RunStore(tmp_path)
    rec = dataclasses.replace(make_record(), accepted=False, stop_reason="infra_failure",
                              audit=None, valid=False, infra_error="TypeError: json raro")
    store.save(rec)
    assert next(store.load_all()).infra_error == "TypeError: json raro"
    assert store.load(rec.config.run_id) == rec


def test_records_without_infra_error_field_still_load(tmp_path):
    import json

    store = RunStore(tmp_path)
    rec = make_record()
    store.save(rec)
    path = next(tmp_path.glob("*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["infra_error"]
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = next(store.load_all())
    assert loaded.infra_error is None and loaded == rec

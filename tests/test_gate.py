from vera.engines.base import ChatResult, EngineError
from vera.gate import (GateVerdict, chat_metrics, evaluate_gate, gpu_residency,
                       parse_nvidia_smi, run_gate)
from vera.types import Task


def result(i, *, parse_error=None, truncated=False, tokens=600, seconds=10.0, warm=True,
           error=None):
    return {"task_id": f"t{i}", "parse_error": parse_error, "truncated": truncated,
            "completion_tokens": tokens, "gen_seconds": seconds, "warm": warm, "error": error}


def results(n_bad=0, **bad):
    """Diez respuestas a 60 tok/s; la primera en frío; las n_bad últimas con `bad`."""
    return [result(i, warm=i > 0, **(bad if i >= 10 - n_bad else {})) for i in range(10)]


def test_gate_passes_with_9_of_10_ok_and_speed():
    verdict = evaluate_gate(results(1, parse_error="invalid_json"))
    assert isinstance(verdict, GateVerdict)
    assert verdict.passed is True


def test_gate_fails_with_truncated_outputs():
    verdict = evaluate_gate(results(2, truncated=True, tokens=2048))
    assert verdict.passed is False
    assert any("truncada" in r for r in verdict.reasons)


def test_gate_fails_below_20_tok_s():
    slow = [result(i, warm=i > 0, tokens=190, seconds=10.0) for i in range(10)]
    verdict = evaluate_gate(slow)
    assert verdict.passed is False
    assert any("tok/s" in r and "19" in r for r in verdict.reasons)


def test_gate_reports_reasons():
    ok = evaluate_gate(results())
    assert ok.passed and any("10 de 10" in r for r in ok.reasons)
    assert any("60.0 tok/s" in r for r in ok.reasons)
    bad = evaluate_gate(results(3, error="EngineError(timeout)"))
    assert not bad.passed
    joined = " | ".join(bad.reasons)
    assert "7 de 10" in joined and "error" in joined


def test_gate_ignores_cold_call_for_speed():
    rs = results()
    rs[0] = result(0, warm=False, tokens=100, seconds=50.0)  # 2 tok/s en frío
    assert evaluate_gate(rs).passed is True


def test_gate_fails_without_warm_calls_or_with_wrong_count():
    cold_only = [result(0, warm=False)]
    verdict = evaluate_gate(cold_only)
    assert verdict.passed is False
    assert any("caliente" in r for r in verdict.reasons)
    assert any("10" in r and "1" in r for r in verdict.reasons)


def test_chat_metrics_from_ollama_body():
    body = {"load_duration": 2_000_000_000, "prompt_eval_count": 300,
            "prompt_eval_duration": 500_000_000, "eval_count": 400,
            "eval_duration": 5_000_000_000, "total_duration": 8_000_000_000,
            "done_reason": "stop"}
    m = chat_metrics(body)
    assert m["load_s"] == 2.0 and m["eval_s"] == 5.0 and m["tok_s"] == 80.0
    assert m["prompt_tokens"] == 300 and m["completion_tokens"] == 400
    assert m["truncated"] is False


def test_gpu_residency_from_api_ps():
    ps = {"models": [{"name": "otro", "size": 1, "size_vram": 1},
                     {"name": "m:7b", "model": "m:7b", "size": 6_000_000_000,
                      "size_vram": 4_500_000_000, "context_length": 8192}]}
    r = gpu_residency(ps, "m:7b")
    assert r == {"size_gb": 6.0, "size_vram_gb": 4.5, "gpu_fraction": 0.75,
                 "context_length": 8192}
    assert gpu_residency({"models": []}, "m:7b") is None


def test_parse_nvidia_smi():
    assert parse_nvidia_smi("5321, 8192\r\n") == (5321, 8192)


class GateEngine:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, messages, *, model, options, json_schema):
        self.seen.append((model, options, json_schema, messages))
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


TASK = Task(id="t", language="java", project="p", focal_name="f", focal_source="s",
            container="C", test_name="CTest", import_hint="")


def test_run_gate_uses_real_prompt_and_records_each_response():
    good = ChatResult(text='{"code": "class T {}", "note": "n"}', prompt_tokens=10,
                      completion_tokens=300, load_seconds=4.0, total_seconds=9.0,
                      truncated=False)
    cut = ChatResult(text='{"code": "cla', prompt_tokens=10, completion_tokens=2048,
                     load_seconds=0.0, total_seconds=30.0, truncated=True)
    engine = GateEngine([good, cut, EngineError("timeout", "lento")])
    rs = run_gate(engine, "m", [TASK, TASK, TASK])
    model, options, schema, messages = engine.seen[0]
    from vera.prompts import OUTPUT_SCHEMA, generation_messages
    assert messages == generation_messages(TASK) and schema == OUTPUT_SCHEMA
    assert (options.num_ctx, options.num_predict, options.temperature, options.seed,
            options.keep_alive) == (8192, 2048, 0.7, 1, "30m")
    assert rs[0]["warm"] is False and rs[1]["warm"] is True
    assert rs[0]["gen_seconds"] == 5.0 and rs[0]["parse_error"] is None
    assert rs[1]["truncated"] is True
    assert rs[2]["error"].startswith("EngineError(timeout)")

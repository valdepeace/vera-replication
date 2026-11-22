"""Mediciones de la fase 1 y puerta de calidad de los modelos.

La puerta somete a cada modelo a las diez tareas de StringUtils con el prompt real de
generación; los scripts `scripts/measure_*.py` y `scripts/gate_model.py` son envoltorios finos."""
from __future__ import annotations

import json
import statistics
import subprocess
import time
import urllib.request
from dataclasses import dataclass

from vera.engines.base import ChatEngine, ChatOptions, EngineError
from vera.parsing import parse_model_output
from vera.prompts import OUTPUT_SCHEMA, generation_messages
from vera.types import Task

GATE_SIZE = 10
MIN_OK = 9
MIN_TOK_S = 20.0
GATE_OPTIONS = ChatOptions(num_ctx=8192, num_predict=2048, temperature=0.7, seed=1,
                           keep_alive="30m")

_NS = 1_000_000_000
_GB = 1_000_000_000


@dataclass
class GateVerdict:
    passed: bool
    reasons: list[str]


def _ok(r: dict) -> bool:
    return r.get("error") is None and r.get("parse_error") is None and not r.get("truncated")


def _tok_s(r: dict) -> float | None:
    seconds = r.get("gen_seconds") or 0
    return r["completion_tokens"] / seconds if seconds > 0 else None


def evaluate_gate(results: list[dict]) -> GateVerdict:
    """Pasa con al menos MIN_OK respuestas parseadas y no truncadas de GATE_SIZE y una
    mediana de velocidad en caliente (sin la primera llamada) de al menos MIN_TOK_S."""
    failures: list[str] = []
    notes: list[str] = []
    if len(results) != GATE_SIZE:
        failures.append(f"se esperaban {GATE_SIZE} respuestas y hay {len(results)}")
    ok = sum(_ok(r) for r in results)
    truncated = sum(bool(r.get("truncated")) and r.get("error") is None for r in results)
    errors = sum(r.get("error") is not None for r in results)
    unparsed = sum(r.get("error") is None and not r.get("truncated")
                   and r.get("parse_error") is not None for r in results)
    detail = f"truncadas: {truncated}, sin parsear: {unparsed}, con error del motor: {errors}"
    line = f"{ok} de {len(results)} respuestas válidas ({detail}); se exigen {MIN_OK}"
    (notes if ok >= MIN_OK else failures).append(line)

    speeds = [s for r in results
              if r.get("warm") and r.get("error") is None and (s := _tok_s(r)) is not None]
    if not speeds:
        failures.append("no hay llamadas en caliente con las que medir la velocidad")
    else:
        speed = statistics.median(speeds)
        line = f"velocidad en caliente (mediana de {len(speeds)}): {speed:.1f} tok/s; mínimo {MIN_TOK_S:g}"
        (notes if speed >= MIN_TOK_S else failures).append(line)
    return GateVerdict(passed=not failures, reasons=failures + notes)


def run_gate(engine: ChatEngine, model: str, tasks: list[Task],
             options: ChatOptions = GATE_OPTIONS) -> list[dict]:
    """Una llamada de generación por tarea con el prompt y el esquema reales del experimento.
    gen_seconds = total - carga: incluye la evaluación del prompt (velocidad conservadora)."""
    out: list[dict] = []
    for index, task in enumerate(tasks):
        row = {"task_id": task.id, "warm": index > 0, "parse_error": None, "truncated": False,
               "completion_tokens": 0, "prompt_tokens": 0, "gen_seconds": 0.0,
               "load_seconds": 0.0, "error": None, "text": ""}
        try:
            r = engine.chat(generation_messages(task), model=model, options=options,
                            json_schema=OUTPUT_SCHEMA)
        except EngineError as exc:
            row["error"] = f"EngineError({exc.kind}): {exc}"
        else:
            row.update(parse_error=parse_model_output(r.text).error, truncated=r.truncated,
                       completion_tokens=r.completion_tokens, prompt_tokens=r.prompt_tokens,
                       gen_seconds=r.total_seconds - r.load_seconds,
                       load_seconds=r.load_seconds, text=r.text)
        out.append(row)
    return out


# --- Mediciones del motor ------------------------------------------------------------

def http_json(url: str, payload: dict | None = None, timeout: float = 900) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat_metrics(body: dict) -> dict:
    eval_s = body.get("eval_duration", 0) / _NS
    count = int(body.get("eval_count", 0))
    return {
        "load_s": body.get("load_duration", 0) / _NS,
        "prompt_tokens": int(body.get("prompt_eval_count", 0)),
        "prompt_eval_s": body.get("prompt_eval_duration", 0) / _NS,
        "completion_tokens": count,
        "eval_s": eval_s,
        "tok_s": count / eval_s if eval_s > 0 else None,
        "total_s": body.get("total_duration", 0) / _NS,
        "done_reason": body.get("done_reason"),
        "truncated": body.get("done_reason") == "length",
    }


def gpu_residency(ps: dict, model: str) -> dict | None:
    """Tamaño total y residente en GPU según /api/ps."""
    for m in ps.get("models", []):
        if model in (m.get("name"), m.get("model")):
            size, vram = m.get("size", 0), m.get("size_vram", 0)
            return {"size_gb": round(size / _GB, 2), "size_vram_gb": round(vram / _GB, 2),
                    "gpu_fraction": round(vram / size, 3) if size else None,
                    "context_length": m.get("context_length")}
    return None


def parse_nvidia_smi(text: str) -> tuple[int, int]:
    used, total = (int(x.strip()) for x in text.strip().splitlines()[0].split(","))
    return used, total


def nvidia_smi_memory() -> tuple[int, int]:
    """Memoria usada y total de la GPU en MiB."""
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                          "--format=csv,noheader,nounits"], capture_output=True, text=True,
                         timeout=30, check=True).stdout
    return parse_nvidia_smi(out)


def unload_and_wait(base_url: str, model: str, timeout_s: float = 60) -> dict | None:
    """Descarga el modelo y espera a que /api/ps deje de listarlo; devuelve la memoria final."""
    http_json(base_url + "/api/chat", {"model": model, "messages": [], "keep_alive": 0})
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if gpu_residency(http_json(base_url + "/api/ps"), model) is None:
            time.sleep(2)  # margen para que el controlador libere la memoria
            used, total = nvidia_smi_memory()
            return {"vram_used_mib": used, "vram_total_mib": total}
        time.sleep(1)
    return None


def measurement_payload(model: str, task: Task, seed: int) -> dict:
    """El payload de OllamaEngine.chat con el prompt real de generación de `task`."""
    return {"model": model, "messages": generation_messages(task), "stream": False,
            "think": False, "keep_alive": "30m", "format": OUTPUT_SCHEMA,
            "options": {"num_ctx": GATE_OPTIONS.num_ctx, "num_predict": GATE_OPTIONS.num_predict,
                        "temperature": GATE_OPTIONS.temperature, "seed": seed}}

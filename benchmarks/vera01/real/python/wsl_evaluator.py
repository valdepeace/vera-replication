"""Evalúa los programas candidatos dentro de WSL2 (los evaluadores de SimpleTES importan ``resource``).

El agente corre en Windows; solo la evaluación se delega a WSL2. Se sustituye en memoria
``dream_rsi.exploration.evaluate.run_evaluator``; el código oficial no se modifica.
El candidato se ejecuta en un proceso de WSL2 con ``timeout -s KILL`` (aislamiento de proceso,
no de sistema de ficheros: WSL2 ve /mnt/e).
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

DISTRO = "Ubuntu-24.04"
PYTHON = "~/poc-ante-venv/bin/python"


def to_wsl_path(p: str | Path) -> str:
    text = str(p).replace(chr(92), "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", text)
    if not m:
        raise ValueError(f"se esperaba una ruta absoluta de Windows: {p!r}")
    return f"/mnt/{m.group(1).lower()}/{m.group(2)}"


def _runner_file() -> Path:
    from dream_rsi.exploration.evaluate import _RUNNER

    path = Path(tempfile.gettempdir()) / "drsi_wsl_eval_runner.py"
    path.write_text(_RUNNER, encoding="utf-8")
    return path


def build_command(evaluator: Path, program: Path, *, timeout_sec: float, runner: Path) -> list[str]:
    q = lambda s: "'" + s.replace("'", "'\''") + "'"  # noqa: E731
    inner = (
        "export EVALUATOR_CONCURRENT_PROCESSES=1; "
        f"timeout -s KILL {math.ceil(timeout_sec)} {PYTHON} {q(to_wsl_path(runner))} "
        f"{q(to_wsl_path(evaluator))} {q(to_wsl_path(program))}"
    )
    return ["wsl.exe", "-d", DISTRO, "--cd", to_wsl_path(Path(evaluator).parent), "--", "bash", "-c", inner]


def run_evaluator_wsl(
    evaluator_path: Path,
    program_path: Path,
    *,
    timeout_sec: float = 600.0,
    python_executable: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    from dream_rsi.exploration.evaluate import _extract_score, _parse_metrics

    del python_executable, extra_env
    evaluator_path, program_path = Path(evaluator_path).resolve(), Path(program_path).resolve()
    if not evaluator_path.is_file():
        return {"error": f"evaluator not found: {evaluator_path}", "score": 0.0}
    if not program_path.is_file():
        return {"error": f"program not found: {program_path}", "score": 0.0}
    cmd = build_command(evaluator_path, program_path, timeout_sec=timeout_sec, runner=_runner_file())
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_sec + 30
        )
    except subprocess.TimeoutExpired:
        return {"error": f"evaluator timeout after {timeout_sec}s", "score": 0.0}
    except OSError as exc:
        return {"error": f"failed to spawn evaluator: {exc}", "score": 0.0}
    metrics = _parse_metrics(proc.stdout or "")
    if proc.returncode != 0 and "error" not in metrics:
        tail = (proc.stderr or proc.stdout or "")[-500:]
        metrics = {"error": f"evaluator exit {proc.returncode}: {tail}", **metrics}
    metrics["score"] = _extract_score(metrics)
    return metrics


def install() -> None:
    import dream_rsi.exploration.evaluate as ev

    ev.run_evaluator = run_evaluator_wsl

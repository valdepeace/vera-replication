"""Adaptador Node/node:test: dícese del juez que ejecuta el test generado con el
runner nativo sobre una copia temporal del proyecto, sin alterar el original."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

from vera.adapters.java_maven import run_killing_tree
from vera.audit import audit_node
from vera.types import AuditOutcome, Task, ValidationResult

MAX_DIAGNOSTIC = 3900
_TRUNCATED = "\n... [diagnostic truncated]"
_FALLBACK_LINES = 15
_LINE_CHARS = 300
_IGNORED = shutil.ignore_patterns(".git", "__pycache__")
_EXTENSIONS = (".mjs", ".js", ".cjs", ".mts", ".ts", ".cts")
# Un proceso abatido por el sistema devuelve un código negativo o desmesurado;
# el 9 es el de "opción inválida" de Node (p. ej. una versión sin --test).
_MAX_SANE_CODE = 255
_INFRA_CODES = {9}
# Ausencia del propio ejecutor: módulos integrados que Node no conoce u opción
# --test inexistente. Un import relativo roto es, en cambio, culpa del modelo.
_INFRA_MARKERS = (
    "ERR_UNKNOWN_BUILTIN_MODULE",
    "Cannot find module 'node:",
    'Cannot find module "node:',
    "bad option: --test",
)
_NOISE_RE = re.compile(r"^\s*(?:at .*node:|ℹ (?:tests|suites|pass|cancelled|skipped|todo|duration_ms))")


def _cap(text: str) -> str:
    if len(text) <= MAX_DIAGNOSTIC:
        return text
    cut = text.rfind("\n", 0, MAX_DIAGNOSTIC - len(_TRUNCATED))
    return text[: cut if cut > 0 else MAX_DIAGNOSTIC - len(_TRUNCATED)] + _TRUNCATED


def filter_node_output(output: str, returncode: int) -> str:
    """Conserva lo sustancial (aserciones, valores, trazas propias) y descarta el
    ruido interno de node; si nada queda, las últimas líneas con sustancia."""
    text = output.replace("\r\n", "\n")
    marker = text.find("failing tests:")
    if marker != -1:
        text = text[marker:]
    kept, seen = [], set()
    for line in text.split("\n"):
        line = line.rstrip()[:_LINE_CHARS]
        if not line.strip() or _NOISE_RE.match(line) or (line in seen and line.strip() != "}"):
            continue
        seen.add(line)
        kept.append(line)
    if kept:
        return "\n".join(kept)
    tail = [ln.strip()[:_LINE_CHARS] for ln in output.split("\n") if ln.strip()][-_FALLBACK_LINES:]
    return f"node --test failed with exit code {returncode}." + (
        "\nLast output lines:\n" + "\n".join(tail) if tail else "")


class NodeTestAdapter:
    def __init__(self, project_dir: Path, node: Path, timeout_s: float = 120,
                 runner: Callable = run_killing_tree) -> None:
        self.project_dir = Path(project_dir)
        self.node = Path(node)
        self.timeout_s = timeout_s
        self.runner = runner

    @staticmethod
    def _filename(task: Task) -> str:
        return task.test_name if task.test_name.endswith(_EXTENSIONS) else f"{task.test_name}.mjs"

    def validate(self, task: Task, code: str) -> ValidationResult:
        started = time.perf_counter()
        filename = self._filename(task)
        with tempfile.TemporaryDirectory(prefix="vera-node-", ignore_cleanup_errors=True) as tmp:
            work = Path(tmp) / "project"
            shutil.copytree(self.project_dir, work, ignore=_IGNORED)
            (work / filename).write_text(code, encoding="utf-8")
            cmd = [str(self.node), "--test", filename]
            try:
                proc = self.runner(cmd, cwd=work, timeout=self.timeout_s, text=True,
                                   encoding="utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                return ValidationResult(
                    passed=False, diagnostic=f"node --test timed out after {self.timeout_s:g} s",
                    seconds=time.perf_counter() - started, infra_failure=True,
                )
            except OSError as exc:
                return ValidationResult(
                    passed=False, diagnostic=_cap(f"node could not be started: {exc}"),
                    seconds=time.perf_counter() - started, infra_failure=True,
                )
        seconds = time.perf_counter() - started
        if proc.returncode == 0:
            return ValidationResult(passed=True, diagnostic="", seconds=seconds)
        output = proc.stdout or ""
        infra = (
            proc.returncode in _INFRA_CODES
            or proc.returncode < 0
            or proc.returncode > _MAX_SANE_CODE
            or any(marker in output for marker in _INFRA_MARKERS)
        )
        return ValidationResult(
            passed=False, diagnostic=_cap(filter_node_output(output, proc.returncode)),
            seconds=seconds, infra_failure=infra,
        )

    def audit(self, task: Task, code: str) -> AuditOutcome:
        return audit_node(code, task.focal_name)

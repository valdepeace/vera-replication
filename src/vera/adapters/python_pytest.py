"""Adaptador Python/pytest: dícese del juez que ejecuta el test generado sobre una
copia temporal del proyecto, de modo que el original jamás se altera."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

from vera.adapters.java_maven import run_killing_tree
from vera.audit import audit_python
from vera.types import AuditOutcome, Task, ValidationResult

MAX_DIAGNOSTIC = 3900
_TRUNCATED = "\n... [diagnostic truncated]"
_FALLBACK_LINES = 15
_LINE_CHARS = 300
_IGNORED = shutil.ignore_patterns(
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "*.pyc"
)
# Códigos de salida de pytest: 5 = ningún test recogido (veredicto del ejecutor
# que la auditoría clasificará); 3 = error interno; 4 = uso incorrecto.
_NO_TESTS = 5
_INFRA_CODES = {3, 4}
_USEFUL_RE = re.compile(
    r"^(?:E\s|>\s|FAILED\b|ERROR\b|\S+\.py:\d+:|=+ .*(?:failed|error|passed).* =+$"
    r"|\d+ (?:failed|passed|error))"
)


def _cap(text: str) -> str:
    if len(text) <= MAX_DIAGNOSTIC:
        return text
    cut = text.rfind("\n", 0, MAX_DIAGNOSTIC - len(_TRUNCATED))
    return text[: cut if cut > 0 else MAX_DIAGNOSTIC - len(_TRUNCATED)] + _TRUNCATED


def filter_pytest_output(output: str, returncode: int) -> str:
    lines = [ln.rstrip()[:_LINE_CHARS] for ln in output.replace("\r\n", "\n").split("\n")]
    kept, seen = [], set()
    for ln in lines:
        if ln and _USEFUL_RE.match(ln) and ln not in seen:
            seen.add(ln)
            kept.append(ln)
    if kept:
        return "\n".join(kept)
    tail = [ln for ln in lines if ln.strip()][-_FALLBACK_LINES:]
    return f"pytest failed with exit code {returncode}." + ("\nLast output lines:\n" + "\n".join(tail) if tail else "")


class PythonPytestAdapter:
    def __init__(self, project_dir: Path, python: Path, timeout_s: float = 120,
                 runner: Callable = run_killing_tree) -> None:
        self.project_dir = Path(project_dir)
        self.python = Path(python)
        self.timeout_s = timeout_s
        self.runner = runner

    @staticmethod
    def _filename(task: Task) -> str:
        return task.test_name if task.test_name.endswith(".py") else f"{task.test_name}.py"

    def validate(self, task: Task, code: str) -> ValidationResult:
        started = time.perf_counter()
        filename = self._filename(task)
        with tempfile.TemporaryDirectory(prefix="vera-py-", ignore_cleanup_errors=True) as tmp:
            work = Path(tmp) / "project"
            shutil.copytree(self.project_dir, work, ignore=_IGNORED)
            (work / filename).write_text(code, encoding="utf-8")
            cmd = [str(self.python), "-m", "pytest", "-q", "-p", "no:cacheprovider", filename]
            try:
                proc = self.runner(cmd, cwd=work, timeout=self.timeout_s, text=True,
                                   encoding="utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                return ValidationResult(
                    passed=False, diagnostic=f"pytest timed out after {self.timeout_s:g} s",
                    seconds=time.perf_counter() - started, infra_failure=True,
                )
        seconds = time.perf_counter() - started
        if proc.returncode in (0, _NO_TESTS):
            return ValidationResult(passed=True, diagnostic="", seconds=seconds)
        diagnostic = _cap(filter_pytest_output(proc.stdout or "", proc.returncode))
        return ValidationResult(passed=False, diagnostic=diagnostic, seconds=seconds,
                                infra_failure=proc.returncode in _INFRA_CODES)

    def audit(self, task: Task, code: str) -> AuditOutcome:
        return audit_python(code, task.focal_name)

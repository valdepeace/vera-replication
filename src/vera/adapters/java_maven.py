"""Adaptador Java/Maven: dícese del juez que compila y ejecuta el test generado
dentro del checkout fijado de Commons Lang, sin dejar en él rastro alguno."""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Callable

from vera.audit import audit_java
from vera.types import AuditOutcome, Task, ValidationResult

GENERATED_DIR = Path("src/test/java/org/generated")
MAX_DIAGNOSTIC = 3900
_TRUNCATED = "\n... [diagnostic truncated]"

REMOVE_ATTEMPTS = 5
REMOVE_DELAY_S = 0.5

# Cabe señalar que estas huellas delatan un fallo del entorno (repositorio local
# incompleto, red) y nunca un defecto del test generado. Solo se buscan en las
# líneas "Failed to execute goal", pues un test podría imprimirlas por su cuenta;
# y una JVM que termina sin despedirse (System.exit) es, ciertamente, culpa del test.
_INFRA_MARKERS = (
    "Could not resolve dependencies",
    "could not be resolved",
    "Cannot access",
    "Could not transfer artifact",
)
_GOAL_FAILURE = "[ERROR] Failed to execute goal"
_FALLBACK_LINES = 10
_FALLBACK_LINE_CHARS = 300
_BOILERPLATE_RE = re.compile(
    r"^(?:-> \[Help|To see the full stack trace|Re-run Maven using|For more information about"
    r"|\[Help \d+\]|See .*surefire-reports|See dump files)"
)
_ERROR_PREFIX = "[ERROR]"


class GeneratedFileNotRemovedError(RuntimeError):
    """El test generado no pudo retirarse del checkout objetivo."""


def _kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)


def run_killing_tree(cmd, *, timeout=None, **kwargs) -> subprocess.CompletedProcess:
    """Equivalente de subprocess.run que, al agotarse el tiempo, abate el árbol de
    procesos entero: en Windows, mvn.cmd deja una JVM hija que retendría las tuberías."""
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs) as proc:
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc.pid)
            proc.kill()
            proc.communicate()
            raise
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout=out, stderr="")


def _cap(text: str) -> str:
    if len(text) <= MAX_DIAGNOSTIC:
        return text
    cut = text.rfind("\n", 0, MAX_DIAGNOSTIC - len(_TRUNCATED))
    return text[: cut if cut > 0 else MAX_DIAGNOSTIC - len(_TRUNCATED)] + _TRUNCATED


def _fallback_diagnostic(output: str, returncode: int) -> str:
    """Mensaje explícito y las últimas líneas con sustancia, sin ruido de Maven."""
    meaningful = [
        line.strip()[:_FALLBACK_LINE_CHARS]
        for line in output.replace("\r\n", "\n").split("\n")
        if line.strip() and not line.startswith(("[INFO]", "[WARNING]"))
        and not line.strip().startswith("at ")
    ]
    head = f"Maven failed with exit code {returncode} and printed no [ERROR] lines."
    tail = meaningful[-_FALLBACK_LINES:]
    return head + ("\nLast output lines:\n" + "\n".join(tail) if tail else "")


def _is_infra_failure(output: str) -> bool:
    goal_lines = [
        line for line in output.replace("\r\n", "\n").split("\n") if line.startswith(_GOAL_FAILURE)
    ]
    return any(marker in line for line in goal_lines for marker in _INFRA_MARKERS)


def _remove_generated(target: Path, created_dir: bool) -> None:
    """Retira el test generado con reintentos (bloqueos transitorios de Windows);
    si persiste, alza un error claro: jamás debe quedar en el checkout."""
    for attempt in range(REMOVE_ATTEMPTS):
        try:
            target.unlink(missing_ok=True)
            break
        except OSError:
            if attempt < REMOVE_ATTEMPTS - 1:
                time.sleep(REMOVE_DELAY_S)
    if target.exists():
        raise GeneratedFileNotRemovedError(
            f"generated test could not be removed from the target checkout: {target}"
        )
    if created_dir:
        try:
            target.parent.rmdir()
        except OSError:
            pass  # no vacío: alberga ficheros ajenos que no nos incumben


def filter_maven_output(output: str) -> str:
    """Conserva las líneas [ERROR] útiles y su contexto inmediato (mensaje de la
    excepción, símbolo y ubicación, marcos del test generado), sin repeticiones."""
    kept: list[str] = []
    seen: set[str] = set()
    in_context = False
    for raw in output.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if line.startswith(_ERROR_PREFIX):
            body = line[len(_ERROR_PREFIX):].strip()
            in_context = bool(body) and not _BOILERPLATE_RE.match(body)
            if not in_context:
                continue
        elif line.startswith("[") or not line.strip():
            in_context = False
            continue
        elif not in_context:
            continue
        else:
            body = line.strip()
            if body.startswith("at ") and "org.generated" not in body:
                continue
        if body in seen:
            continue
        seen.add(body)
        kept.append(line)
    return "\n".join(kept)


class JavaMavenAdapter:
    def __init__(self, repo: Path, mvn: Path, m2: Path, timeout_s: float = 300,
                 runner: Callable = run_killing_tree) -> None:
        self.repo = Path(repo)
        self.mvn = Path(mvn)
        self.m2 = Path(m2)
        self.timeout_s = timeout_s
        self.runner = runner

    def _command(self, test_name: str) -> list[str]:
        # La comprobación de licencias (RAT) rechazaría el fichero generado,
        # que ciertamente carece de cabecera Apache: se omite.
        return [
            str(self.mvn), "-o", "-B", "-q", f"-Dmaven.repo.local={self.m2}",
            "-Drat.skip=true", f"-Dtest={test_name}",
            "-Dsurefire.failIfNoSpecifiedTests=false", "test",
        ]

    def validate(self, task: Task, code: str) -> ValidationResult:
        target_dir = self.repo / GENERATED_DIR
        target = target_dir / f"{task.test_name}.java"
        started = time.perf_counter()
        created_dir = not target_dir.exists()
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            target.write_text(code, encoding="utf-8")
            try:
                proc = self.runner(
                    self._command(task.test_name), cwd=self.repo, timeout=self.timeout_s,
                    text=True, encoding="utf-8", errors="replace",
                )
            except subprocess.TimeoutExpired:
                return ValidationResult(
                    passed=False,
                    diagnostic=f"Maven timed out after {self.timeout_s:g} s",
                    seconds=time.perf_counter() - started,
                    infra_failure=True,
                )
        finally:
            _remove_generated(target, created_dir)

        seconds = time.perf_counter() - started
        output = proc.stdout or ""
        if proc.returncode == 0:
            return ValidationResult(passed=True, diagnostic="", seconds=seconds)
        diagnostic = filter_maven_output(output) or _fallback_diagnostic(output, proc.returncode)
        infra = _is_infra_failure(output)
        return ValidationResult(
            passed=False, diagnostic=_cap(diagnostic), seconds=seconds, infra_failure=infra
        )

    def audit(self, task: Task, code: str) -> AuditOutcome:
        # El auditor espera el nombre simple de la clase contenedora.
        return audit_java(code, task.focal_name, task.container.rsplit(".", 1)[-1])

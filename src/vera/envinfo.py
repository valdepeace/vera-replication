"""Recogida del manifiesto del entorno de VERA-01 (versiones y digests de modelos)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable

from vera.adapters.java_maven import JavaMavenAdapter, run_killing_tree
from vera.types import Task

COMMONS_LANG_COMMIT = "89bb30909bf873d75f5e06d144f9b2e72d74c076"
OLLAMA_URLS = ("http://127.0.0.1:11434", "http://127.0.0.1:11435")
MAVEN_BIN = "E:/vera-data/maven/bin/mvn.cmd"
COMMONS_LANG_DIR = "E:/vera-data/commons-lang"
M2_DIR = "E:/vera-data/m2"


def parse_mvn_version(output: str) -> str:
    """Extrae la versión semántica de la primera línea de `mvn -v`."""
    primera = output.strip().splitlines()[0] if output.strip() else ""
    m = re.search(r"Apache Maven (\d+\.\d+\.\d+)", primera)
    return m.group(1) if m else ""


def _run(cmd: list[str], cwd: str | None = None) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()


def _http_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.load(resp)


def _safe(fn, *args, default=""):
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001 - un dato ausente no debe abortar el manifiesto
        return default


def collect_env_manifest(model_names: list[str]) -> dict:
    """Reúne versiones, commit fijado y digest de cada modelo pedido."""
    java = _safe(_run, ["java", "-version"])
    digests: dict[str, str | None] = {n: None for n in model_names}
    ollama_version = ""
    for base in OLLAMA_URLS:
        ollama_version = ollama_version or _safe(lambda b=base: _http_json(b + "/api/version")["version"])
        tags = _safe(lambda b=base: _http_json(b + "/api/tags"), default={})
        for modelo in tags.get("models", []):
            if modelo.get("name") in digests and digests[modelo["name"]] is None:
                digests[modelo["name"]] = modelo.get("digest")
    return {
        "python": sys.version.split()[0],
        "java": java.splitlines()[0] if java else "",
        "maven": parse_mvn_version(_safe(_run, [MAVEN_BIN, "-v"])),
        "commons_lang_commit": _safe(_run, ["git", "rev-parse", "HEAD"], COMMONS_LANG_DIR),
        "ollama_version": ollama_version,
        "gpu": _safe(
            _run,
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
        ),
        "models": digests,
    }


ENV_CHECK_TEST = "VeraEnvCheckTest"
_ENV_CHECK_CODE = (
    "package org.generated;\n"
    "import static org.junit.jupiter.api.Assertions.assertTrue;\n"
    "import org.junit.jupiter.api.Test;\n"
    f"public class {ENV_CHECK_TEST} {{\n"
    "  @Test void runs() { assertTrue(true); }\n"
    "}\n"
)
_MISSING_ARTIFACT_RES = (
    re.compile(r"the artifact (\S+) has not been downloaded"),
    re.compile(r"could not be resolved: (\S+)"),
    re.compile(r"Could not resolve dependencies for project \S+: (.+?)(?: -> |$)", re.M),
)


def _tests_in_report(report: Path) -> int:
    if not report.is_file():
        return 0
    m = re.search(r'\btests="(\d+)"', report.read_text(encoding="utf-8", errors="replace"))
    return int(m.group(1)) if m else 0


def check_surefire_offline(repo: Path, mvn: Path, m2: Path,
                           runner: Callable = run_killing_tree) -> str | None:
    """Ejecuta, sin red y con el mismo comando del adaptador, un test JUnit 5 trivial.

    Devuelve None si Surefire ejecutó exactamente un test, o el motivo del fallo
    (nombrando el artefacto ausente del repositorio local cuando es el caso).
    El adaptador retira el fichero en su finally."""
    repo = Path(repo)
    report = repo / "target/surefire-reports" / f"TEST-org.generated.{ENV_CHECK_TEST}.xml"
    report.unlink(missing_ok=True)
    adapter = JavaMavenAdapter(repo=repo, mvn=Path(mvn), m2=Path(m2), runner=runner)
    task = Task(id="env-check", language="java", project="commons-lang", focal_name="",
                focal_source="", container="", test_name=ENV_CHECK_TEST, import_hint="")
    result = adapter.validate(task, _ENV_CHECK_CODE)
    if not result.passed:
        for pattern in _MISSING_ARTIFACT_RES:
            m = pattern.search(result.diagnostic)
            if m:
                return (f"falta en el repositorio local de Maven ({m2}) el artefacto {m.group(1)}; "
                        "hace falta un calentamiento con red:\n" + result.diagnostic)
        return "la validación offline con Surefire falló:\n" + result.diagnostic
    executed = _tests_in_report(report)
    if executed != 1:
        return (f"Surefire terminó con código 0 pero no consta 'Tests run: 1' "
                f"(tests ejecutados según {report.name}: {executed})")
    return None

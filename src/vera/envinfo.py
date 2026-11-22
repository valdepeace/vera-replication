"""Recogida del manifiesto del entorno de VERA-01 (versiones y digests de modelos)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request

COMMONS_LANG_COMMIT = "89bb30909bf873d75f5e06d144f9b2e72d74c076"
OLLAMA_URLS = ("http://127.0.0.1:11434", "http://127.0.0.1:11435")
MAVEN_BIN = "E:/vera-data/maven/bin/mvn.cmd"
COMMONS_LANG_DIR = "E:/vera-data/commons-lang"


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

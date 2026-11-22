"""Ejecución confinada de scripts del modelo en WSL2 con bubblewrap (herramienta ``run_python``).

Cada ejecución:
  * trabaja sobre una COPIA temporal del directorio del intento (nada vuelve al nodo real);
  * no tiene red (``--unshare-net``), ni ve los discos de Windows (/mnt no se monta), ni el evaluador;
  * ve el sistema y el venv en solo lectura, con tiempo máximo (``timeout -s KILL``) y memoria acotada;
  * muere con su proceso padre (``--die-with-parent``).
Límite honesto: es aislamiento de proceso con bubblewrap, no una máquina virtual.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

from wsl_evaluator import DISTRO, to_wsl_path

MAX_OUTPUT_CHARS = 8_000
MEM_LIMIT_KB = 8 * 1024 * 1024  # 8 GB de espacio de direcciones


def truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n[salida truncada: {len(text)} caracteres en total]"


def build_command(node_dir: Path, script_rel: str, *, timeout_sec: float) -> list[str]:
    src = to_wsl_path(Path(node_dir).resolve())
    q = lambda s: "'" + s.replace("'", "'\''") + "'"  # noqa: E731
    inner = (
        'w=$(mktemp -d) && trap "rm -rf $w" EXIT && '
        f"cp -r {q(src)}/. $w/ && "
        f"ulimit -v {MEM_LIMIT_KB} && "
        f"timeout -s KILL {math.ceil(timeout_sec)} "
        "bwrap --unshare-net --unshare-pid --unshare-ipc --die-with-parent "
        "--ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 "
        '--ro-bind "$HOME/poc-ante-venv" "$HOME/poc-ante-venv" '
        "--proc /proc --dev /dev --tmpfs /tmp --bind $w /work --chdir /work "
        "--setenv OPENBLAS_NUM_THREADS 1 --setenv OMP_NUM_THREADS 1 --setenv HOME /work "
        f'"$HOME/poc-ante-venv/bin/python" {q(script_rel)} 2>&1'
    )
    # El último elemento es el script: se envía por stdin (``bash -s``) para que ``wsl.exe`` no
    # expanda las variables ``$w``/``$HOME`` con su propia shell antes de que las vea bash.
    return ["wsl.exe", "-d", DISTRO, "--", "bash", "-s", inner]


def run_python_sandboxed(node_dir: Path, script_rel: str, timeout_sec: float) -> str:
    cmd = build_command(node_dir, script_rel, timeout_sec=timeout_sec)
    script = cmd.pop()
    try:
        p = subprocess.run(
            cmd, input=script, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_sec + 30
        )
    except subprocess.TimeoutExpired:
        return f"error: timeout tras {timeout_sec}s"
    except OSError as exc:
        return f"error: no se pudo lanzar el sandbox: {exc}"
    out = (p.stdout or "").replace("\x00", "")
    if p.returncode == 137:
        out += f"\n[proceso terminado: timeout de {timeout_sec}s]"
    elif p.returncode != 0:
        out += f"\n[código de salida {p.returncode}]"
    return truncate(out) or "(sin salida)"

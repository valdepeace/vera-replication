"""Comprobación de sensibilidad: dícese de la prueba de que la suite propia de un
proyecto detecta una mutación manual, requisito para fijarlo como objeto de estudio."""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

DEFAULT_TIMEOUT_S = 600.0


def mutation_detected(
    project_dir: Path,
    file: Path,
    mutation: tuple[str, str],
    test_cmd: list[str],
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> bool:
    """Aplica el reemplazo `mutation` a `file`, ejecuta `test_cmd` en `project_dir` y
    devuelve True si la suite falla. El fichero se restaura siempre, byte a byte.

    Lanza ValueError si el patrón no figura en el fichero (nada se escribe) y deja
    propagar los errores de arranque o de tiempo agotado tras restaurarlo.
    """
    file = Path(file)
    old, new = mutation
    original = file.read_bytes()
    text = original.decode("utf-8")
    if "\r\n" in text:  # el patrón se escribe con saltos \n, el fichero puede usar \r\n
        old, new = (s.replace("\r\n", "\n").replace("\n", "\r\n") for s in (old, new))
    if old not in text:
        raise ValueError(f"el patrón {old!r} no figura en {file}")
    try:
        file.write_bytes(text.replace(old, new, 1).encode("utf-8"))
        proc = subprocess.run(
            test_cmd, cwd=project_dir, capture_output=True, timeout=timeout_s, check=False,
        )
        return proc.returncode != 0
    finally:
        file.write_bytes(original)


def extract_python_function(source: str, name: str) -> str:
    """Firma, decoradores y cuerpo de la función de primer nivel `name`, sin su docstring
    (los ejemplos de la documentación desvelarían el oráculo)."""
    lines = source.replace("\r\n", "\n").split("\n")
    hits = [n for n in ast.parse("\n".join(lines)).body
            if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(hits) != 1:
        raise ValueError(f"función {name!r}: {len(hits)} coincidencias")
    node = hits[0]
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    first = node.body[0]
    has_doc = (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
               and isinstance(first.value.value, str))
    if has_doc and len(node.body) == 1:
        raise ValueError(f"función {name!r}: solo contiene el docstring")
    body_start = node.body[1].lineno if has_doc else first.lineno
    header = lines[start - 1:first.lineno - 1]
    return "\n".join(header + lines[body_start - 1:node.end_lineno]).rstrip()


_ESLINT_RE = re.compile(r"^\s*(?:/\*|//)\s*eslint")


def extract_js_module_body(source: str) -> str:
    """Módulo ES sin importaciones ni directivas de eslint: las constantes del módulo
    (expresiones regulares, opciones) se conservan, pues forman parte del comportamiento."""
    kept = [ln for ln in source.replace("\r\n", "\n").split("\n")
            if not ln.startswith("import ") and not _ESLINT_RE.match(ln)]
    return "\n".join(kept).strip()

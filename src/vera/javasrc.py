"""Extraccion de metodos focales de codigo fuente Java."""
from __future__ import annotations

import re
from pathlib import Path

from vera.types import Task

PROJECT = "commons-lang"
LANG3 = "src/main/java/org/apache/commons/lang3"

# Los veinte metodos focales; los diez primeros (StringUtils) son el bloque determinista.
METHODS: list[tuple[str, str]] = [
    ("StringUtils", "isEmpty(CharSequence)"),
    ("StringUtils", "isBlank(CharSequence)"),
    ("StringUtils", "isNotEmpty(CharSequence)"),
    ("StringUtils", "isNotBlank(CharSequence)"),
    ("StringUtils", "length(CharSequence)"),
    ("StringUtils", "trim(String)"),
    ("StringUtils", "trimToEmpty(String)"),
    ("StringUtils", "trimToNull(String)"),
    ("StringUtils", "equals(CharSequence, CharSequence)"),
    ("StringUtils", "equalsIgnoreCase(CharSequence, CharSequence)"),
    ("CharUtils", "isAscii(char)"),
    ("CharUtils", "isAsciiAlpha(char)"),
    ("CharUtils", "isAsciiNumeric(char)"),
    ("CharUtils", "toIntValue(char)"),
    ("CharUtils", "toChar(Character, char)"),
    ("BooleanUtils", "isTrue(Boolean)"),
    ("BooleanUtils", "negate(Boolean)"),
    ("BooleanUtils", "toBoolean(String)"),
    ("BooleanUtils", "and(boolean...)"),
    ("BooleanUtils", "toInteger(boolean)"),
]


def _mask(src: str) -> str:
    """Sustituye por espacios comentarios, cadenas y caracteres (conserva longitud y saltos)."""
    out = list(src)
    i, n = 0, len(src)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        two = src[i:i + 2]
        if two == "//":
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif two == "/*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif src.startswith('"""', i):
            j = i + 3
            while j < n and not src.startswith('"""', j):
                j += 2 if src[j] == "\\" else 1
            j = min(n, j + 3)
            blank(i, j)
            i = j
        elif src[i] in "\"'":
            q = src[i]
            j = i + 1
            while j < n and src[j] != q and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            j = min(n, j + 1)
            blank(i, j)
            i = j
        else:
            i += 1
    return "".join(out)


def _split_top(text: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return [p.strip() for p in parts]


def _norm_type(t: str) -> str:
    t = re.sub(r"\s*\.\.\.\s*", "...", t)
    t = re.sub(r"\s*\[\s*\]", "[]", t)
    return re.sub(r"\s+", " ", t).strip()


def _param_types(params: str) -> list[str]:
    """Tipos de una lista de parametros declarados (con nombres, final y anotaciones)."""
    types = []
    for p in _split_top(params):
        p = re.sub(r"@\w+(\([^)]*\))?\s*", "", p)
        p = re.sub(r"\bfinal\b\s*", "", p).strip()
        m = re.match(r"^(.*?)\s*\b\w+\s*(\[\s*\])*$", p, re.S)
        types.append(_norm_type(m.group(1) if m else p))
    return types


def _wanted(signature: str) -> tuple[str, list[str]]:
    m = re.fullmatch(r"\s*(\w+)\s*\((.*)\)\s*", signature, re.S)
    if not m:
        raise ValueError(f"firma mal formada: {signature!r}")
    return m.group(1), [_norm_type(t) for t in _split_top(m.group(2))]


def extract_method(source: str, signature: str) -> str:
    """Devuelve firma y cuerpo (sin Javadoc ni comentarios previos) del metodo pedido.

    `signature` es nombre y tipos de parametro, p. ej. "isEmpty(CharSequence)".
    """
    name, wanted = _wanted(signature)
    masked = _mask(source)
    pattern = re.compile(
        r"(?<![\w.])" + re.escape(name) + r"\s*\(([^()]*)\)\s*(?:throws\s+[\w.,\s]+?)?\s*\{"
    )
    hits = [m for m in pattern.finditer(masked) if _param_types(m.group(1)) == wanted]
    if not hits:
        raise ValueError(f"firma no encontrada: {signature}")
    if len(hits) > 1:
        raise ValueError(f"firma ambigua: {signature}")
    m = hits[0]
    start = max(masked.rfind(c, 0, m.start()) for c in ";{}") + 1
    while masked[start].isspace():
        start += 1
    depth, i = 0, m.end() - 1
    while i < len(masked):
        if masked[i] == "{":
            depth += 1
        elif masked[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    raise ValueError(f"llaves sin cerrar en {signature}")


def build_tasks(repo: Path | str, methods: list[tuple[str, str]] = METHODS) -> list[Task]:
    repo = Path(repo)
    tasks = []
    for cls, sig in methods:
        text = (repo / LANG3 / f"{cls}.java").read_text(encoding="utf-8")
        name = sig.split("(", 1)[0]
        tasks.append(
            Task(
                id=f"java-{cls}-{name}",
                language="java",
                project=PROJECT,
                focal_name=name,
                focal_source=extract_method(text, sig),
                container=cls,
                test_name=f"Generated_{cls}_{name}_Test",
                import_hint=f"import org.apache.commons.lang3.{cls};",
            )
        )
    return tasks

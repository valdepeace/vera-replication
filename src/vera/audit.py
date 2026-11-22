"""Auditoría de los éxitos: dícese del juicio que decide si un test aceptado
ejerce de veras el método focal. Cinco resultados excluyentes, de los cuales
solo REAL cuenta como éxito sustantivo."""
from __future__ import annotations

import re

from vera.types import AuditOutcome

_CLASS_RE = re.compile(r"\bclass\s+[A-Za-z_$][\w$]*")
_TEST_ANNOTATION_RE = re.compile(
    r"@(?:[\w$]+\.)*(?:Test|ParameterizedTest|RepeatedTest)\b"
)
# Cabe señalar que la cabecera de un método termina en ")" (con un "throws"
# opcional) justo antes de su llave; así se esquivan las llaves que viven
# dentro de los argumentos de anotaciones como @ValueSource(strings = {...}).
_METHOD_OPEN_RE = re.compile(
    r"\)\s*(?:throws\s+[\w$.]+(?:\s*,\s*[\w$.]+)*\s*)?\{"
)
_ASSERT_RE = re.compile(r"(?<![\w$])assert\w*\s*\(")
_ASSIGN_RE = re.compile(r"(?<![\w$])([A-Za-z_$][\w$]*)\s*=(?!=)")


def _strip_java(code: str) -> str:
    """Elimina comentarios y vacía los literales de cadena y de carácter."""
    out: list[str] = []
    i, n = 0, len(code)
    while i < n:
        if code.startswith("//", i):
            end = code.find("\n", i)
            i = n if end == -1 else end
        elif code.startswith("/*", i):
            end = code.find("*/", i + 2)
            out.append(" ")
            i = n if end == -1 else end + 2
        elif code.startswith('"""', i):
            end = code.find('"""', i + 3)
            out.append('""')
            i = n if end == -1 else end + 3
        elif code[i] in "\"'":
            quote = code[i]
            j = i + 1
            while j < n and code[j] != quote and code[j] != "\n":
                j += 2 if code[j] == "\\" else 1
            out.append(quote * 2)
            i = j + 1
        else:
            out.append(code[i])
            i += 1
    return "".join(out)


def _matching(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """Índice del cierre que empareja la apertura en start (o el final)."""
    depth = 0
    for k in range(start, len(text)):
        if text[k] == open_ch:
            depth += 1
        elif text[k] == close_ch:
            depth -= 1
            if depth == 0:
                return k
    return len(text)


def _test_bodies(code: str) -> list[str]:
    """Cuerpos de los métodos anotados como test, sin duplicados."""
    bodies: list[str] = []
    seen: set[int] = set()
    for ann in _TEST_ANNOTATION_RE.finditer(code):
        head = _METHOD_OPEN_RE.search(code, ann.end())
        if head is None:
            continue
        open_idx = head.end() - 1
        if open_idx in seen:
            continue
        seen.add(open_idx)
        bodies.append(code[open_idx + 1 : _matching(code, open_idx, "{", "}")])
    return bodies


def _assertions(body: str) -> list[tuple[int, str]]:
    """Posición y argumentos de cada llamada assert*(...)."""
    found = []
    for m in _ASSERT_RE.finditer(body):
        open_idx = m.end() - 1
        found.append((m.start(), body[open_idx + 1 : _matching(body, open_idx, "(", ")")]))
    return found


def _focal_call_re(focal_name: str, container: str) -> re.Pattern[str]:
    focal = re.escape(focal_name)
    owner = re.escape(container)
    return re.compile(
        rf"(?:(?<![\w$]){owner}\s*\.\s*|(?<![\w$.]))(?<![\w$]){focal}\s*\("
        rf"|(?<![\w$]){owner}\s*::\s*{focal}(?![\w$])"
    )


def _focal_variables(body: str, focal_call: re.Pattern[str]) -> list[tuple[int, str]]:
    """Variables a las que se asigna una expresión con la llamada focal."""
    result = []
    for m in _ASSIGN_RE.finditer(body):
        end = body.find(";", m.end())
        rhs = body[m.end() : len(body) if end == -1 else end]
        if focal_call.search(rhs):
            result.append((m.end(), m.group(1)))
    return result


def audit_java(code: str, focal_name: str, container: str) -> AuditOutcome:
    """Clasifica un test Java en las cinco categorías de la tesis."""
    clean = _strip_java(code or "")
    if not _CLASS_RE.search(clean):
        return AuditOutcome.EMPTY
    bodies = _test_bodies(clean)
    if not bodies:
        return AuditOutcome.TEST_FREE
    per_method = [(body, _assertions(body)) for body in bodies]
    if not any(asserts for _, asserts in per_method):
        return AuditOutcome.ASSERTION_FREE
    focal_call = _focal_call_re(focal_name, container)
    for body, asserts in per_method:
        if any(focal_call.search(args) for _, args in asserts):
            return AuditOutcome.REAL
        # Salto de variable: un único paso de flujo de datos dentro del mismo
        # método, siempre que la aserción venga tras la asignación.
        for assigned_at, name in _focal_variables(body, focal_call):
            used = re.compile(rf"(?<![\w$.]){re.escape(name)}(?![\w$])")
            if any(pos >= assigned_at and used.search(args) for pos, args in asserts):
                return AuditOutcome.REAL
    return AuditOutcome.NO_FOCAL

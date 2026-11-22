"""Auditoría de los éxitos: dícese del juicio que decide si un test aceptado
ejerce de veras el método focal. Cinco resultados excluyentes, de los cuales
solo REAL cuenta como éxito sustantivo."""
from __future__ import annotations

import ast
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


_DEF_RE = re.compile(r"^\s*(?:async\s+def|def|class)\s", re.MULTILINE)


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _calls_focal(node: ast.AST, focal_name: str) -> bool:
    return any(
        isinstance(n, ast.Call) and _call_name(n.func) == focal_name for n in ast.walk(node)
    )


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _local_names(target: ast.expr) -> set[str]:
    """Variables locales ligadas por un destino: nombres simples y su
    desempaquetado; jamás atributos ni subíndices (self.x no es una local)."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_local_names(e) for e in target.elts))
    if isinstance(target, ast.Starred):
        return _local_names(target.value)
    return set()


def _is_raises(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and _call_name(node.func) == "raises"


def _is_self_assert(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.startswith("assert")
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    )


def _collected_tests(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Funciones que pytest registraría: test* de módulo y test* de clases Test*
    o derivadas de TestCase."""
    func = (ast.FunctionDef, ast.AsyncFunctionDef)
    tests = [n for n in tree.body if isinstance(n, func) and n.name.startswith("test")]
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        bases = {_call_name(b) for b in cls.bases}
        if cls.name.startswith("Test") or "TestCase" in bases:
            tests += [n for n in cls.body if isinstance(n, func) and n.name.startswith("test")]
    return tests


def _python_checks(test: ast.AST) -> list[tuple[int, ast.AST]]:
    """Aserciones de un test con su posición: assert, self.assert*() y los
    bloques with pytest.raises (cuyo cuerpo es lo aseverado)."""
    found: list[tuple[int, ast.AST]] = []
    for n in ast.walk(test):
        if isinstance(n, ast.Assert):
            found.append((n.lineno, n.test))
        elif _is_self_assert(n):
            found.append((n.lineno, n))
        elif isinstance(n, (ast.With, ast.AsyncWith)) and any(
            _is_raises(item.context_expr) for item in n.items
        ):
            found.append((n.lineno, n))
    return found


def audit_python(code: str, focal_name: str) -> AuditOutcome:
    """Clasifica un test Python en las cinco categorías de la tesis."""
    code = code or ""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Cabe señalar que lo ininteligible no se registra: sin definiciones es
        # vacío; con ellas, el test jamás llegaría a registrarse.
        return AuditOutcome.TEST_FREE if _DEF_RE.search(code) else AuditOutcome.EMPTY
    if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
               for n in ast.walk(tree)):
        return AuditOutcome.EMPTY
    tests = _collected_tests(tree)
    if not tests:
        return AuditOutcome.TEST_FREE
    per_test = [(t, _python_checks(t)) for t in tests]
    if not any(checks for _, checks in per_test):
        return AuditOutcome.ASSERTION_FREE
    for test, checks in per_test:
        if any(_calls_focal(node, focal_name) for _, node in checks):
            return AuditOutcome.REAL
        # Salto de variable: un solo paso de flujo de datos dentro del mismo test.
        for n in ast.walk(test):
            if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is not None \
                    and _calls_focal(n.value, focal_name):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                assigned = set().union(*(_local_names(t) for t in targets))
                end = getattr(n, "end_lineno", n.lineno)
                if any(pos > end and assigned & _names(node) for pos, node in checks):
                    return AuditOutcome.REAL
    return AuditOutcome.NO_FOCAL


# ---------------------------------------------------------------------------
# Node: análisis textual (sin dependencias) tras quitar comentarios y cadenas.
# ---------------------------------------------------------------------------
_JS_IDENT = r"[A-Za-z_$][\w$]*"
_JS_IMPORT_RE = re.compile(
    r"\bimport\s*(?:([^;'\"]*?)\s*from\s*)?(['\"])([^'\"\n]*)\2\s*;?"
)
_JS_REQUIRE_RE = re.compile(
    rf"\b(?:const|let|var)\s+(\{{[^}}]*\}}|{_JS_IDENT})\s*=\s*require\s*\(\s*(['\"])([^'\"\n]*)\2\s*\)\s*;?"
)
_JS_TEST_KINDS = {"test": "test", "it": "test", "describe": "suite", "suite": "suite"}
_JS_ASSERT_MODULES = {"node:assert", "node:assert/strict", "assert", "assert/strict"}


def _strip_js(code: str, keep_strings: bool = False) -> str:
    """Elimina comentarios y, salvo que se pida lo contrario, vacía las cadenas
    y las plantillas (las posiciones se conservan en lo posible)."""
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
        elif code[i] in "\"'`":
            quote = code[i]
            j = i + 1
            while j < n and code[j] != quote and (quote == "`" or code[j] != "\n"):
                j += 2 if code[j] == "\\" else 1
            out.append(code[i : j + 1] if keep_strings else quote * 2)
            i = j + 1
        else:
            out.append(code[i])
            i += 1
    return "".join(out)


def _split_names(clause: str) -> list[tuple[str, str]]:
    """Pares (importado, local) de una cláusula entre llaves: 'a, b as c'."""
    pairs = []
    for part in clause.strip().strip("{}").split(","):
        bits = re.split(r"\s+as\s+|\s*:\s*", part.strip())
        if bits and bits[0]:
            pairs.append((bits[0], bits[-1]))
    return pairs


def _js_bindings(raw: str, module_ok) -> list[tuple[str, str, str]]:
    """Enlaces de los módulos pedidos: (forma, importado, local), con forma en
    default, namespace o named."""
    found: list[tuple[str, str, str]] = []
    for m in _JS_IMPORT_RE.finditer(raw):
        clause, spec = (m.group(1) or "").strip(), m.group(3)
        if not clause or not module_ok(spec):
            continue
        brace = re.search(r"\{[^}]*\}", clause)
        if brace:
            found += [("named", a, b) for a, b in _split_names(brace.group(0))]
            clause = clause.replace(brace.group(0), " ")
        ns = re.search(rf"\*\s*as\s+({_JS_IDENT})", clause)
        if ns:
            found.append(("namespace", "*", ns.group(1)))
            clause = clause.replace(ns.group(0), " ")
        default = re.search(_JS_IDENT, clause)
        if default:
            found.append(("default", "default", default.group(0)))
    for m in _JS_REQUIRE_RE.finditer(raw):
        if not module_ok(m.group(3)):
            continue
        target = m.group(1)
        if target.startswith("{"):
            found += [("named", a, b) for a, b in _split_names(target)]
        else:
            found.append(("default", "default", target))
    return found


def _js_registration_res(raw: str) -> list[tuple[str, re.Pattern[str]]]:
    """Patrones de las llamadas que registran tests o suites en node:test."""
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for form, imported, local in _js_bindings(raw, lambda s: s == "node:test"):
        name = re.escape(local)
        if form == "named" and imported in _JS_TEST_KINDS:
            patterns.append((_JS_TEST_KINDS[imported],
                             re.compile(rf"(?<![\w$.]){name}(?:\s*\.\s*only)?\s*\(")))
        elif form in ("default", "namespace"):
            if form == "default":
                patterns.append(("test", re.compile(rf"(?<![\w$.]){name}(?:\s*\.\s*only)?\s*\(")))
            for member, kind in _JS_TEST_KINDS.items():
                patterns.append((kind, re.compile(
                    rf"(?<![\w$.]){name}\s*\.\s*{member}(?:\s*\.\s*only)?\s*\(")))
    return patterns


def _js_assert_re(raw: str) -> re.Pattern[str]:
    owners, direct = {"assert"}, set()
    for form, imported, local in _js_bindings(raw, lambda s: s in _JS_ASSERT_MODULES):
        (direct if form == "named" else owners).add(local)
    owner_alt = "|".join(re.escape(o) for o in sorted(owners))
    parts = [rf"(?<![\w$.])(?:{owner_alt})(?:\s*\.\s*[\w$]+)*\s*\("]
    if direct:
        parts.append(rf"(?<![\w$.])(?:{'|'.join(re.escape(d) for d in sorted(direct))})\s*\(")
    # t.assert.equal(...) del contexto de node:test.
    parts.append(r"(?<![\w$])[\w$]+\s*\.\s*assert\s*\.\s*[\w$]+\s*\(")
    return re.compile("|".join(parts))


def _mask_swallowed_try(text: str, assert_re: re.Pattern[str]) -> str:
    """Borra el cuerpo de los try cuyo catch traga el fallo (ni relanza ni
    aserta): una aserción ahí dentro jamás llega al código de salida."""
    chars = list(text)
    for m in re.finditer(r"(?<![\w$.])try\s*\{", text):
        t_open = m.end() - 1
        t_close = _matching(text, t_open, "{", "}")
        c = re.compile(r"\s*catch\s*(?:\([^)]*\))?\s*\{").match(text, t_close + 1)
        if c is None:
            continue
        c_open = c.end() - 1
        c_body = text[c_open + 1 : _matching(text, c_open, "{", "}")]
        if re.search(r"(?<![\w$.])throw\b", c_body) or assert_re.search(c_body):
            continue
        for k in range(t_open + 1, min(t_close, len(chars))):
            if chars[k] != "\n":
                chars[k] = " "
    return "".join(chars)


def _statement_end(text: str, start: int) -> int:
    """Fin de la expresión que empieza en start: ';' o salto de línea a
    profundidad cero, o el cierre de un paréntesis que la contiene."""
    depth = 0
    for k in range(start, len(text)):
        ch = text[k]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth < 0:
                return k
        elif depth == 0 and ch in ";\n":
            return k
    return len(text)


def _js_regions(clean: str, patterns) -> list[tuple[int, int, str]]:
    regions = []
    for kind, pattern in patterns:
        for m in pattern.finditer(clean):
            open_idx = m.end() - 1
            regions.append((m.start(), _matching(clean, open_idx, "(", ")"), kind))
    return sorted(regions)


_JS_ASSIGN_RE = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=(?![=>])")


def audit_node(code: str, focal_name: str) -> AuditOutcome:
    """Clasifica un test Node en las cinco categorías de la tesis. Un test que no
    se registra con node:test, o cuyo fallo no llega al código de salida, cuenta
    como TEST_FREE aunque el proceso termine con código 0."""
    raw = _strip_js(code or "", keep_strings=True)
    residue = _JS_IMPORT_RE.sub(" ", raw)
    residue = _JS_REQUIRE_RE.sub(" ", residue)
    if not re.sub(r"[\s;]", "", residue):
        return AuditOutcome.EMPTY
    plain = _strip_js(code or "")
    assert_re = _js_assert_re(raw)
    clean = _mask_swallowed_try(plain, assert_re)
    regions = _js_regions(clean, _js_registration_res(raw))
    tests = [(s, e) for s, e, kind in regions if kind == "test"]
    if not tests:
        return AuditOutcome.TEST_FREE
    if not any(s < m.start() < e for m in assert_re.finditer(clean) for s, e in tests) and any(
        s < m.start() < e for m in assert_re.finditer(plain) for s, e in tests
    ):
        # Todas las aserciones las traga un try/catch: su fallo no llega al código
        # de salida, luego el test no se registra a efectos de la tesis.
        return AuditOutcome.TEST_FREE
    outer: list[tuple[int, int]] = []
    for s, e, _ in regions:
        if not outer or s > outer[-1][1]:
            outer.append((s, e))
    asserts = []
    for m in assert_re.finditer(clean):
        if any(s < m.start() < e for s, e in tests):
            open_idx = m.end() - 1
            asserts.append((m.start(), clean[open_idx + 1 : _matching(clean, open_idx, "(", ")")]))
    if not asserts:
        return AuditOutcome.ASSERTION_FREE
    focal = re.compile(rf"(?<![\w$.]){re.escape(focal_name)}\s*\(")
    if any(focal.search(args) for _, args in asserts):
        return AuditOutcome.REAL
    # Salto de variable: solo variables simples; this.x o obj.x quedan fuera por
    # el (?<![\w$.]) de la asignación.
    for s, e in outer:
        for m in _JS_ASSIGN_RE.finditer(clean, s, e):
            rhs = clean[m.end() : _statement_end(clean, m.end())]
            if not focal.search(rhs):
                continue
            used = re.compile(rf"(?<![\w$.]){re.escape(m.group(1))}(?![\w$])")
            if any(pos >= m.end() and s <= pos < e and used.search(args) for pos, args in asserts):
                return AuditOutcome.REAL
    return AuditOutcome.NO_FOCAL

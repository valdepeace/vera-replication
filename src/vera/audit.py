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


def _js_registration_res(raw: str) -> list[tuple[str, re.Pattern[str], re.Pattern[str]]]:
    """Patrones (tipo, llamada, llamada con skip/todo) de node:test."""
    out: list[tuple[str, re.Pattern[str], re.Pattern[str]]] = []

    def add(kind: str, base: str) -> None:
        out.append((kind, re.compile(rf"(?<![\w$.]){base}(?:\s*\.\s*only)?\s*\("),
                    re.compile(rf"(?<![\w$.]){base}\s*\.\s*(?:skip|todo)\s*\(")))

    for form, imported, local in _js_bindings(raw, lambda s: s == "node:test"):
        name = re.escape(local)
        if form == "named" and imported in _JS_TEST_KINDS:
            add(_JS_TEST_KINDS[imported], name)
        elif form in ("default", "namespace"):
            if form == "default":
                add("test", name)
            for member, kind in _JS_TEST_KINDS.items():
                add(kind, rf"{name}\s*\.\s*{member}")
    return out


def _js_local_test_names(raw: str) -> set[str]:
    return {local for _, _, local in _js_bindings(raw, lambda s: s == "node:test")}


_JS_LOCAL_ASSERT_RE = re.compile(
    r"\b(?:const|let|var|function|class)\s+assert\b|(?<![\w$.])assert\s*=(?![=>])"
)


def _js_assert_re(raw: str) -> re.Pattern[str]:
    owners, direct, bound = {"assert"}, set(), set()
    for form, imported, local in _js_bindings(raw, lambda s: s in _JS_ASSERT_MODULES):
        (direct if form == "named" else owners).add(local)
        bound.add(local)
    # Un "assert" declarado en el propio fichero y no ligado a node:assert es un
    # doble inofensivo, no una aserción.
    if "assert" not in bound and _JS_LOCAL_ASSERT_RE.search(raw):
        owners.discard("assert")
    parts = []
    if owners:
        owner_alt = "|".join(re.escape(o) for o in sorted(owners))
        parts.append(rf"(?<![\w$.])(?:{owner_alt})(?:\s*\.\s*[\w$]+)*\s*\(")
    if direct:
        parts.append(rf"(?<![\w$.])(?:{'|'.join(re.escape(d) for d in sorted(direct))})\s*\(")
    # t.assert.equal(...) del contexto de node:test.
    parts.append(r"(?<![\w$])[\w$]+\s*\.\s*assert\s*\.\s*[\w$]+\s*\(")
    return re.compile("|".join(parts))


_JS_VOID_PROCESS_RE = re.compile(
    r"(?<![\w$.])process\s*\.\s*(?:exit|reallyExit|abort|kill|exitCode\s*=(?!=)"
    r"|setUncaughtExceptionCaptureCallback)\b"
)
_JS_VOID_EVENT_RE = re.compile(
    r"process\s*\.\s*(?:on|once|addListener|prependListener)\s*\(\s*['\"]"
    r"(?:uncaughtException|uncaughtExceptionMonitor|unhandledRejection|exit|beforeExit)['\"]"
)
_JS_ASSERT_MUTATION_RE = re.compile(r"(?<![\w$.])assert\s*(?:\.\s*[\w$]+)+\s*=(?!=)")
_JS_RETHROW_RE = re.compile(r"(?<![\w$.])throw\b|\.\s*fail\s*\(|\bifError\s*\(")
_JS_CALLEES = {
    "then", "setTimeout", "setImmediate", "setInterval", "queueMicrotask", "nextTick",
    "forEach", "map", "test", "it", "describe", "suite", "before", "after",
    "beforeEach", "afterEach", "on", "once",
}
_JS_FUNC_HEAD_RE = re.compile(
    rf"(?<![\w$.])function\s+({_JS_IDENT})\s*\([^()]*(?:\([^()]*\)[^()]*)*\)\s*(?=\{{)"
    rf"|(?<![\w$.])(?:const|let|var)\s+({_JS_IDENT})\s*=\s*(?:async\s+)?"
    rf"(?:function\b[^(){{}};]*\([^()]*(?:\([^()]*\)[^()]*)*\)\s*(?=\{{)"
    rf"|(?:\([^()]*(?:\([^()]*\)[^()]*)*\)|{_JS_IDENT})\s*=>\s*)"
)
_JS_BODY_FN_RE = re.compile(
    r"=>\s*(?=\{)|\bfunction\b[^(){};]*\([^()]*(?:\([^()]*\)[^()]*)*\)\s*(?=\{)"
)


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


def _blank(chars: list[str], a: int, b: int) -> None:
    for k in range(max(a, 0), min(b, len(chars))):
        if chars[k] != "\n":
            chars[k] = " "


def _word_before(text: str, end: int) -> str:
    m = re.search(r"([\w$]+)\s*$", text[:end])
    return m.group(1) if m else ""


def _open_before(text: str, close_idx: int) -> int:
    """Índice de la apertura que empareja el cierre en close_idx (o -1)."""
    depth = 0
    for k in range(close_idx, -1, -1):
        if text[k] in ")]}":
            depth += 1
        elif text[k] in "([{":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _statement_start(text: str, pos: int) -> int:
    depth = 0
    for k in range(pos - 1, -1, -1):
        ch = text[k]
        if ch in ")]}":
            depth += 1
        elif ch in "([{":
            if depth == 0:
                return k + 1
            depth -= 1
        elif depth == 0 and ch == ";":
            return k + 1
        elif depth == 0 and ch == "\n" and not text[k + 1 :].lstrip(" \t").startswith("."):
            return k + 1
    return 0


def _enclosing_callee(text: str, pos: int) -> str:
    depth = 0
    for k in range(pos - 1, -1, -1):
        ch = text[k]
        if ch in ")]}":
            depth += 1
        elif ch in "([{":
            if depth == 0:
                return _word_before(text, k) if ch == "(" else ""
            depth -= 1
    return ""


def _unconditional(text: str, k: int, floor: int) -> bool:
    """True si la sentencia que empieza en k se ejecuta siempre que se llega a su
    bloque (no es el cuerpo de un if/else/while/for sin llaves)."""
    j = k - 1
    while j > floor and text[j].isspace():
        j -= 1
    if j <= floor:
        return True
    if text[j] in ";{}":
        return True
    if text[j] == ")":
        o = _open_before(text, j)
        return o > 0 and _word_before(text, o) not in {"if", "while", "for", "with", "switch"}
    return False


def _mask_dead_after_exit(text: str, chars: list[str]) -> None:
    """Tras un return/throw/process.exit incondicional del propio cuerpo de una
    función, lo que sigue es inalcanzable."""
    exit_re = re.compile(r"(?:return|throw)(?![\w$])|process\s*\.\s*exit\s*\(")
    for m in _JS_BODY_FN_RE.finditer(text):
        open_idx = m.end()
        close = _matching(text, open_idx, "{", "}")
        depth, k = 0, open_idx + 1
        while k < close:
            ch = text[k]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif depth == 0 and ch.isalpha() and not (text[k - 1].isalnum() or text[k - 1] in "_$."):
                if exit_re.match(text, k) and _unconditional(text, k, open_idx):
                    _blank(chars, _statement_end(text, k) + 1, close)
                    break
            k += 1


_DEAD_COND = r"(?:false|0|null|undefined|!\s*true|!\s*1)"
_TRUE_COND = r"(?:true|1|!\s*false|!\s*0)"


def _branch_end(text: str, start: int) -> int:
    """Fin del bloque o de la sentencia que empieza en start."""
    while start < len(text) and text[start].isspace():
        start += 1
    if start < len(text) and text[start] == "{":
        return _matching(text, start, "{", "}") + 1
    return _statement_end(text, start) + 1


def _mask_dead_branches(text: str, chars: list[str]) -> None:
    for m in re.finditer(rf"(?<![\w$.])(?:if|while)\s*\(\s*{_DEAD_COND}\s*\)\s*", text):
        _blank(chars, m.end(), _branch_end(text, m.end()))
    for m in re.finditer(rf"(?<![\w$.])if\s*\(\s*{_TRUE_COND}\s*\)\s*", text):
        end = _branch_end(text, m.end())
        e = re.compile(r"\s*else\b\s*").match(text, end)
        if e:
            _blank(chars, e.end(), _branch_end(text, e.end()))


def _swallowing_try_ranges(text: str) -> list[tuple[int, int]]:
    """Rangos de try (y catch) cuyo fallo no llega al código de salida: catch que
    no relanza, o finally que sale con return/break/continue."""
    ranges: list[tuple[int, int]] = []
    for m in re.finditer(r"(?<![\w$.])try\s*\{", text):
        t_open = m.end() - 1
        t_close = _matching(text, t_open, "{", "}")
        pos, c_range, c_body = t_close + 1, None, ""
        c = re.compile(r"\s*catch\s*(?:\([^)]*\))?\s*\{").match(text, pos)
        if c:
            c_open = c.end() - 1
            c_close = _matching(text, c_open, "{", "}")
            c_range, c_body, pos = (c_open + 1, c_close), text[c_open + 1 : c_close], c_close + 1
        f = re.compile(r"\s*finally\s*\{").match(text, pos)
        f_body = ""
        if f:
            f_open = f.end() - 1
            f_body = text[f_open + 1 : _matching(text, f_open, "{", "}")]
        if re.search(r"(?<![\w$.])(?:return|break|continue)(?![\w$])", f_body):
            ranges.append((t_open + 1, t_close))
            if c_range:
                ranges.append(c_range)
        elif c_range and not _JS_RETHROW_RE.search(c_body):
            ranges.append((t_open + 1, t_close))
    return ranges


def _swallowing_catch_ranges(text: str) -> list[tuple[int, int]]:
    """Cadenas de promesas terminadas en .catch(...) que no relanza: se anula el
    receptor, cuyo fallo queda tragado."""
    ranges = []
    for m in re.finditer(r"\.\s*catch\s*\(", text):
        close = _matching(text, m.end() - 1, "(", ")")
        arg = text[m.end() : close]
        if not _JS_RETHROW_RE.search(arg) and "reject" not in arg:
            ranges.append((_statement_start(text, m.start()), m.start()))
    return ranges


def _function_defs(text: str) -> list[tuple[str, int, int, int]]:
    """(nombre, posición del nombre, inicio y fin del cuerpo) de las funciones
    con nombre del fichero."""
    defs = []
    for m in _JS_FUNC_HEAD_RE.finditer(text):
        name = m.group(1) or m.group(2)
        start = m.end()
        while start < len(text) and text[start].isspace():
            start += 1
        if start < len(text) and text[start] == "{":
            end = _matching(text, start, "{", "}") + 1
        else:
            end = _statement_end(text, start)
        defs.append((name, m.start(1) if m.group(1) else m.start(2), start, end))
    return defs


def _invoked(text: str, name: str, name_pos: int, callees: set[str]) -> bool:
    for m in re.finditer(rf"(?<![\w$.]){re.escape(name)}(?![\w$])", text):
        if m.start() == name_pos:
            continue
        after = text[m.end() :]
        if re.match(r"\s*(?:\(|\.\s*(?:call|apply)\b)", after):
            return True
        if _enclosing_callee(text, m.start()) in callees:
            return True
    return False


def _mask_calls_and_dead_functions(text: str, chars: list[str], callees: set[str]) -> None:
    defs = _function_defs(text)
    for name, _, b_start, b_end in defs:
        body = text[b_start:b_end]
        if _swallowing_try_ranges(body) or _swallowing_catch_ranges(body):
            call = re.compile(rf"(?<![\w$.])(?<!function\s){re.escape(name)}\s*\(")
            for m in call.finditer(text):
                if not any(d[0] == name and d[1] == m.start() for d in defs):
                    _blank(chars, m.end(), _matching(text, m.end() - 1, "(", ")"))
    for name, n_pos, b_start, b_end in defs:
        if not _invoked(text, name, n_pos, callees):
            _blank(chars, b_start, b_end)


def _mask_unref_timers(text: str, chars: list[str]) -> None:
    for m in re.finditer(r"(?<![\w$.])(?:setTimeout|setInterval|setImmediate)\s*\(", text):
        open_idx = m.end() - 1
        close = _matching(text, open_idx, "(", ")")
        dead = re.compile(r"\s*\.\s*unref\s*\(").match(text, close + 1) is not None
        if not dead:
            v = re.search(rf"({_JS_IDENT})\s*=\s*$", text[_statement_start(text, m.start()) : m.start()])
            if v:
                n = re.escape(v.group(1))
                dead = re.search(
                    rf"(?<![\w$.]){n}\s*\.\s*unref\s*\(|clear(?:Timeout|Interval|Immediate)\s*\(\s*{n}\s*\)",
                    text) is not None
        if dead:
            _blank(chars, open_idx + 1, close)


def _mask_unreachable(plain: str, callees: set[str]) -> str:
    chars = list(plain)
    _mask_dead_after_exit(plain, chars)
    text = "".join(chars)
    _mask_dead_branches(text, chars)
    text = "".join(chars)
    for a, b in _swallowing_try_ranges(text) + _swallowing_catch_ranges(text):
        _blank(chars, a, b)
    text = "".join(chars)
    _mask_unref_timers(text, chars)
    _mask_calls_and_dead_functions(plain, chars, callees)
    return "".join(chars)


def _function_span(text: str, name: str) -> tuple[int, int] | None:
    for n, _, b_start, b_end in _function_defs(text):
        if n == name:
            return b_start, b_end
    return None


_JS_ASSIGN_RE = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=(?![=>])")
_JS_OPT_SKIP_RE = re.compile(r"\b(?:skip|todo)\s*:\s*(?!false\b|0\b|undefined\b|null\b)")
_JS_CTX_SKIP_RE = re.compile(r"(?<![\w$])[\w$]+\s*\.\s*(?:skip|todo)\s*\(")


def _js_regions(clean: str, patterns) -> tuple[list[tuple[int, int, str]], list[tuple[int, int]]]:
    """Regiones de llamadas registradas (y las funciones referenciadas por nombre)
    tras descartar las saltadas (skip/todo)."""
    found, skipped = [], []
    for kind, call_re, skip_re in patterns:
        for m in skip_re.finditer(clean):
            skipped.append((m.start(), _matching(clean, m.end() - 1, "(", ")")))
        for m in call_re.finditer(clean):
            end = _matching(clean, m.end() - 1, "(", ")")
            args = clean[m.end() : end]
            head = re.split(r"=>|\bfunction\b", args, maxsplit=1)[0]
            if _JS_OPT_SKIP_RE.search(head) or (kind == "test" and _JS_CTX_SKIP_RE.search(args)):
                skipped.append((m.start(), end))
                continue
            found.append((m.start(), end, kind))
    regions = sorted(r for r in found if not any(a <= r[0] and r[1] <= b for a, b in skipped))
    extra = []
    for s, e, kind in regions:
        ref = re.search(rf",\s*({_JS_IDENT})\s*$", clean[s:e])
        span = _function_span(clean, ref.group(1)) if ref and kind == "test" else None
        if span:
            extra.append(span)
    return regions, extra


def audit_node(code: str, focal_name: str) -> AuditOutcome:
    """Clasifica un test Node en las cinco categorías de la tesis. Un test que no
    se registra con node:test, o cuyo fallo no llega al código de salida
    (try/catch que traga, return previo, rama muerta, promesa con catch vacío,
    helper que traga, skip/todo, process.exit...), cuenta como TEST_FREE aunque
    el proceso termine con código 0. En la duda se resuelve hacia TEST_FREE o
    ASSERTION_FREE: se prefiere infravalorar REAL."""
    raw = _strip_js(code or "", keep_strings=True)
    residue = _JS_IMPORT_RE.sub(" ", raw)
    residue = _JS_REQUIRE_RE.sub(" ", residue)
    if not re.sub(r"[\s;]", "", residue):
        return AuditOutcome.EMPTY
    plain = _strip_js(code or "")
    if (_JS_VOID_PROCESS_RE.search(plain) or _JS_VOID_EVENT_RE.search(raw)
            or _JS_ASSERT_MUTATION_RE.search(plain)):
        return AuditOutcome.TEST_FREE
    assert_re = _js_assert_re(raw)
    clean = _mask_unreachable(plain, _JS_CALLEES | _js_local_test_names(raw))
    regions, extra = _js_regions(clean, _js_registration_res(raw))
    tests = [(s, e) for s, e, kind in regions if kind == "test"] + extra
    if not tests:
        return AuditOutcome.TEST_FREE
    outer: list[tuple[int, int]] = []
    for s, e, _ in regions:
        if not outer or s > outer[-1][1]:
            outer.append((s, e))
    outer += extra

    def inside(pos: int) -> bool:
        return any(s < pos < e for s, e in tests)

    asserts = []
    for m in assert_re.finditer(clean):
        if inside(m.start()):
            open_idx = m.end() - 1
            asserts.append((m.start(), clean[open_idx + 1 : _matching(clean, open_idx, "(", ")")]))
    if not asserts:
        if any(inside(m.start()) for m in assert_re.finditer(plain)):
            # Todas las aserciones quedan tragadas o inalcanzables: su fallo no
            # llega al código de salida.
            return AuditOutcome.TEST_FREE
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

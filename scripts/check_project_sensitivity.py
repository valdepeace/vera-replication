"""Comprobación de sensibilidad y generación de tareas de los proyectos de Python y Node.

Envoltorio fino sobre vera.sensitivity. No ejecuta ningún modelo.

  python scripts/check_project_sensitivity.py python|node|all   # suite base y mutaciones
  python scripts/check_project_sensitivity.py --build           # escribe los tasks.json
"""
import argparse
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import subprocess  # noqa: E402

from vera.sensitivity import (  # noqa: E402
    extract_js_module_body,
    extract_python_function,
    mutation_detected,
)
from vera.types import Task  # noqa: E402

DATA = Path("E:/vera-data")
PY_REPO = DATA / "pydash"
JS_REPO = DATA / "validatorjs"
PY_COMMIT = "683471ca9c062bd5e1283fbd958928fc2dffe672"
JS_COMMIT = "9ff342479591ca5a43cb30000195bcf55c1bbed9"

# Directorio con el que el adaptador valida los tests generados: solo el código del
# proyecto, sin sus dependencias de desarrollo (el adaptador copia el directorio entero).
PY_PROJECT_DIR = PY_REPO / "src"
JS_PROJECT_DIR = JS_REPO / "lib"

PY_FUNCTIONS = [
    ("predicates", n) for n in ("is_blank", "is_boolean", "is_empty", "is_none", "is_string")
] + [
    ("strings", n) for n in (
        "chars", "clean", "count_substr", "decapitalize", "ends_with", "ensure_ends_with",
        "ensure_starts_with", "has_substr", "lower_first", "upper_first", "capitalize",
        "starts_with", "trim", "trim_start", "trim_end",
    )
]
JS_FUNCTIONS = [
    "isEmpty", "isBoolean", "isAscii", "isLowercase", "isUppercase", "isMultibyte",
    "trim", "isWhitelisted", "isSurrogatePair", "isHexadecimal", "isOctal", "isNumeric",
    "isSlug", "isMD5", "isLength", "equals", "contains", "toBoolean", "ltrim", "rtrim",
]

PY_SUITE = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=",
            "-o", "pythonpath=src", "tests/test_predicates.py", "tests/test_strings.py"]
JS_SUITE = ["node", "node_modules/mocha/bin/mocha", "--require", "@babel/register",
            "--reporter", "dot", "--recursive"]

# (fichero relativo al repositorio, patrón, sustituto): mutaciones manuales.
PY_MUTATIONS = [
    ("src/pydash/predicates.py", "is_boolean(value) or is_number(value) or not value",
     "is_boolean(value) or is_number(value) or value"),
    ("src/pydash/strings.py", "    if text.endswith(suffix):\n        return text",
     "    if not text.endswith(suffix):\n        return text"),
    ("src/pydash/strings.py", "return text.count(subtext)", "return text.count(subtext) + 1"),
    ("src/pydash/strings.py", "return text.lstrip(chars)", "return text.rstrip(chars)"),
    ("src/pydash/predicates.py", "return value is None", "return value is not None"),
]
JS_MUTATIONS = [
    ("src/lib/isEmpty.js", "str.length) === 0", "str.length) === 1"),
    ("src/lib/equals.js", "return str === comparison;", "return str !== comparison;"),
    ("src/lib/toBoolean.js", "str !== '0' && !/^false$/i.test(str) && str !== ''",
     "str !== '0' && !/^false$/i.test(str) && str === ''"),
    ("src/lib/isLowercase.js", "str === str.toLowerCase()", "str === str.toUpperCase()"),
    ("src/lib/isHexadecimal.js", "/^(0x|0h)?[0-9A-F]+$/i", "/^(0x|0h)?[0-9A-F]*$/i"),
]


def py_tasks() -> list[Task]:
    tasks = []
    for module, name in PY_FUNCTIONS:
        source = (PY_REPO / "src/pydash" / f"{module}.py").read_text(encoding="utf-8")
        tasks.append(Task(
            id=f"python-{module}-{name}", language="python", project="pydash",
            focal_name=name, focal_source=extract_python_function(source, name),
            container=f"pydash.{module}", test_name=f"test_generated_{module}_{name}",
            import_hint=f"from pydash import {name}",
        ))
    return tasks


def js_tasks() -> list[Task]:
    tasks = []
    for name in JS_FUNCTIONS:
        source = (JS_REPO / "src/lib" / f"{name}.js").read_text(encoding="utf-8")
        tasks.append(Task(
            id=f"node-{name}", language="node", project="validator.js",
            focal_name=name, focal_source=extract_js_module_body(source),
            container=f"{name}.js", test_name=f"generated_{name}.test.mjs",
            import_hint=f"import {name} from './{name}.js';",
        ))
    return tasks


def check(repo: Path, cmd: list[str], mutations: list[tuple[str, str, str]]) -> bool:
    base = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    print(f"{repo.name}: suite base {'pasa' if base.returncode == 0 else 'FALLA'}")
    if base.returncode != 0:
        print(base.stdout[-1500:])
        return False
    ok = True
    for rel, old, new in mutations:
        detected = mutation_detected(repo, repo / rel, (old, new), cmd)
        print(f"  {'detectada' if detected else 'NO detectada'}: {rel}: {old[:50]!r}")
        ok = ok and detected
    return ok


def build() -> None:
    for lang, tasks in (("python", py_tasks()), ("node", js_tasks())):
        out = ROOT / "benchmarks/vera01/replica" / lang / "tasks.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps([asdict(t) for t in tasks], indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"{len(tasks)} tareas escritas en {out}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("which", nargs="?", choices=["python", "node", "all"])
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        build()
        return 0
    if not args.which:
        parser.error("indique python, node, all o --build")
    results = []
    if args.which in ("python", "all"):
        results.append(check(PY_REPO, PY_SUITE, PY_MUTATIONS))
    if args.which in ("node", "all"):
        if shutil.which("node") is None:
            print("node no está en el PATH")
            return 2
        results.append(check(JS_REPO, JS_SUITE, JS_MUTATIONS))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

"""Pruebas de la comprobación de sensibilidad: una mutación manual ha de romper la suite."""
import sys
from pathlib import Path

import pytest

from vera.sensitivity import extract_js_module_body, extract_python_function, mutation_detected

CHECK = "import sys; sys.path.insert(0, '.'); import mod; sys.exit(0 if mod.is_empty('') else 1)"
CMD = [sys.executable, "-c", CHECK]
SOURCE = "def is_empty(s):\n    return len(s) == 0\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "mod.py").write_bytes(SOURCE.encode("utf-8"))
    return tmp_path


def test_mutation_detected_when_suite_fails(project: Path) -> None:
    assert mutation_detected(project, project / "mod.py", ("== 0", "== 1"), CMD) is True
    assert (project / "mod.py").read_bytes() == SOURCE.encode("utf-8")


def test_mutation_not_detected_when_suite_still_passes(project: Path) -> None:
    assert mutation_detected(project, project / "mod.py", ("len(s)", "len(s) + 0"), CMD) is False
    assert (project / "mod.py").read_bytes() == SOURCE.encode("utf-8")


def test_file_restored_after_check_even_on_error(project: Path) -> None:
    target = project / "mod.py"
    with pytest.raises(OSError):
        mutation_detected(project, target, ("== 0", "== 1"), [str(project / "no-existe-este-ejecutable")])
    assert target.read_bytes() == SOURCE.encode("utf-8")


def test_absent_pattern_is_an_error_and_leaves_file_untouched(project: Path) -> None:
    with pytest.raises(ValueError):
        mutation_detected(project, project / "mod.py", ("no esta", "x"), CMD)
    assert (project / "mod.py").read_bytes() == SOURCE.encode("utf-8")


def test_extract_python_function_drops_docstring_keeps_decorators() -> None:
    src = 'import os\n\n@deco\ndef f(x):\n    """Doc\n    >>> f(1)\n    """\n    y = x\n    return y\n\n\ndef g():\n    return 0\n'
    assert extract_python_function(src, "f") == "@deco\ndef f(x):\n    y = x\n    return y"
    assert extract_python_function(src, "g") == "def g():\n    return 0"
    with pytest.raises(ValueError):
        extract_python_function(src, "h")


def test_extract_js_module_body_drops_imports_and_eslint_directives() -> None:
    src = "import a from './a';\r\n\r\n/* eslint-disable x */\r\nconst re = /a/;\r\nexport default function f(s) {\r\n  return re.test(s);\r\n}\r\n"
    assert extract_js_module_body(src) == "const re = /a/;\nexport default function f(s) {\n  return re.test(s);\n}"


def test_multiline_pattern_matches_crlf_file(tmp_path: Path) -> None:
    target = tmp_path / "mod.py"
    crlf = b"def is_empty(s):\r\n    if s:\r\n        return False\r\n    return True\r\n"
    target.write_bytes(crlf)
    mutation = ("    if s:\n        return False", "    if not s:\n        return False")
    check = "import sys; sys.path.insert(0, '.'); import mod; sys.exit(0 if mod.is_empty('') else 1)"
    assert mutation_detected(tmp_path, target, mutation, [sys.executable, "-c", check]) is True
    assert target.read_bytes() == crlf

"""Pruebas de la auditoría de tests Python (análisis por ast)."""
from __future__ import annotations

import pytest

from vera.audit import audit_python
from vera.types import AuditOutcome

F = "slugify"


def audit(code: str) -> AuditOutcome:
    return audit_python(code, F)


@pytest.mark.parametrize("code", ["", "   \n", "import pytest\nx = 1\n", "# solo un comentario"])
def test_empty(code):
    assert audit(code) is AuditOutcome.EMPTY


def test_test_free_without_test_functions():
    assert audit("def helper():\n    assert slugify('a') == 'a'\n") is AuditOutcome.TEST_FREE


def test_test_free_method_in_non_collected_class():
    code = "class Helper:\n    def test_x(self):\n        assert slugify('a')\n"
    assert audit(code) is AuditOutcome.TEST_FREE


def test_test_free_on_syntax_error_with_definitions():
    assert audit("def test_x(:\n    pass\n") is AuditOutcome.TEST_FREE


def test_assertion_free():
    assert audit("def test_x():\n    slugify('a')\n") is AuditOutcome.ASSERTION_FREE


def test_no_focal():
    code = "def test_x():\n    assert len('a') == 1\n"
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_real_direct_call_in_assert():
    assert audit("def test_x():\n    assert slugify('A b') == 'a-b'\n") is AuditOutcome.REAL


def test_real_attribute_call():
    code = "import m\n\ndef test_x():\n    assert m.slugify('A') == 'a'\n"
    assert audit(code) is AuditOutcome.REAL


def test_real_via_variable():
    code = "def test_x():\n    r = slugify('A b')\n    assert r == 'a-b'\n"
    assert audit(code) is AuditOutcome.REAL


def test_variable_assigned_after_assert_is_not_real():
    code = "def test_x():\n    r = 1\n    assert r == 1\n    r = slugify('a')\n"
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_real_inside_pytest_raises():
    code = (
        "import pytest\n\ndef test_x():\n"
        "    with pytest.raises(ValueError):\n        slugify(None)\n"
    )
    assert audit(code) is AuditOutcome.REAL


def test_pytest_raises_without_focal_is_no_focal():
    code = (
        "import pytest\n\ndef test_x():\n"
        "    with pytest.raises(ValueError):\n        int('x')\n"
    )
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_real_unittest_self_assert():
    code = (
        "import unittest\n\nclass TestX(unittest.TestCase):\n"
        "    def test_a(self):\n        self.assertEqual(slugify('A'), 'a')\n"
    )
    assert audit(code) is AuditOutcome.REAL


def test_real_in_test_class_method():
    code = "class TestX:\n    def test_a(self):\n        assert slugify('A') == 'a'\n"
    assert audit(code) is AuditOutcome.REAL


def test_focal_only_in_a_non_test_function_is_no_focal():
    code = (
        "def helper():\n    return slugify('a')\n\n"
        "def test_x():\n    assert helper() == 'a'\n"
    )
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_none_code_is_empty():
    assert audit_python(None, F) is AuditOutcome.EMPTY


def test_attribute_target_does_not_taint_self_asserts():
    # self.x = focal(...) no asigna una variable local: self.assertTrue(True)
    # ejerce un assert, pero no el método focal, luego es NO_FOCAL.
    code = (
        "import unittest\n\nclass TestX(unittest.TestCase):\n"
        "    def test_a(self):\n        self.x = slugify('A')\n        self.assertTrue(True)\n"
    )
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_subscript_target_does_not_taint():
    code = "def test_x():\n    d = {}\n    d['k'] = slugify('A')\n    assert d is not None\n"
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_tuple_unpacking_of_names_is_followed():
    code = "def test_x():\n    a, b = slugify('A'), 1\n    assert a == 'a'\n"
    assert audit(code) is AuditOutcome.REAL


def test_plain_variable_hop_stays_real():
    code = "def test_x():\n    r = slugify('A')\n    assert r == 'a'\n"
    assert audit(code) is AuditOutcome.REAL


# --- Aserciones que jamás se ejercen: nunca deben contar como REAL ---------

NOT_REAL = [AuditOutcome.TEST_FREE, AuditOutcome.ASSERTION_FREE]
A = "    assert slugify('A') == 'a'\n"


def _not_real(code: str, expected: AuditOutcome) -> None:
    assert audit(code) is expected


def test_pytest_skip_before_assert():
    _not_real("import pytest\n\ndef test_x():\n    pytest.skip('no')\n" + A,
              AuditOutcome.ASSERTION_FREE)


def test_unittest_skiptest_before_assert():
    code = (
        "import unittest\n\nclass TestX(unittest.TestCase):\n"
        "    def test_a(self):\n        self.skipTest('no')\n"
        "        self.assertEqual(slugify('A'), 'a')\n"
    )
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_conditional_skip_before_assert_is_doubtful():
    code = "import pytest, sys\n\ndef test_x():\n    if sys.platform == 'win32':\n        pytest.skip('x')\n" + A
    _not_real(code, AuditOutcome.ASSERTION_FREE)


@pytest.mark.parametrize("deco", [
    "@pytest.mark.skip", "@pytest.mark.skip(reason='x')", "@pytest.mark.skipif(True, reason='x')",
    "@pytest.mark.skipif(1 == 1, reason='x')", "@pytest.mark.skipif(sys.platform == 'win32', reason='x')",
    "@pytest.mark.xfail", "@unittest.skip('x')", "@unittest.skipIf(True, 'x')",
    "@unittest.skipUnless(False, 'x')", "@unittest.expectedFailure",
])
def test_disabling_decorators(deco):
    code = f"import pytest, sys, unittest\n\n{deco}\ndef test_x():\n" + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_skip_decorator_on_class():
    code = "import pytest\n\n@pytest.mark.skip\nclass TestX:\n    def test_a(self):\n    " + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_module_level_pytestmark_skip():
    code = "import pytest\npytestmark = pytest.mark.skip\n\ndef test_x():\n" + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_skipif_false_stays_real():
    code = "import pytest\n\n@pytest.mark.skipif(False, reason='x')\ndef test_x():\n" + A
    assert audit(code) is AuditOutcome.REAL


def test_assert_after_return():
    _not_real("def test_x():\n    return\n" + A, AuditOutcome.ASSERTION_FREE)


def test_assert_after_raise():
    _not_real("def test_x():\n    raise RuntimeError\n" + A, AuditOutcome.ASSERTION_FREE)


@pytest.mark.parametrize("cond", ["False", "0", "None", "not True"])
def test_if_false_block(cond):
    _not_real(f"def test_x():\n    if {cond}:\n    " + A.replace("    assert", "    assert", 1),
              AuditOutcome.ASSERTION_FREE)


def test_if_true_else_branch_is_dead():
    code = "def test_x():\n    if True:\n        pass\n    else:\n    " + A
    _not_real(code, AuditOutcome.ASSERTION_FREE)


@pytest.mark.parametrize("handler", [
    "except AssertionError:\n        pass", "except:\n        pass",
    "except Exception:\n        pass", "except (ValueError, AssertionError):\n        pass",
    "except BaseException as e:\n        print(e)",
])
def test_try_except_swallows_assertion(handler):
    code = f"def test_x():\n    try:\n    {A}    {handler}\n"
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_try_except_that_reraises_stays_real():
    code = "def test_x():\n    try:\n    " + A + "    except AssertionError:\n        raise\n"
    assert audit(code) is AuditOutcome.REAL


def test_try_except_unrelated_error_stays_real():
    code = "def test_x():\n    try:\n    " + A + "    except ValueError:\n        pass\n"
    assert audit(code) is AuditOutcome.REAL


def test_contextlib_suppress_swallows():
    code = "import contextlib\n\ndef test_x():\n    with contextlib.suppress(AssertionError):\n    " + A
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_nested_function_never_called():
    code = "def test_x():\n    def check():\n    " + A + "    pass\n"
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_lambda_never_called():
    code = "import unittest\n\nclass TestX(unittest.TestCase):\n    def test_a(self):\n" \
           "        f = lambda: self.assertEqual(slugify('A'), 'a')\n"
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_nested_function_called_is_real():
    code = "def test_x():\n    def check():\n    " + A + "    check()\n"
    assert audit(code) is AuditOutcome.REAL


@pytest.mark.parametrize("stop", ["import sys\nsys.exit(0)", "import os\nos._exit(0)",
                                   "raise SystemExit", "import pytest\npytest.skip('x', allow_module_level=True)"])
def test_module_level_exit_before_collection(stop):
    code = f"{stop}\n\ndef test_x():\n" + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_async_test_without_plugin_is_not_counted():
    _not_real("async def test_x():\n" + A, AuditOutcome.TEST_FREE)


def test_loop_over_empty_literal_is_dead():
    _not_real("def test_x():\n    for c in []:\n    " + A, AuditOutcome.ASSERTION_FREE)


# --- Positivos legítimos que deben seguir siendo REAL ---------------------

def test_legit_assert_in_for_loop_over_cases():
    code = "def test_x():\n    for s, e in [('A', 'a')]:\n        assert slugify(s) == e\n"
    assert audit(code) is AuditOutcome.REAL


def test_legit_loop_with_continue_guard():
    code = ("def test_x():\n    for s in ['', 'A']:\n        if not s:\n            continue\n"
            "        assert slugify(s) == 'a'\n")
    assert audit(code) is AuditOutcome.REAL


def test_legit_assert_in_with_block():
    code = "import contextlib\n\ndef test_x():\n    with contextlib.nullcontext():\n    " + A
    assert audit(code) is AuditOutcome.REAL


def test_legit_parametrize():
    code = ("import pytest\n\n@pytest.mark.parametrize('s,e', [('A', 'a')])\n"
            "def test_x(s, e):\n    assert slugify(s) == e\n")
    assert audit(code) is AuditOutcome.REAL


def test_legit_assert_raises_unittest_with():
    code = ("import unittest\n\nclass TestX(unittest.TestCase):\n    def test_a(self):\n"
            "        with self.assertRaises(ValueError):\n            slugify(None)\n")
    assert audit(code) is AuditOutcome.REAL


def test_legit_assert_in_if_branch_and_try_finally():
    code = ("def test_x():\n    try:\n        r = slugify('A')\n    finally:\n        pass\n"
            "    if r:\n        assert r == 'a'\n")
    assert audit(code) is AuditOutcome.REAL

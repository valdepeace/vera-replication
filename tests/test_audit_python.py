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


# --- Ronda 14b: huecos verificados con pytest real -------------------------

@pytest.mark.parametrize("assertion", [
    "assert (slugify('A') == 'a', 'msg')",
    "assert (lambda: slugify('A') == 'a')",
    "assert (slugify(x) for x in 'A')",
])
def test_always_true_assert_forms(assertion):
    _not_real(f"def test_x():\n    {assertion}\n", AuditOutcome.ASSERTION_FREE)


def test_self_asserttrue_of_lambda():
    code = ("import unittest\n\nclass TestX(unittest.TestCase):\n    def test_a(self):\n"
            "        self.assertTrue(lambda: slugify('A'))\n")
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_variable_holding_lambda_is_not_a_focal_call():
    _not_real("def test_x():\n    f = lambda: slugify('A')\n    assert f\n", AuditOutcome.NO_FOCAL)


def test_all_over_generator_stays_real():
    assert audit("def test_x():\n    assert all(slugify(c) for c in 'AB')\n") is AuditOutcome.REAL


def test_assert_with_message_stays_real():
    assert audit("def test_x():\n    assert slugify('A') == 'a', 'msg'\n") is AuditOutcome.REAL


def test_duplicate_test_names_only_last_runs():
    code = "def test_a():\n" + A + "\ndef test_a():\n    pass\n"
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_duplicate_method_names_only_last_runs():
    code = ("class TestX:\n    def test_a(self):\n    " + A + "\n    def test_a(self):\n        pass\n")
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_duplicate_where_last_one_asserts_is_real():
    code = "def test_a():\n    pass\n\ndef test_a():\n" + A
    assert audit(code) is AuditOutcome.REAL


@pytest.mark.parametrize("stop", [
    "import pytest\nnp = pytest.importorskip('nonexistent_mod')",
    "import pytest\ntry:\n    import nonexistent_mod\nexcept ImportError:\n"
    "    pytest.skip('x', allow_module_level=True)",
    "import pytest, sys\nif sys.platform == 'win32':\n    pytest.skip('x', allow_module_level=True)",
])
def test_conditional_or_assigned_module_skips(stop):
    _not_real(f"{stop}\n\ndef test_x():\n" + A, AuditOutcome.TEST_FREE)


def test_main_guard_exit_does_not_disable_module():
    code = "import sys, pytest\n\ndef test_x():\n" + A + "\nif __name__ == '__main__':\n    sys.exit(pytest.main())\n"
    assert audit(code) is AuditOutcome.REAL


def test_importorskip_assigned_inside_test():
    _not_real("import pytest\n\ndef test_x():\n    m = pytest.importorskip('zz')\n" + A,
              AuditOutcome.ASSERTION_FREE)


def test_nested_helper_called_inside_swallowing_try():
    code = ("def test_x():\n    def check():\n    " + A +
            "    try:\n        check()\n    except Exception:\n        pass\n")
    _not_real(code, AuditOutcome.ASSERTION_FREE)


@pytest.mark.parametrize("flow", [
    "for x in [1]:\n        return", "while True:\n        return",
    "try:\n        return\n    except ValueError:\n        pass",
    "for x in range(3):\n        pytest.skip('x')",
])
def test_hard_flow_inside_compound_blocks(flow):
    code = f"import pytest\n\ndef test_x():\n    {flow}\n" + A
    _not_real(code, AuditOutcome.ASSERTION_FREE)


def test_parametrize_empty_list_runs_nothing():
    code = "import pytest\n\n@pytest.mark.parametrize('s', [])\ndef test_x(s):\n" + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_pytestmark_inside_class():
    code = "import pytest\n\nclass TestX:\n    pytestmark = pytest.mark.skip\n    def test_a(self):\n    " + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_annotated_pytestmark():
    code = "import pytest\npytestmark: object = pytest.mark.skip\n\ndef test_x():\n" + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_pytestmark_skipif_false_is_consistent():
    code = "import pytest\npytestmark = pytest.mark.skipif(False, reason='x')\n\ndef test_x():\n" + A
    assert audit(code) is AuditOutcome.REAL


def test_skipif_condition_keyword():
    code = "import pytest\n\n@pytest.mark.skipif(condition=True, reason='x')\ndef test_x():\n" + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_class_with_init_is_not_collected():
    code = "class TestX:\n    def __init__(self):\n        pass\n    def test_a(self):\n    " + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_class_without_testcase_is_collected():
    assert audit("class TestX:\n    def test_a(self):\n    " + A) is AuditOutcome.REAL


def test_fixture_named_test_is_not_a_test():
    code = "import pytest\n\n@pytest.fixture\ndef test_a():\n" + A
    _not_real(code, AuditOutcome.TEST_FREE)


def test_pytest_fail_in_handler_counts_as_reraise():
    code = ("import pytest\n\ndef test_x():\n    try:\n    " + A +
            "    except AssertionError:\n        pytest.fail('no')\n")
    assert audit(code) is AuditOutcome.REAL


@pytest.mark.parametrize("exc", ["Exception", "BaseException", "AssertionError"])
def test_assert_inside_broad_raises_does_not_count(exc):
    code = f"import pytest\n\ndef test_x():\n    with pytest.raises({exc}):\n    " + A
    _not_real(code, AuditOutcome.NO_FOCAL)  # el bloque raises cuenta, pero sin el focal


def test_focal_call_inside_broad_raises_still_real():
    code = "import pytest\n\ndef test_x():\n    with pytest.raises(Exception):\n        slugify(None)\n"
    assert audit(code) is AuditOutcome.REAL


def test_multiple_asserts_and_via_variable_still_real():
    code = ("def test_x():\n    assert 1 == 1\n    r = slugify('A')\n    assert r == 'a'\n"
            "    assert slugify('B') == 'b'\n")
    assert audit(code) is AuditOutcome.REAL

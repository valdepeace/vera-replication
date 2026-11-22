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

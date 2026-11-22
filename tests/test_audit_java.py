import time

import pytest

from vera.audit import audit_java
from vera.types import AuditOutcome

FOCAL = "isEmpty"
CONTAINER = "StringUtils"


def _test_class(body: str) -> str:
    return (
        "import org.junit.jupiter.api.Test;\n"
        "import static org.junit.jupiter.api.Assertions.*;\n"
        "class StringUtilsIsEmptyTest {\n"
        "    @Test\n"
        "    void generated() {\n"
        f"        {body}\n"
        "    }\n"
        "}\n"
    )


def _audit(code: str) -> AuditOutcome:
    return audit_java(code, FOCAL, CONTAINER)


def test_empty_when_no_class():
    assert _audit("") is AuditOutcome.EMPTY
    assert _audit("import org.junit.jupiter.api.Test;\n") is AuditOutcome.EMPTY


def test_test_free_when_no_test_annotation():
    code = (
        "class StringUtilsIsEmptyTest {\n"
        "    void generated() { assertTrue(StringUtils.isEmpty(\"\")); }\n"
        "}\n"
    )
    assert _audit(code) is AuditOutcome.TEST_FREE


def test_assertion_free():
    code = _test_class('StringUtils.isEmpty("");')
    assert _audit(code) is AuditOutcome.ASSERTION_FREE


def test_no_focal():
    code = _test_class('assertEquals(2, 1 + 1);')
    assert _audit(code) is AuditOutcome.NO_FOCAL


def test_real_direct_call_in_assertion():
    code = _test_class('assertTrue(StringUtils.isEmpty(""));')
    assert _audit(code) is AuditOutcome.REAL


def test_real_via_variable():
    code = _test_class('boolean r = StringUtils.isEmpty(""); assertTrue(r);')
    assert _audit(code) is AuditOutcome.REAL


def test_focal_call_outside_assertion_and_unused_is_no_focal():
    code = _test_class('boolean r = StringUtils.isEmpty(""); assertTrue(true);')
    assert _audit(code) is AuditOutcome.NO_FOCAL


def test_assert_throws_with_lambda_counts():
    code = _test_class(
        "assertThrows(NullPointerException.class, () -> StringUtils.isEmpty(null));"
    )
    assert _audit(code) is AuditOutcome.REAL


def test_comment_mentioning_focal_does_not_count():
    code = _test_class(
        "// assertTrue(StringUtils.isEmpty(\"\"));\n"
        "        /* StringUtils.isEmpty(x) */ assertTrue(true);"
    )
    assert _audit(code) is AuditOutcome.NO_FOCAL


def test_string_literal_mentioning_focal_does_not_count():
    code = _test_class('assertEquals("StringUtils.isEmpty(x)", "a");')
    assert _audit(code) is AuditOutcome.NO_FOCAL


def test_same_name_on_other_receiver_is_no_focal():
    code = _test_class('java.util.List<String> l = new java.util.ArrayList<>(); assertTrue(l.isEmpty());')
    assert _audit(code) is AuditOutcome.NO_FOCAL


def test_static_import_unqualified_call_counts():
    code = _test_class('assertTrue(isEmpty(""));')
    assert _audit(code) is AuditOutcome.REAL


def test_variable_from_other_method_does_not_count():
    code = (
        "import org.junit.jupiter.api.Test;\n"
        "class StringUtilsIsEmptyTest {\n"
        "    @Test void a() { boolean r = StringUtils.isEmpty(\"\"); }\n"
        "    @Test void b() { boolean r = true; assertTrue(r); }\n"
        "}\n"
    )
    assert _audit(code) is AuditOutcome.NO_FOCAL


def test_parameterized_test_with_brace_annotation_counts():
    code = (
        "import org.junit.jupiter.params.ParameterizedTest;\n"
        "class StringUtilsIsEmptyTest {\n"
        "    @ParameterizedTest\n"
        "    @ValueSource(strings = {\"\", \"\"})\n"
        "    void generated(String s) { assertTrue(StringUtils.isEmpty(s)); }\n"
        "}\n"
    )
    assert _audit(code) is AuditOutcome.REAL


@pytest.mark.parametrize(
    "prefix",
    ["class X { @Test void a() throws ", "class X { @Test void a() "],
)
def test_pathological_whitespace_returns_quickly(prefix):
    code = prefix + " " * 20000
    start = time.perf_counter()
    outcome = audit_java(code, FOCAL, CONTAINER)
    assert time.perf_counter() - start < 1.0
    assert isinstance(outcome, AuditOutcome)


def test_throws_clause_with_several_exceptions_counts():
    code = (
        "class StringUtilsIsEmptyTest {\n"
        "    @Test void generated() throws java.io.IOException , Exception {\n"
        "        assertTrue(StringUtils.isEmpty(\"\"));\n"
        "    }\n"
        "}\n"
    )
    assert _audit(code) is AuditOutcome.REAL

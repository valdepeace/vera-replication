"""Pruebas de la auditoría de tests Node (análisis textual)."""
from __future__ import annotations

import pytest

from vera.audit import audit_node
from vera.types import AuditOutcome

F = "slugify"
HEAD = "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { slugify } from './text.mjs';\n"


def audit(code: str) -> AuditOutcome:
    return audit_node(code, F)


@pytest.mark.parametrize("code", [
    "", "   \n", "// solo un comentario", "import test from 'node:test';\nimport { slugify } from './t.mjs';\n",
    "const assert = require('node:assert');\n",
])
def test_empty(code):
    assert audit(code) is AuditOutcome.EMPTY


def test_own_suite_wrapper_is_test_free():
    code = (
        "import assert from 'node:assert/strict';\nimport { slugify } from './text.mjs';\n"
        "function test(name, fn) { try { fn(); console.log('ok', name); } catch (e) { console.log(e.message); } }\n"
        "test('a', () => { assert.equal(slugify('A'), 'zzz'); });\n"
    )
    assert audit(code) is AuditOutcome.TEST_FREE


def test_test_free_when_only_skipped_or_outside_tests():
    code = HEAD + "test.skip('a', () => { assert.equal(slugify('A'), 'a'); });\nassert.equal(slugify('A'), 'a');\n"
    assert audit(code) is AuditOutcome.TEST_FREE


def test_test_free_when_node_test_missing_but_test_called():
    code = "import assert from 'node:assert/strict';\ntest('a', () => { assert.equal(slugify('A'), 'a'); });\n"
    assert audit(code) is AuditOutcome.TEST_FREE


def test_assertion_free():
    assert audit(HEAD + "test('a', () => { slugify('A'); });\n") is AuditOutcome.ASSERTION_FREE


def test_assertion_free_ignores_comments_and_strings():
    code = HEAD + "test('a', () => { // assert.equal(slugify('A'), 'a')\n const s = 'assert.ok(slugify(1))'; });\n"
    assert audit(code) is AuditOutcome.ASSERTION_FREE


def test_no_focal():
    assert audit(HEAD + "test('a', () => { assert.equal(1, 1); });\n") is AuditOutcome.NO_FOCAL


def test_focal_only_in_a_string_or_comment_is_no_focal():
    code = HEAD + "test('a', () => { assert.equal('slugify(1)', 'x'); /* slugify(2) */ });\n"
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_real_direct():
    assert audit(HEAD + "test('a', () => { assert.equal(slugify('A'), 'a'); });\n") is AuditOutcome.REAL


def test_real_via_variable():
    code = HEAD + "test('a', () => {\n  const r = slugify('A');\n  assert.equal(r, 'a');\n});\n"
    assert audit(code) is AuditOutcome.REAL


def test_real_with_require_and_it_inside_describe():
    code = (
        "const { describe, it } = require('node:test');\nconst assert = require('node:assert');\n"
        "describe('s', () => { it('a', () => { assert.strictEqual(slugify('A'), 'a'); }); });\n"
    )
    assert audit(code) is AuditOutcome.REAL


def test_real_with_aliased_and_named_assert_imports():
    code = (
        "import { test as t } from 'node:test';\nimport { strictEqual } from 'node:assert';\n"
        "t('a', async () => { strictEqual(slugify('A'), 'a'); });\n"
    )
    assert audit(code) is AuditOutcome.REAL


def test_real_with_namespace_import_and_context_assert():
    code = "import * as nt from 'node:test';\nnt.test('a', (t) => { t.assert.equal(slugify('A'), 'a'); });\n"
    assert audit(code) is AuditOutcome.REAL


@pytest.mark.parametrize("stmt", [
    "this.r = slugify('A');\n  assert.equal(this.r, 'a');",
    "obj.r = slugify('A');\n  assert.equal(obj.r, 'a');",
    "ctx['r'] = slugify('A');\n  assert.equal(ctx.r, 'a');",
])
def test_property_assignment_is_not_a_chain(stmt):
    code = HEAD + "test('a', () => {\n  const obj = {}; const ctx = {};\n  " + stmt + "\n});\n"
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_variable_used_before_assignment_does_not_count():
    code = HEAD + "test('a', () => {\n  let r = 1;\n  assert.equal(r, 1);\n  r = slugify('A');\n});\n"
    assert audit(code) is AuditOutcome.NO_FOCAL


def test_assertion_swallowed_by_try_catch_is_test_free():
    code = HEAD + "test('a', () => {\n  try { assert.equal(slugify('A'), 'zzz'); } catch (e) { console.log('x'); }\n});\n"
    assert audit(code) is AuditOutcome.TEST_FREE


def test_try_catch_that_rethrows_or_asserts_still_counts():
    rethrow = HEAD + "test('a', () => {\n  try { assert.equal(slugify('A'), 'a'); } catch (e) { throw e; }\n});\n"
    assert audit(rethrow) is AuditOutcome.REAL
    expected = HEAD + "test('a', () => {\n  try { slugify(null); } catch (e) { assert.match(e.message, /x/); }\n});\n"
    assert audit(expected) is AuditOutcome.NO_FOCAL


def test_unawaited_async_assertion_inside_a_registered_test_counts():
    code = HEAD + "test('a', () => {\n  setTimeout(() => { assert.equal(slugify('A'), 'a'); }, 10);\n});\n"
    assert audit(code) is AuditOutcome.REAL

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


# --- Patrones que el runner da por buenos (código 0) o que no se ejecutan ------------------
# Cabe señalar que en todos la aserción falsa es assert.equal(slugify('A'), 'zzz'), de modo
# que ninguno puede auditarse como REAL (se resuelve hacia TEST_FREE ante la duda).
H = HEAD
SWALLOWED = {
    "a_promise_empty_catch": H + "test('a', () => { Promise.resolve().then(() => { assert.equal(slugify('A'), 'zzz'); }).catch(() => {}); });\n",
    "a_promise_multiline_catch": H + "test('a', () => {\n  Promise.resolve()\n    .then(() => { assert.equal(slugify('A'), 'zzz'); })\n    .catch((e) => { console.log(e.message); });\n});\n",
    "b_return_before": H + "test('a', () => { return; assert.equal(slugify('A'), 'zzz'); });\n",
    "b_throw_before_unreachable": H + "test('a', () => { return 1;\n assert.equal(slugify('A'), 'zzz'); });\n",
    "c_if_false": H + "test('a', () => { if (false) { assert.equal(slugify('A'), 'zzz'); } });\n",
    "c_if_zero": H + "test('a', () => { if (0) assert.equal(slugify('A'), 'zzz'); });\n",
    "c_while_false": H + "test('a', () => { while (false) { assert.equal(slugify('A'), 'zzz'); } });\n",
    "c_if_true_else": H + "test('a', () => { if (true) { console.log(1); } else { assert.equal(slugify('A'), 'zzz'); } });\n",
    "d_never_called": H + "test('a', () => { const check = () => assert.equal(slugify('A'), 'zzz');\n });\n",
    "d_never_called_function": H + "test('a', () => { function check() { assert.equal(slugify('A'), 'zzz'); } });\n",
    "e_swallowing_helper": H + "function safe(f) { try { f(); } catch (e) { console.log(e.message); } }\ntest('a', () => { safe(() => { assert.equal(slugify('A'), 'zzz'); }); });\n",
    "e_swallowing_helper_const": H + "const safe = (f) => { try { f(); } catch (e) { } };\ntest('a', () => { safe(() => { assert.equal(slugify('A'), 'zzz'); }); });\n",
    "f_skip_option": H + "test('a', { skip: true }, () => { assert.equal(slugify('A'), 'zzz'); });\n",
    "f_todo_option": H + "test('a', { todo: 'later' }, () => { assert.equal(slugify('A'), 'zzz'); });\n",
    "f_t_todo": H + "test('a', (t) => { t.todo(); assert.equal(slugify('A'), 'zzz'); });\n",
    "f_t_skip": H + "test('a', (t) => { t.skip('x'); assert.equal(slugify('A'), 'zzz'); });\n",
    "f_describe_skip": H + "import { describe, it } from 'node:test';\ndescribe.skip('s', () => { it('a', () => { assert.equal(slugify('A'), 'zzz'); }); });\n",
    "g_catch_assert_ok": H + "test('a', () => { try { assert.equal(slugify('A'), 'zzz'); } catch (e) { assert.ok(e); } });\n",
    "h_finally_return": H + "test('a', () => { (() => { try { assert.equal(slugify('A'), 'zzz'); } finally { return; } })(); });\n",
    "i_process_exit": H + "test('a', () => { assert.equal(slugify('A'), 'zzz'); });\nprocess.exit(0);\n",
    "i_process_on_exit": H + "test('a', () => { assert.equal(slugify('A'), 'zzz'); });\nprocess.on('exit', () => { process.exitCode = 0; });\n",
    "j_unref": H + "test('a', () => { setTimeout(() => { assert.equal(slugify('A'), 'zzz'); }, 100).unref(); });\n",
    "j_unref_var": H + "test('a', () => { const t = setTimeout(() => { assert.equal(slugify('A'), 'zzz'); }, 100); t.unref(); });\n",
    "k_local_fake_assert": "import test from 'node:test';\nimport { slugify } from './text.mjs';\nconst assert = { equal() {} };\ntest('a', () => { assert.equal(slugify('A'), 'zzz'); });\n",
    "k_assert_mutated": H + "assert.equal = () => {};\ntest('a', () => { assert.equal(slugify('A'), 'zzz'); });\n",
}


@pytest.mark.parametrize("name", sorted(SWALLOWED))
def test_swallowed_or_unreachable_assertion_is_never_real(name):
    outcome = audit(SWALLOWED[name])
    assert outcome is not AuditOutcome.REAL
    expected = {"g": AuditOutcome.NO_FOCAL, "k_local_fake_assert": AuditOutcome.ASSERTION_FREE}.get(
        name.split("_")[0] if name.startswith("g_") else name, AuditOutcome.TEST_FREE)
    assert outcome is expected


def test_test_passed_by_reference_resolves_to_its_declaration():
    code = HEAD + "function body() { assert.equal(slugify('A'), 'a'); }\ntest('a', body);\n"
    assert audit(code) is AuditOutcome.REAL
    arrow = HEAD + "const body = async () => { const r = slugify('A'); assert.equal(r, 'a'); };\ntest('a', body);\n"
    assert audit(arrow) is AuditOutcome.REAL
    no_assert = HEAD + "function body() { slugify('A'); }\ntest('a', body);\n"
    assert audit(no_assert) is AuditOutcome.ASSERTION_FREE
    unrelated = HEAD + "function body() { assert.equal(1, 1); }\ntest('a', body);\n"
    assert audit(unrelated) is AuditOutcome.NO_FOCAL


@pytest.mark.parametrize("body", [
    "if (process.argv.length > 99) return;\n  assert.equal(slugify('A'), 'a');",
    "const check = () => assert.equal(slugify('A'), 'a');\n  check();",
    "function check() { assert.equal(slugify('A'), 'a'); }\n  check();",
    "Promise.resolve().then(() => { assert.equal(slugify('A'), 'a'); }).catch((e) => { throw e; });",
    "try { assert.equal(slugify('A'), 'a'); } catch (e) { throw e; } finally { console.log(1); }",
    "if (true) { assert.equal(slugify('A'), 'a'); }",
    "const t = setTimeout(() => { assert.equal(slugify('A'), 'a'); }, 5);",
    "[1].forEach(() => { assert.equal(slugify('A'), 'a'); });",
])
def test_reachable_and_propagating_assertions_still_count(body):
    assert audit(HEAD + "test('a', () => {\n  " + body + "\n});\n") is AuditOutcome.REAL


def test_non_swallowing_helper_still_counts():
    code = HEAD + "function run(f) { f(); }\ntest('a', () => { run(() => assert.equal(slugify('A'), 'a')); });\n"
    assert audit(code) is AuditOutcome.REAL

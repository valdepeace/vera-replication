"""Pruebas del adaptador node:test: unitarias con ejecutor inyectado e integración
real (opt-in) con el node instalado."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from vera.adapters.node_test import MAX_DIAGNOSTIC, NodeTestAdapter
from vera.types import AuditOutcome, Task

NODE = shutil.which("node")
HEAD = "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { slugify } from './text.mjs';\n"


def make_task(test_name: str = "slugify.generated.test") -> Task:
    return Task(
        id="node-slugify", language="node", project="mini", focal_name="slugify",
        focal_source="export function slugify(s) {}", container="text.mjs",
        test_name=test_name, import_hint="import { slugify } from './text.mjs';",
    )


def make_project(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "text.mjs").write_text(
        "export function slugify(s) { return s.trim().toLowerCase().replace(/ /g, '-'); }\n",
        encoding="utf-8")
    return root


class FakeRunner:
    def __init__(self, returncode=0, stdout="", raises=None):
        self.returncode, self.stdout, self.raises = returncode, stdout, raises
        self.calls: list[tuple[list[str], dict]] = []
        self.existed: bool | None = None

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        self.existed = (Path(kwargs["cwd"]) / "slugify.generated.test.mjs").exists()
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(cmd, self.returncode, stdout=self.stdout, stderr="")


def adapter(tmp_path: Path, runner) -> NodeTestAdapter:
    return NodeTestAdapter(make_project(tmp_path / "proj"), Path("node.exe"), timeout_s=5, runner=runner)


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_runs_node_test_in_a_copy_and_leaves_original_untouched(tmp_path):
    runner = FakeRunner()
    a = adapter(tmp_path, runner)
    before = snapshot(a.project_dir)
    result = a.validate(make_task(), "x")
    assert result.passed and result.diagnostic == "" and not result.infra_failure
    cmd, kwargs = runner.calls[0]
    assert cmd == ["node.exe", "--test", "slugify.generated.test.mjs"]
    assert runner.existed is True
    assert Path(kwargs["cwd"]) != a.project_dir
    assert snapshot(a.project_dir) == before
    assert not Path(kwargs["cwd"]).exists()


def test_failure_returns_filtered_diagnostic(tmp_path):
    out = ("✖ a (1ms)\nℹ tests 1\nℹ pass 0\n\n✖ failing tests:\n\ntest at x.mjs:2:1\n✖ a (1ms)\n"
           "  AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:\n  1 !== 2\n"
           "      at Test.run (node:internal/test_runner/test:1106:25)\n")
    result = adapter(tmp_path, FakeRunner(returncode=1, stdout=out)).validate(make_task(), "x")
    assert not result.passed and not result.infra_failure
    assert "1 !== 2" in result.diagnostic and "AssertionError" in result.diagnostic
    assert "node:internal" not in result.diagnostic and "ℹ tests" not in result.diagnostic


def test_huge_output_is_capped(tmp_path):
    out = "E " + "x" * 50000 + "\n" + "".join(f"line {i}\n" for i in range(5000))
    result = adapter(tmp_path, FakeRunner(returncode=1, stdout=out)).validate(make_task(), "x")
    assert 0 < len(result.diagnostic) <= MAX_DIAGNOSTIC < 4000


def test_unfilterable_output_falls_back_to_message(tmp_path):
    result = adapter(tmp_path, FakeRunner(returncode=1, stdout="\n")).validate(make_task(), "x")
    assert "exit code 1" in result.diagnostic and not result.infra_failure


def test_timeout_is_infrastructure_failure(tmp_path):
    runner = FakeRunner(raises=subprocess.TimeoutExpired("node", 5))
    result = adapter(tmp_path, runner).validate(make_task(), "x")
    assert not result.passed and result.infra_failure and "timed out" in result.diagnostic
    assert not Path(runner.calls[0][1]["cwd"]).exists()


def test_missing_interpreter_is_infrastructure_and_cleans_up(tmp_path):
    runner = FakeRunner(raises=FileNotFoundError("node.exe"))
    result = adapter(tmp_path, runner).validate(make_task(), "x")
    assert result.infra_failure and not result.passed
    assert not Path(runner.calls[0][1]["cwd"]).exists()


@pytest.mark.parametrize("code", [-9, -1, 3221225477, 9])
def test_process_killed_by_os_is_infrastructure(tmp_path, code):
    result = adapter(tmp_path, FakeRunner(returncode=code)).validate(make_task(), "x")
    assert result.infra_failure and not result.passed


@pytest.mark.parametrize("out", [
    "Error [ERR_UNKNOWN_BUILTIN_MODULE]: No such built-in module: node:test",
    "Error: Cannot find module 'node:test'",
    "node: bad option: --test",
])
def test_missing_runner_is_infrastructure(tmp_path, out):
    result = adapter(tmp_path, FakeRunner(returncode=1, stdout=out)).validate(make_task(), "x")
    assert result.infra_failure and not result.passed


def test_broken_relative_import_is_a_model_failure(tmp_path):
    out = "Error [ERR_MODULE_NOT_FOUND]: Cannot find module '/p/nope.mjs' imported from /p/x.mjs"
    result = adapter(tmp_path, FakeRunner(returncode=1, stdout=out)).validate(make_task(), "x")
    assert not result.infra_failure and not result.passed


def test_own_wrapper_passes_in_runner_but_audits_test_free(tmp_path):
    code = ("import assert from 'node:assert/strict';\n"
            "function test(n, f) { try { f(); } catch (e) {} }\n"
            "test('a', () => { assert.equal(slugify('A'), 'zzz'); });\n")
    a = adapter(tmp_path, FakeRunner(returncode=0))
    assert a.validate(make_task(), code).passed
    assert a.audit(make_task(), code) is AuditOutcome.TEST_FREE


def test_audit_delegates_with_focal_name(tmp_path):
    a = adapter(tmp_path, FakeRunner())
    assert a.audit(make_task(), HEAD + "test('a', () => { assert.equal(slugify('A'), 'a'); });\n") \
        is AuditOutcome.REAL


# --- Integración real con node (opt-in: pytest -m integration) -------------------------

needs_node = pytest.mark.skipif(NODE is None, reason="node no está en el PATH")


def real(tmp_path, timeout_s=120) -> NodeTestAdapter:
    return NodeTestAdapter(make_project(tmp_path / "proj"), Path(NODE), timeout_s=timeout_s)


@pytest.mark.integration
@needs_node
def test_real_pass_fail_and_original_untouched(tmp_path):
    a = real(tmp_path)
    before = snapshot(a.project_dir)
    ok = a.validate(make_task(), HEAD + "test('ok', () => { assert.equal(slugify(' A b '), 'a-b'); });\n")
    bad = a.validate(make_task(), HEAD + "test('bad', () => { assert.equal(slugify('A'), 'zzz'); });\n")
    assert ok.passed
    assert not bad.passed and not bad.infra_failure and "zzz" in bad.diagnostic
    assert len(bad.diagnostic) < 4000
    assert snapshot(a.project_dir) == before


@pytest.mark.integration
@needs_node
@pytest.mark.parametrize("body", [
    "assert.equal(slugify('A'), 'zzz');",
    "setTimeout(() => { assert.equal(slugify('A'), 'zzz'); }, 30);",
    "Promise.resolve().then(() => { assert.equal(slugify('A'), 'zzz'); });",
    "(async () => { await null; assert.equal(slugify('A'), 'zzz'); })();",
])
def test_real_failing_assertion_in_registered_test_fails_the_process(tmp_path, body):
    """Incluida la aserción dentro de un callback asíncrono no esperado."""
    a = real(tmp_path)
    code = HEAD + "test('a', () => { " + body + " });\ntest('b', async () => { await new Promise(r => setTimeout(r, 300)); });\n"
    result = a.validate(make_task(), code)
    assert not result.passed and not result.infra_failure
    assert a.audit(make_task(), code) is AuditOutcome.REAL


@pytest.mark.integration
@needs_node
def test_real_assertion_swallowed_by_try_catch_passes_but_does_not_count(tmp_path):
    """El runner no puede ver lo que el propio test traga: la auditoría lo excluye."""
    a = real(tmp_path)
    code = HEAD + "test('a', () => { try { assert.equal(slugify('A'), 'zzz'); } catch (e) { /* tragado */ } });\n"
    assert a.validate(make_task(), code).passed
    assert a.audit(make_task(), code) is AuditOutcome.TEST_FREE


@pytest.mark.integration
@needs_node
def test_real_own_wrapper_passes_but_is_test_free(tmp_path):
    a = real(tmp_path)
    code = ("import assert from 'node:assert/strict';\nimport { slugify } from './text.mjs';\n"
            "function test(n, f) { try { f(); } catch (e) { console.log(e.message); } }\n"
            "test('a', () => { assert.equal(slugify('A'), 'zzz'); });\n")
    assert a.validate(make_task(), code).passed
    assert a.audit(make_task(), code) is AuditOutcome.TEST_FREE


@pytest.mark.integration
@needs_node
def test_real_timeout_is_infrastructure(tmp_path):
    a = real(tmp_path, timeout_s=2)
    result = a.validate(make_task(), HEAD + "test('s', async () => { await new Promise(r => setTimeout(r, 30000)); });\n")
    assert result.infra_failure and not result.passed


@pytest.mark.integration
@needs_node
def test_real_swallowed_patterns_exit_zero_yet_never_audit_real(tmp_path):
    """Cada patrón engaña al runner (código 0, o no se ejecuta) con una aserción falsa;
    la auditoría jamás debe darlo por REAL."""
    from tests.test_audit_node import SWALLOWED
    a = real(tmp_path)
    leaked = {}
    for name, code in SWALLOWED.items():
        if name == "i_process_on_exit":
            continue  # node ignora process.exitCode = 0 tras un fallo: se anula por cautela
        result = a.validate(make_task(), code)
        leaked[name] = (result.passed, result.infra_failure, a.audit(make_task(), code).name)
    assert all(passed and not infra and audit != "REAL" for passed, infra, audit in leaked.values()), leaked


@pytest.mark.integration
@needs_node
def test_real_test_passed_by_reference_fails_the_process_and_audits_real(tmp_path):
    a = real(tmp_path)
    code = HEAD + "function body() { assert.equal(slugify('A'), 'zzz'); }\ntest('a', body);\n"
    result = a.validate(make_task(), code)
    assert not result.passed and not result.infra_failure
    assert a.audit(make_task(), code) is AuditOutcome.REAL

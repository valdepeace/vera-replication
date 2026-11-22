"""Pruebas del adaptador pytest: unitarias con ejecutor inyectado e integración
real (opt-in) con el Python del .venv."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from vera.adapters.python_pytest import MAX_DIAGNOSTIC, PythonPytestAdapter
from vera.types import AuditOutcome, Task


def make_task(test_name: str = "test_slugify_generated") -> Task:
    return Task(
        id="py-slugify", language="python", project="mini", focal_name="slugify",
        focal_source="def slugify(s): ...", container="mini.text",
        test_name=test_name, import_hint="from mini.text import slugify",
    )


def make_project(root: Path) -> Path:
    pkg = root / "mini"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "text.py").write_text(
        "def slugify(s):\n    return s.strip().lower().replace(' ', '-')\n", encoding="utf-8"
    )
    (root / "conftest.py").write_text("", encoding="utf-8")
    return root


class FakeRunner:
    def __init__(self, returncode=0, stdout="", raises=None):
        self.returncode, self.stdout, self.raises = returncode, stdout, raises
        self.calls: list[tuple[list[str], dict]] = []
        self.existed: bool | None = None

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        self.existed = (Path(kwargs["cwd"]) / (make_task().test_name + ".py")).exists()
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(cmd, self.returncode, stdout=self.stdout, stderr="")


def adapter(tmp_path: Path, runner) -> PythonPytestAdapter:
    return PythonPytestAdapter(
        project_dir=make_project(tmp_path / "proj"), python=Path("py.exe"), timeout_s=5,
        runner=runner,
    )


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_runs_pytest_in_a_copy_and_leaves_original_untouched(tmp_path):
    runner = FakeRunner()
    a = adapter(tmp_path, runner)
    before = snapshot(a.project_dir)
    result = a.validate(make_task(), "def test_x():\n    assert True\n")
    assert result.passed and result.diagnostic == "" and not result.infra_failure
    cmd, kwargs = runner.calls[0]
    assert cmd == ["py.exe", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "test_slugify_generated.py"]
    assert runner.existed is True
    assert Path(kwargs["cwd"]) != a.project_dir
    assert snapshot(a.project_dir) == before
    assert not Path(kwargs["cwd"]).exists()


def test_failure_returns_filtered_diagnostic(tmp_path):
    out = "noise\n" * 50 + "    def test_x():\n>       assert 1 == 2\nE       assert 1 == 2\n" \
        "test_slugify_generated.py:2: AssertionError\nFAILED test_slugify_generated.py::test_x\n"
    result = adapter(tmp_path, FakeRunner(returncode=1, stdout=out)).validate(make_task(), "x")
    assert not result.passed and not result.infra_failure
    assert "assert 1 == 2" in result.diagnostic and "AssertionError" in result.diagnostic
    assert "noise" not in result.diagnostic


def test_huge_output_is_capped(tmp_path):
    out = "E   " + "x" * 50000 + "\n" + "E   y\n" * 5000
    result = adapter(tmp_path, FakeRunner(returncode=1, stdout=out)).validate(make_task(), "x")
    assert 0 < len(result.diagnostic) <= MAX_DIAGNOSTIC < 4000


def test_unfilterable_output_falls_back_to_tail(tmp_path):
    result = adapter(tmp_path, FakeRunner(returncode=2, stdout="boom\n")).validate(make_task(), "x")
    assert "boom" in result.diagnostic and not result.infra_failure


def test_no_tests_collected_is_a_runner_pass_left_to_the_audit(tmp_path):
    a = adapter(tmp_path, FakeRunner(returncode=5, stdout="no tests ran"))
    assert a.validate(make_task(), "x = 1\n").passed
    assert a.audit(make_task(), "def helper():\n    pass\n") is AuditOutcome.TEST_FREE
    assert a.audit(make_task(), "def test_a():\n    slugify('a')\n") is AuditOutcome.ASSERTION_FREE


def test_timeout_is_infrastructure_failure(tmp_path):
    runner = FakeRunner(raises=subprocess.TimeoutExpired("pytest", 5))
    a = adapter(tmp_path, runner)
    result = a.validate(make_task(), "x")
    assert not result.passed and result.infra_failure and "timed out" in result.diagnostic
    assert not Path(runner.calls[0][1]["cwd"]).exists()


@pytest.mark.parametrize("code", [3, 4])
def test_internal_and_usage_errors_are_infrastructure(tmp_path, code):
    result = adapter(tmp_path, FakeRunner(returncode=code, stdout="INTERNALERROR")).validate(
        make_task(), "x")
    assert result.infra_failure


def test_runner_exception_propagates_and_cleans_up(tmp_path):
    runner = FakeRunner(raises=OSError("no python"))
    a = adapter(tmp_path, runner)
    with pytest.raises(OSError):
        a.validate(make_task(), "x")
    assert not Path(runner.calls[0][1]["cwd"]).exists()


def test_audit_delegates_with_focal_name(tmp_path):
    a = adapter(tmp_path, FakeRunner())
    assert a.audit(make_task(), "def test_a():\n    assert slugify('A') == 'a'\n") is AuditOutcome.REAL


@pytest.mark.integration
def test_real_pytest_pass_fail_and_original_untouched(tmp_path):
    a = PythonPytestAdapter(make_project(tmp_path / "proj"), Path(sys.executable), timeout_s=120)
    before = snapshot(a.project_dir)
    ok = a.validate(make_task(), "from mini.text import slugify\n\n"
                    "def test_ok():\n    assert slugify(' A b ') == 'a-b'\n")
    bad = a.validate(make_task(), "from mini.text import slugify\n\n"
                     "def test_bad():\n    assert slugify('A') == 'zzz'\n")
    assert ok.passed
    assert not bad.passed and not bad.infra_failure and "zzz" in bad.diagnostic
    assert len(bad.diagnostic) < 4000
    assert snapshot(a.project_dir) == before


@pytest.mark.integration
def test_real_timeout_is_infrastructure(tmp_path):
    a = PythonPytestAdapter(make_project(tmp_path / "proj"), Path(sys.executable), timeout_s=2)
    result = a.validate(make_task(), "import time\n\ndef test_slow():\n    time.sleep(30)\n")
    assert result.infra_failure and not result.passed


@pytest.mark.parametrize("code", [-9, -1, 3221225477])
def test_process_killed_by_os_is_infrastructure(tmp_path, code):
    result = adapter(tmp_path, FakeRunner(returncode=code, stdout="")).validate(make_task(), "x")
    assert result.infra_failure and not result.passed


def test_missing_pytest_module_is_infrastructure(tmp_path):
    out = "C:\\py\\python.exe: No module named pytest\n"
    result = adapter(tmp_path, FakeRunner(returncode=1, stdout=out)).validate(make_task(), "x")
    assert result.infra_failure and not result.passed
    assert "No module named pytest" in result.diagnostic


@pytest.mark.parametrize("code", [1, 2])
def test_ordinary_failures_stay_model_failures(tmp_path, code):
    result = adapter(tmp_path, FakeRunner(returncode=code, stdout="E   assert 1 == 2\n")).validate(
        make_task(), "x")
    assert not result.infra_failure and not result.passed

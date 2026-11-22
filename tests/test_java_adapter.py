"""Pruebas del adaptador Java/Maven: unitarias con un runner inyectado e
integración contra el checkout fijado de Commons Lang."""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from vera.adapters.java_maven import JavaMavenAdapter, run_killing_tree
from vera.envinfo import COMMONS_LANG_DIR, MAVEN_BIN
from vera.types import AuditOutcome, Task

M2_DIR = "E:/vera-data/m2"


def make_task(test_name: str = "StringUtils_isEmpty_Test") -> Task:
    return Task(
        id="java-isEmpty",
        language="java",
        project="commons-lang",
        focal_name="isEmpty",
        focal_source="public static boolean isEmpty(CharSequence cs) { ... }",
        container="org.apache.commons.lang3.StringUtils",
        test_name=test_name,
        import_hint="import org.apache.commons.lang3.StringUtils;",
    )


class FakeRunner:
    """Simula subprocess.run y anota si el fichero generado existía al llamarle."""

    def __init__(self, repo: Path, returncode: int = 0, stdout: str = "", raises=None):
        self.repo = repo
        self.returncode = returncode
        self.stdout = stdout
        self.raises = raises
        self.calls: list[tuple[list[str], dict]] = []
        self.file_existed: bool | None = None

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        target = self.repo / "src/test/java/org/generated/StringUtils_isEmpty_Test.java"
        self.file_existed = target.exists()
        self.content = target.read_text(encoding="utf-8") if target.exists() else None
        if self.raises is not None:
            raise self.raises
        return subprocess.CompletedProcess(cmd, self.returncode, stdout=self.stdout, stderr="")


def adapter_with(tmp_path: Path, runner: FakeRunner) -> JavaMavenAdapter:
    return JavaMavenAdapter(
        repo=tmp_path, mvn=Path("mvn.cmd"), m2=Path("E:/m2"), timeout_s=5, runner=runner
    )


def generated_dir(repo: Path) -> Path:
    return repo / "src/test/java/org/generated"


def test_writes_file_then_removes_it(tmp_path):
    runner = FakeRunner(tmp_path)
    result = adapter_with(tmp_path, runner).validate(make_task(), "class X {}")
    assert runner.file_existed is True
    assert runner.content == "class X {}"
    assert not generated_dir(tmp_path).exists()
    cmd, kwargs = runner.calls[0]
    assert cmd == [
        "mvn.cmd", "-o", "-B", "-q", "-Dmaven.repo.local=" + str(Path("E:/m2")),
        "-Drat.skip=true", "-Dtest=StringUtils_isEmpty_Test",
        "-Dsurefire.failIfNoSpecifiedTests=false", "test",
    ]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["timeout"] == 5
    assert result.passed is True


def test_file_removed_even_if_runner_raises(tmp_path):
    runner = FakeRunner(tmp_path, raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        adapter_with(tmp_path, runner).validate(make_task(), "class X {}")
    assert runner.file_existed is True
    assert not generated_dir(tmp_path).exists()


def test_file_removed_on_timeout(tmp_path):
    runner = FakeRunner(tmp_path, raises=subprocess.TimeoutExpired("mvn", 5))
    adapter_with(tmp_path, runner).validate(make_task(), "class X {}")
    assert runner.file_existed is True
    assert not generated_dir(tmp_path).exists()


def test_timeout_is_infra_failure(tmp_path):
    runner = FakeRunner(tmp_path, raises=subprocess.TimeoutExpired("mvn", 5))
    result = adapter_with(tmp_path, runner).validate(make_task(), "class X {}")
    assert result.passed is False
    assert result.infra_failure is True
    assert "timed out" in result.diagnostic


SUREFIRE_FAILURE = (
    "[INFO] Scanning for projects...\r\n"
    + "[INFO] noise line\r\n" * 400
    + "[ERROR] Tests run: 1, Failures: 1, Errors: 0, Skipped: 0 <<< FAILURE! -- in org.generated.X\r\n"
    "[ERROR] org.generated.X.t -- Time elapsed: 0.055 s <<< FAILURE!\r\n"
    "org.opentest4j.AssertionFailedError: expected: <true> but was: <false>\r\n"
    + "\tat org.junit.jupiter.api.AssertTrue.assertTrue(AssertTrue.java:36)\r\n" * 50
    + "\tat org.generated.X.t(X.java:6)\r\n"
    "\r\n"
    "[ERROR] Failures: \r\n"
    "[ERROR]   X.t:6 expected: <true> but was: <false>\r\n"
    "[ERROR] Failed to execute goal org.apache.maven.plugins:maven-surefire-plugin:3.5.4:test"
    " (default-test) on project commons-lang3: There are test failures.\r\n"
    "[ERROR] \r\n"
    "[ERROR] -> [Help 1]\r\n"
    "[ERROR] To see the full stack trace of the errors, re-run Maven with the -e switch.\r\n"
    "[ERROR] Re-run Maven using the -X switch to enable full debug logging.\r\n"
    "[ERROR] [Help 1] http://cwiki.apache.org/confluence/display/MAVEN/MojoFailureException\r\n"
)


def test_nonzero_exit_returns_failed_with_trimmed_diagnostic(tmp_path):
    runner = FakeRunner(tmp_path, returncode=1, stdout=SUREFIRE_FAILURE)
    result = adapter_with(tmp_path, runner).validate(make_task(), "class X {}")
    assert result.passed is False
    assert result.infra_failure is False
    diag = result.diagnostic
    assert len(diag) < 4000
    assert diag.startswith("[ERROR] Tests run: 1, Failures: 1")
    assert "AssertionFailedError: expected: <true> but was: <false>" in diag
    assert "at org.generated.X.t(X.java:6)" in diag
    assert "X.t:6 expected: <true> but was: <false>" in diag
    assert "[INFO]" not in diag
    assert "AssertTrue.java" not in diag
    assert "[Help 1]" not in diag
    assert "re-run Maven" not in diag


def test_compilation_errors_are_kept_once_with_their_context(tmp_path):
    out = (
        "[ERROR] COMPILATION ERROR : \r\n"
        "[ERROR] /E:/x/X.java:[4,33] cannot find symbol\n"
        "  symbol:   method nope()\n"
        "  location: class org.generated.X\r\n"
        "[ERROR] Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin:3.14.1:"
        "testCompile (default-testCompile) on project commons-lang3: Compilation failure\r\n"
        "[ERROR] /E:/x/X.java:[4,33] cannot find symbol\r\n"
        "[ERROR]   symbol:   method nope()\r\n"
        "[ERROR]   location: class org.generated.X\r\n"
        "[ERROR] -> [Help 1]\r\n"
    )
    runner = FakeRunner(tmp_path, returncode=1, stdout=out)
    diag = adapter_with(tmp_path, runner).validate(make_task(), "class X {}").diagnostic
    assert diag.startswith("[ERROR] COMPILATION ERROR")
    assert diag.count("cannot find symbol") == 1
    assert diag.count("symbol:   method nope()") == 1
    assert "location: class org.generated.X" in diag


def test_huge_diagnostic_is_capped_below_4000(tmp_path):
    out = "".join(f"[ERROR] /E:/x/X.java:[{i},1] cannot find symbol number {i}\r\n" for i in range(500))
    runner = FakeRunner(tmp_path, returncode=1, stdout=out)
    diag = adapter_with(tmp_path, runner).validate(make_task(), "class X {}").diagnostic
    assert len(diag) < 4000
    assert diag.startswith("[ERROR] /E:/x/X.java:[0,1]")


def test_dependency_resolution_error_is_infra_failure(tmp_path):
    out = (
        "[ERROR] Failed to execute goal on project commons-lang3: Could not resolve dependencies"
        " for project org.apache.commons:commons-lang3:jar:3.19.0\r\n"
    )
    runner = FakeRunner(tmp_path, returncode=1, stdout=out)
    result = adapter_with(tmp_path, runner).validate(make_task(), "class X {}")
    assert result.passed is False
    assert result.infra_failure is True
    assert "Could not resolve dependencies" in result.diagnostic


def test_offline_missing_artifact_is_infra_failure(tmp_path):
    out = (
        "[ERROR] Failed to execute goal org.apache.maven.plugins:maven-surefire-plugin:3.5.4:test"
        " (default-test) on project commons-lang3: The following artifacts could not be resolved:"
        " x (absent): Cannot access central (https://repo.maven.apache.org/maven2) in offline mode\r\n"
    )
    runner = FakeRunner(tmp_path, returncode=1, stdout=out)
    assert adapter_with(tmp_path, runner).validate(make_task(), "class X {}").infra_failure is True


def test_exit_zero_with_no_tests_executed_passes(tmp_path):
    runner = FakeRunner(tmp_path, returncode=0, stdout="[WARNING] No tests were executed!\r\n")
    result = adapter_with(tmp_path, runner).validate(make_task(), "class X {}")
    assert result.passed is True
    assert result.infra_failure is False


def test_audit_delegates_to_audit_java(tmp_path):
    adapter = adapter_with(tmp_path, FakeRunner(tmp_path))
    code = "class T { @Test void t() { assertTrue(StringUtils.isEmpty(\"\")); } }"
    assert adapter.audit(make_task(), code) is AuditOutcome.REAL
    assert adapter.audit(make_task(), "class T { void t() {} }") is AuditOutcome.TEST_FREE


def test_default_runner_raises_timeout_and_kills_the_child():
    import sys
    started = time.perf_counter()
    with pytest.raises(subprocess.TimeoutExpired):
        run_killing_tree([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1, text=True)
    assert time.perf_counter() - started < 15


# --- Integración: requiere el entorno de la Tarea 6 -------------------------------

needs_java_env = pytest.mark.skipif(
    not (Path(COMMONS_LANG_DIR).is_dir() and Path(MAVEN_BIN).is_file() and Path(M2_DIR).is_dir()),
    reason="entorno Java de la Tarea 6 ausente",
)

HEADER = (
    "package org.generated;\n"
    "import static org.junit.jupiter.api.Assertions.*;\n"
    "import org.apache.commons.lang3.StringUtils;\n"
    "import org.junit.jupiter.api.Test;\n"
)


@pytest.fixture(scope="module")
def real_adapter():
    adapter = JavaMavenAdapter(repo=Path(COMMONS_LANG_DIR), mvn=Path(MAVEN_BIN), m2=Path(M2_DIR))
    yield adapter
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=COMMONS_LANG_DIR, capture_output=True, text=True
    )
    assert status.stdout == ""


@pytest.mark.integration
@needs_java_env
def test_integration_correct_test_passes(real_adapter):
    task = make_task("VeraIntegOkTest")
    code = HEADER + (
        "public class VeraIntegOkTest {\n"
        "  @Test void empty() { assertTrue(StringUtils.isEmpty(\"\")); }\n"
        "  @Test void notEmpty() { assertFalse(StringUtils.isEmpty(\"x\")); }\n"
        "}\n"
    )
    result = real_adapter.validate(task, code)
    assert result.passed is True, result.diagnostic
    assert result.infra_failure is False
    assert real_adapter.audit(task, code) is AuditOutcome.REAL


@pytest.mark.integration
@needs_java_env
def test_integration_false_assertion_fails(real_adapter):
    task = make_task("VeraIntegFailTest")
    code = HEADER + (
        "public class VeraIntegFailTest {\n"
        "  @Test void wrong() { assertTrue(StringUtils.isEmpty(\"x\")); }\n"
        "}\n"
    )
    result = real_adapter.validate(task, code)
    assert result.passed is False
    assert result.infra_failure is False
    assert "AssertionFailedError" in result.diagnostic
    assert len(result.diagnostic) < 4000


@pytest.mark.integration
@needs_java_env
def test_integration_compilation_error(real_adapter):
    task = make_task("VeraIntegCompileTest")
    code = HEADER + (
        "public class VeraIntegCompileTest {\n"
        "  @Test void broken() { int x = \"a\"; }\n"
        "}\n"
    )
    result = real_adapter.validate(task, code)
    assert result.passed is False
    assert result.infra_failure is False
    assert "COMPILATION ERROR" in result.diagnostic
    assert "incompatible types" in result.diagnostic
    assert len(result.diagnostic) < 4000


@pytest.mark.integration
@needs_java_env
def test_integration_file_without_test_passes_and_audits_test_free(real_adapter):
    task = make_task("VeraIntegNoTest")
    code = HEADER + (
        "public class VeraIntegNoTest {\n"
        "  void helper() { StringUtils.isEmpty(\"\"); }\n"
        "}\n"
    )
    result = real_adapter.validate(task, code)
    assert result.passed is True, result.diagnostic
    assert real_adapter.audit(task, code) is AuditOutcome.TEST_FREE

import subprocess
from pathlib import Path

from vera import envinfo
from vera.envinfo import collect_env_manifest, parse_mvn_version

CLAVES = {"python", "java", "maven", "commons_lang_commit", "ollama_version", "gpu", "models"}


def test_parse_mvn_version_extracts_semver():
    salida = "Apache Maven 3.9.9 (8e8579a9e76f7d015ee5ec7bfcdc97d260186937)\nMaven home: E:\\x"
    assert envinfo.parse_mvn_version(salida) == "3.9.9"
    assert parse_mvn_version("basura") == ""


def test_manifest_has_required_keys(monkeypatch):
    def falso_run(cmd, cwd=None):
        nombre = cmd[0]
        if nombre.endswith("java"):
            return 'openjdk version "11.0.23" 2024-04-16'
        if "mvn" in nombre:
            return "Apache Maven 3.9.9 (abc)"
        if nombre == "git":
            return "89bb30909bf873d75f5e06d144f9b2e72d74c076"
        if nombre == "nvidia-smi":
            return "NVIDIA GeForce RTX, 8192 MiB, 555.1"
        return ""

    def falso_http(url):
        if url.endswith("/api/version"):
            return {"version": "0.6.0"}
        return {"models": [{"name": "llama3.1:8b", "digest": "abc123"}]}

    monkeypatch.setattr(envinfo, "_run", falso_run)
    monkeypatch.setattr(envinfo, "_http_json", falso_http)
    m = collect_env_manifest(["llama3.1:8b", "ausente:1b"])
    assert CLAVES <= set(m)
    assert m["maven"] == "3.9.9"
    assert m["java"].startswith("openjdk version")
    assert m["commons_lang_commit"] == "89bb30909bf873d75f5e06d144f9b2e72d74c076"
    assert m["models"]["llama3.1:8b"] == "abc123"
    assert m["models"]["ausente:1b"] is None


REPORT = "target/surefire-reports/TEST-org.generated.VeraEnvCheckTest.xml"


class SurefireRunner:
    """Simula Maven: anota el comando y el fichero generado, y escribe el informe."""

    def __init__(self, repo: Path, returncode=0, stdout="", tests=1):
        self.repo, self.returncode, self.stdout, self.tests = repo, returncode, stdout, tests
        self.cmd = None
        self.file_existed = None

    def __call__(self, cmd, **kwargs):
        self.cmd = cmd
        self.file_existed = (self.repo / "src/test/java/org/generated/VeraEnvCheckTest.java").exists()
        if self.returncode == 0 and self.tests is not None:
            report = self.repo / REPORT
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(f'<testsuite name="x" tests="{self.tests}" failures="0"/>', encoding="utf-8")
        return subprocess.CompletedProcess(cmd, self.returncode, stdout=self.stdout, stderr="")


def check(tmp_path, runner):
    return envinfo.check_surefire_offline(tmp_path, Path("mvn.cmd"), Path("E:/m2"), runner=runner)


def test_surefire_check_passes_when_one_test_runs(tmp_path):
    runner = SurefireRunner(tmp_path)
    assert check(tmp_path, runner) is None
    assert runner.file_existed is True
    assert "-o" in runner.cmd and "-Drat.skip=true" in runner.cmd and "-Dtest=VeraEnvCheckTest" in runner.cmd
    assert not (tmp_path / "src/test/java/org/generated").exists()


def test_surefire_check_fails_when_no_test_executed(tmp_path):
    msg = check(tmp_path, SurefireRunner(tmp_path, tests=0))
    assert msg is not None and "Tests run: 1" in msg


def test_surefire_check_ignores_stale_report(tmp_path):
    stale = tmp_path / REPORT
    stale.parent.mkdir(parents=True)
    stale.write_text('<testsuite tests="1"/>', encoding="utf-8")
    msg = check(tmp_path, SurefireRunner(tmp_path, tests=None))
    assert msg is not None and "Tests run: 1" in msg


def test_surefire_check_names_the_missing_artifact(tmp_path):
    out = (
        "[ERROR] Failed to execute goal org.apache.maven.plugins:maven-surefire-plugin:3.5.4:test"
        " (default-test) on project commons-lang3: The following artifacts could not be resolved:"
        " org.apache.maven.surefire:surefire-junit-platform:jar:3.5.4 (absent): Cannot access central"
        " (https://repo.maven.apache.org/maven2) in offline mode and the artifact"
        " org.apache.maven.surefire:surefire-junit-platform:jar:3.5.4 has not been downloaded from it before."
        " -> [Help 1]\r\n"
    )
    msg = check(tmp_path, SurefireRunner(tmp_path, returncode=1, stdout=out))
    assert msg is not None
    assert "org.apache.maven.surefire:surefire-junit-platform:jar:3.5.4" in msg
    assert not (tmp_path / "src/test/java/org/generated").exists()


def test_surefire_check_reports_other_failures(tmp_path):
    out = "[ERROR] COMPILATION ERROR : \r\n[ERROR] /x/Y.java:[1,1] boom\r\n"
    msg = check(tmp_path, SurefireRunner(tmp_path, returncode=1, stdout=out))
    assert msg is not None and "boom" in msg

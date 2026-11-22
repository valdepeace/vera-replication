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

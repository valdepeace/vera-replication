"""CLI fino sobre vera.envinfo: verifica el entorno de VERA-01 y sale con 1 si algo no cumple."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from vera import envinfo  # noqa: E402

MODELOS = ["llama3.1:8b", "qwen2.5-coder:7b", "qwen3:8b", "gemma4:e4b"]


def main() -> int:
    manifiesto = envinfo.collect_env_manifest(MODELOS)
    print(json.dumps(manifiesto, indent=2, ensure_ascii=False))
    fallos = []
    if manifiesto["commons_lang_commit"] != envinfo.COMMONS_LANG_COMMIT:
        fallos.append("el commit de Commons Lang no es el fijado")
    if not manifiesto["maven"]:
        fallos.append("Maven no responde")
    if not manifiesto["ollama_version"]:
        fallos.append("Ollama no responde")
    for nombre, digest in manifiesto["models"].items():
        if not digest:
            fallos.append(f"falta el modelo {nombre}")
    for base in envinfo.OLLAMA_URLS:
        try:
            envinfo._http_json(base + "/api/version")
        except Exception as exc:  # noqa: BLE001
            fallos.append(f"el servidor {base} no contesta: {exc}")
    surefire = envinfo.check_surefire_offline(
        Path(envinfo.COMMONS_LANG_DIR), Path(envinfo.MAVEN_BIN), Path(envinfo.M2_DIR)
    )
    if surefire is not None:
        fallos.append(surefire)
    for f in fallos:
        print("FALLO:", f, file=sys.stderr)
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())

"""Puerta de calidad: las diez tareas de StringUtils con el prompt real de generación,
temperatura 0,7 y semilla 1 (envoltorio de vera.gate).
Uso: .venv/Scripts/python scripts/gate_model.py [--models m1 m2 ...]
Escribe results/fase1/gate-<modelo>.json; sale con 1 si algún modelo no pasa."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vera import gate  # noqa: E402
from vera.blocks import DETERMINISTIC, load_tasks  # noqa: E402
from vera.engines.ollama import OllamaEngine  # noqa: E402
from vera.models import MODELS  # noqa: E402

ORDEN = ["qwen2.5-coder:7b", "qwen3:8b", "llama3.1:8b", "gemma4:e4b"]
OUT_DIR = ROOT / "results/fase1"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=ORDEN)
    args = p.parse_args()
    tareas = DETERMINISTIC.task_filter(load_tasks("java"))  # los diez métodos de StringUtils
    assert len(tareas) == gate.GATE_SIZE and all(t.container == "StringUtils" for t in tareas)
    fallidos = []
    for nombre in args.models:
        base = MODELS[nombre].base_url
        gate.unload_and_wait(base, nombre)
        print(f"puerta de {nombre}...", file=sys.stderr, flush=True)
        resultados = gate.run_gate(OllamaEngine(base, timeout_s=900), nombre, tareas)
        veredicto = gate.evaluate_gate(resultados)
        libre = gate.unload_and_wait(base, nombre)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"gate-{nombre.replace(':', '_')}.json").write_text(json.dumps(
            {"model": nombre, "passed": veredicto.passed, "reasons": veredicto.reasons,
             "vram_after": libre, "results": resultados}, indent=2, ensure_ascii=False),
            encoding="utf-8")
        print(f"{nombre}: {'PASA' if veredicto.passed else 'NO PASA'}", flush=True)
        for razon in veredicto.reasons:
            print(f"  - {razon}", flush=True)
        if not veredicto.passed:
            fallidos.append(nombre)
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())

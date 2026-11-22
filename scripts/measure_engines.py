"""Carga en frío y en caliente de los cuatro modelos con num_ctx 8192 (envoltorio de vera.gate).

Uso: .venv/Scripts/python scripts/measure_engines.py [--models m1 m2 ...] [--warm 3]
Escribe results/fase1/engines.json. Carga un único modelo cada vez y lo descarga antes del siguiente."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vera import gate  # noqa: E402
from vera.blocks import load_tasks  # noqa: E402
from vera.models import MODELS  # noqa: E402

ORDEN = ["qwen2.5-coder:7b", "qwen3:8b", "llama3.1:8b", "gemma4:e4b"]
OUT = ROOT / "results/fase1/engines.json"
_SHOW_KEYS = ("details", "capabilities", "parameters", "model_info")


def medir(nombre: str, warm: int) -> dict:
    base = MODELS[nombre].base_url
    tareas = load_tasks("java")
    antes = gate.unload_and_wait(base, nombre)
    show = gate.http_json(base + "/api/show", {"model": nombre})
    fila = {"model": nombre, "server": base, "vram_before": antes,
            "show": {k: show.get(k) for k in _SHOW_KEYS}}
    cuerpo = gate.http_json(base + "/api/chat", gate.measurement_payload(nombre, tareas[0], 1))
    fila["cold"] = gate.chat_metrics(cuerpo) | {"chars": len(cuerpo["message"]["content"])}
    ps = gate.http_json(base + "/api/ps")
    fila["ps_raw"] = [m for m in ps.get("models", []) if nombre in (m.get("name"), m.get("model"))]
    fila["residency"] = gate.gpu_residency(ps, nombre)
    usada, total = gate.nvidia_smi_memory()
    fila["vram_loaded"] = {"vram_used_mib": usada, "vram_total_mib": total}
    fila["warm"] = []
    for i in range(1, warm + 1):
        cuerpo = gate.http_json(base + "/api/chat",
                                gate.measurement_payload(nombre, tareas[i], 1 + i))
        fila["warm"].append(gate.chat_metrics(cuerpo) | {"chars": len(cuerpo["message"]["content"])})
    fila["vram_after"] = gate.unload_and_wait(base, nombre)
    return fila


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=ORDEN)
    p.add_argument("--warm", type=int, default=3)
    args = p.parse_args()
    filas = []
    for nombre in args.models:
        print(f"midiendo {nombre}...", file=sys.stderr, flush=True)
        fila = medir(nombre, args.warm)
        filas.append(fila)
        c, r = fila["cold"], fila["residency"] or {}
        tok = [w["tok_s"] for w in fila["warm"] if w["tok_s"]]
        print(f"{nombre}: carga {c['load_s']:.1f} s, frío {c['tok_s'] or 0:.1f} tok/s, "
              f"caliente {sum(tok) / len(tok) if tok else 0:.1f} tok/s, "
              f"GPU {r.get('size_vram_gb')}/{r.get('size_gb')} GB, "
              f"nvidia-smi {fila['vram_loaded']['vram_used_mib']} MiB, "
              f"después {fila['vram_after']}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(filas, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"escrito {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Tiempos de una validación Java correcta con el adaptador real: la primera en frío y
las siguientes en caliente. Uso: .venv/Scripts/python scripts/measure_maven.py [--n 6] [--full]
--full mide el comando completo de la Tarea 7 (sin FAST_FLAGS), como referencia del antes.
Escribe results/fase1/maven.json (o maven-full.json con --full)."""
import argparse
import statistics
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vera.__main__ import _java_adapter  # noqa: E402
from vera.adapters import java_maven  # noqa: E402
from vera.blocks import load_tasks  # noqa: E402

OUT = ROOT / "results/fase1/maven.json"
OUT_FULL = ROOT / "results/fase1/maven-full.json"


def _full_runner(cmd, **kwargs):
    return java_maven.run_killing_tree([a for a in cmd if a not in java_maven.FAST_FLAGS], **kwargs)
CORRECTO = """package org.generated;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.apache.commons.lang3.StringUtils;
import org.junit.jupiter.api.Test;

public class Generated_StringUtils_isEmpty_Test {
    @Test
    void detectsEmptyAndNull() {
        assertTrue(StringUtils.isEmpty(null));
        assertTrue(StringUtils.isEmpty(""));
        assertFalse(StringUtils.isEmpty(" "));
        assertFalse(StringUtils.isEmpty("bob"));
    }
}
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=6, help="validaciones (mínimo 6: 1 en frío + 5)")
    p.add_argument("--full", action="store_true", help="comando completo, sin FAST_FLAGS")
    args = p.parse_args()
    tarea = next(t for t in load_tasks("java") if t.id == "java-StringUtils-isEmpty")
    adaptador = _java_adapter()
    out = OUT
    if args.full:
        adaptador.runner = _full_runner
        out = OUT_FULL
    filas = []
    for i in range(max(args.n, 6)):
        r = adaptador.validate(tarea, CORRECTO)
        filas.append({"index": i, "cold": i == 0, "passed": r.passed, "seconds": r.seconds,
                      "infra_failure": r.infra_failure, "diagnostic": r.diagnostic[:500]})
        print(f"{i}: passed={r.passed} {r.seconds:.1f} s", flush=True)
    caliente = [f["seconds"] for f in filas[1:]]
    resumen = {"cold_s": filas[0]["seconds"], "warm_median_s": statistics.median(caliente),
               "warm_min_s": min(caliente), "warm_max_s": max(caliente),
               "all_passed": all(f["passed"] for f in filas)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": resumen, "runs": filas}, indent=2), encoding="utf-8")
    print(json.dumps(resumen))
    return 0 if resumen["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

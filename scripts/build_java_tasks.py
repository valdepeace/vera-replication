"""Escribe benchmarks/vera01/replica/java/tasks.json a partir del checkout fijado."""
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vera.javasrc import build_tasks  # noqa: E402

REPO = Path("E:/vera-data/commons-lang")
OUT = ROOT / "benchmarks/vera01/replica/java/tasks.json"


def main() -> int:
    tasks = build_tasks(REPO)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps([asdict(t) for t in tasks], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"{len(tasks)} tareas escritas en {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

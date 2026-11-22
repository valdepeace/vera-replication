"""CLI de VERA-01: python -m vera run --block ... --language ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vera.blocks import BLOCKS, REPO_ROOT
from vera.types import RunRecord

ADAPTER_LANGUAGES = ("java",)


def _java_adapter():
    from vera.adapters.java_maven import JavaMavenAdapter
    from vera.envinfo import COMMONS_LANG_DIR, M2_DIR, MAVEN_BIN

    return JavaMavenAdapter(repo=Path(COMMONS_LANG_DIR), mvn=Path(MAVEN_BIN), m2=Path(M2_DIR))


def _report_progress(index: int, total: int, record: RunRecord) -> None:
    print(f"[{index + 1}/{total}] {record.config.run_id}: {record.stop_reason}"
          f" valid={record.valid}", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vera")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="ejecuta un bloque experimental")
    run.add_argument("--block", choices=sorted(BLOCKS), required=True)
    run.add_argument("--language", choices=("java", "python", "node"), required=True)
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.language not in ADAPTER_LANGUAGES:
        run.error(f"el lenguaje '{args.language}' todavia no tiene adaptador; "
                  f"disponibles: {', '.join(ADAPTER_LANGUAGES)}")
    if args.limit is not None and args.limit < 0:
        run.error("--limit debe ser un entero no negativo")

    from vera.engines.ollama import OllamaEngine
    from vera.models import MODELS
    from vera.runner import run_block

    block = BLOCKS[args.block]
    engines = {name: OllamaEngine(MODELS[name].base_url) for name in block.models}
    summary = run_block(
        block, args.language, results_root=REPO_ROOT / "results",
        engines=engines, adapters={"java": _java_adapter()},
        limit=args.limit, dry_run=args.dry_run,
        on_record=_report_progress,
    )
    if args.dry_run:
        print(f"{summary.total} ejecuciones planificadas")
    else:
        print(f"total={summary.total} ejecutadas={summary.executed} reanudadas={summary.resumed} "
              f"aceptadas={summary.accepted} validas={summary.valid} invalidas={summary.invalid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""CLI de VERA-01: python -m vera {run,report} --block ... --language ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from vera.blocks import BLOCKS, REPO_ROOT
from vera.types import RunRecord

ADAPTER_LANGUAGES = ("java", "python", "node")


def _java_adapter():
    from vera.adapters.java_maven import JavaMavenAdapter
    from vera.envinfo import COMMONS_LANG_DIR, M2_DIR, MAVEN_BIN

    return JavaMavenAdapter(repo=Path(COMMONS_LANG_DIR), mvn=Path(MAVEN_BIN), m2=Path(M2_DIR))


def _python_adapter():
    from vera.adapters.python_pytest import PythonPytestAdapter

    return PythonPytestAdapter(project_dir=Path("E:/vera-data/pydash/src"), python=Path(sys.executable))


def _node_adapter():
    from vera.adapters.node_test import NodeTestAdapter

    return NodeTestAdapter(project_dir=Path("E:/vera-data/validatorjs/lib"),
                           node=Path("C:/Program Files/nodejs/node.exe"))


_ADAPTERS = {"java": _java_adapter, "python": _python_adapter, "node": _node_adapter}


def _report_progress(index: int, total: int, record: RunRecord) -> None:
    print(f"[{index + 1}/{total}] {record.config.run_id}: {record.stop_reason}"
          f" valid={record.valid}", file=sys.stderr, flush=True)


def _report(block_name: str, language: str, partial: bool = False,
            include: tuple[str, ...] = ()) -> int:
    from vera.analysis.report import IncompleteBlockError, planned_run_ids, render_markdown
    from vera.runner import block_dir
    from vera.store import RunStore

    records, tmp_files, planned = [], 0, set()
    for name in (block_name, *include):
        records_dir = block_dir(REPO_ROOT / "results", BLOCKS[name], language) / "records"
        records += list(RunStore(records_dir).load_all())
        tmp_files += len(list(records_dir.glob("*.tmp"))) if records_dir.is_dir() else 0
        planned |= planned_run_ids(name, language)
    invalid = sum(not r.valid for r in records)
    print(f"ejecuciones={len(records)} invalidas={invalid} tmp_sin_cerrar={tmp_files}")
    print()
    try:
        print(render_markdown(records, block=block_name, partial_ok=partial,
                              planned_ids=planned, include=include))
    except IncompleteBlockError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m vera")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="ejecuta un bloque experimental")
    run.add_argument("--block", choices=sorted(BLOCKS), required=True)
    run.add_argument("--language", choices=("java", "python", "node"), required=True)
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--skip-infra-failed", action="store_true",
                     help="no repetir las ejecuciones guardadas con fallo de infraestructura")
    report = sub.add_parser("report", help="resume en Markdown las ejecuciones de un bloque")
    report.add_argument("--block", choices=sorted(BLOCKS), required=True)
    report.add_argument("--language", choices=("java", "python", "node"), required=True)
    report.add_argument("--with", dest="extra", nargs="+", choices=sorted(BLOCKS), default=[],
                        help="suma al informe los registros de otros bloques (la ampliación)")
    report.add_argument("--partial", action="store_true",
                        help="presenta un bloque incompleto marcado como PARCIAL (no es una métrica)")
    args = parser.parse_args(argv)

    if args.command == "report":
        return _report(args.block, args.language, args.partial, tuple(args.extra))
    if args.language not in ADAPTER_LANGUAGES:
        run.error(f"el lenguaje '{args.language}' todavia no tiene adaptador; "
                  f"disponibles: {', '.join(ADAPTER_LANGUAGES)}")
    if args.limit is not None and args.limit < 0:
        run.error("--limit debe ser un entero no negativo")

    from vera.engines.ollama import OllamaEngine
    from vera.models import MODELS
    from vera import runner

    block = BLOCKS[args.block]
    engines = {name: OllamaEngine(MODELS[name].base_url) for name in block.models}
    try:
        summary = runner.run_block(
            block, args.language, results_root=REPO_ROOT / "results",
            engines=engines, adapters={args.language: _ADAPTERS[args.language]()},
            limit=args.limit, dry_run=args.dry_run, skip_infra_failed=args.skip_infra_failed,
            on_record=_report_progress,
        )
    except runner.BlockAborted as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"{summary.total} ejecuciones planificadas")
    else:
        print(f"total={summary.total} ejecutadas={summary.executed} reanudadas={summary.resumed} "
              f"aceptadas={summary.accepted} validas={summary.valid} invalidas={summary.invalid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

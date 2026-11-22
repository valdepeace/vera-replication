"""Ejecución de bloques: reanudación, reintento de fallos de infraestructura y manifiesto."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from vera.adapters.base import LanguageAdapter
from vera.blocks import REPO_ROOT, BlockSpec, expand_block, load_tasks
from vera.engines.base import ChatEngine
from vera.envinfo import collect_env_manifest
from vera.prompts import PROMPT_VERSION
from vera.store import RunStore
from vera.types import RunConfig, RunRecord
from vera.workflow import run_workflow


@dataclass
class BlockSummary:
    total: int
    executed: int = 0
    resumed: int = 0
    accepted: int = 0
    valid: int = 0
    invalid: int = 0


def _run_with_retries(config: RunConfig, engine: ChatEngine, adapter: LanguageAdapter,
                      retries: int) -> RunRecord:
    record: RunRecord | None = None
    for _ in range(1 + retries):
        try:
            record = run_workflow(config, engine, adapter)
        except Exception:  # noqa: BLE001 - toda excepción del motor o del flujo es infraestructura
            record = None
            continue
        if record.stop_reason != "infra_failure":
            return record
    if record is None:
        record = RunRecord(config=config, attempts=[], accepted=False,
                           stop_reason="infra_failure", audit=None, valid=False)
    return record


def execute_block(configs: list[RunConfig], engines: dict[str, ChatEngine],
                  adapters: dict[str, LanguageAdapter], store: RunStore, *,
                  retries: int = 2,
                  on_record: Callable[[int, int, RunRecord], None] | None = None) -> BlockSummary:
    summary = BlockSummary(total=len(configs))
    for index, config in enumerate(configs):
        if store.has(config.run_id):
            summary.resumed += 1
            continue
        record = _run_with_retries(config, engines[config.model.name],
                                   adapters[config.task.language], retries)
        store.save(record)
        summary.executed += 1
        summary.accepted += record.accepted
        summary.valid += record.valid
        summary.invalid += not record.valid
        if on_record is not None:
            on_record(index, len(configs), record)
    return summary


def block_dir(results_root: Path, block: BlockSpec, language: str) -> Path:
    return Path(results_root) / "runs" / block.name / language


def git_head() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _write_manifest(path: Path, block: BlockSpec, language: str, session: dict) -> None:
    """Añade la sesión al manifiesto: cada reanudación deja constancia de su entorno."""
    manifest = (json.loads(path.read_text(encoding="utf-8")) if path.is_file()
                else {"block": block.name, "language": language,
                      "prompt_version": PROMPT_VERSION, "sessions": []})
    manifest["sessions"].append(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run_block(block: BlockSpec, language: str, *, results_root: Path,
              engines: dict[str, ChatEngine], adapters: dict[str, LanguageAdapter],
              limit: int | None = None, dry_run: bool = False,
              env_collector: Callable[[list[str]], dict] = collect_env_manifest,
              harness_commit: Callable[[], str | None] = git_head,
              on_record: Callable[[int, int, RunRecord], None] | None = None) -> BlockSummary:
    configs = expand_block(block, load_tasks(language))
    if limit is not None:
        configs = configs[:limit]
    if dry_run:
        return BlockSummary(total=len(configs))
    out = block_dir(results_root, block, language)
    _write_manifest(out / "manifest.json", block, language, {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "harness_commit": harness_commit(),
        "planned": len(configs),
        "env": env_collector(list(block.models)),
    })
    return execute_block(configs, engines, adapters, RunStore(out / "records"),
                         on_record=on_record)

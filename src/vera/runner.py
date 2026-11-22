"""Ejecución de bloques: reanudación, reintento de fallos de infraestructura y manifiesto."""
from __future__ import annotations

import json
import subprocess
import sys
import time
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


RETRY_WAITS_S = (2, 5)
MAX_CONSECUTIVE_INFRA = 5


@dataclass
class BlockSummary:
    total: int
    executed: int = 0
    resumed: int = 0
    accepted: int = 0
    valid: int = 0
    invalid: int = 0


class BlockAborted(RuntimeError):
    """Corte del bloque por fallos de infraestructura consecutivos."""

    def __init__(self, message: str, summary: BlockSummary | None) -> None:
        super().__init__(message)
        self.summary = summary


def _run_with_retries(config: RunConfig, engine: ChatEngine, adapter: LanguageAdapter,
                      retries: int, sleep: Callable[[float], None]) -> RunRecord:
    """Repite la ejecución completa ante un fallo de infraestructura, con espera creciente."""
    infra_record: RunRecord | None = None  # último registro infra devuelto por el flujo
    error: str | None = None
    total = 1 + retries
    for attempt in range(total):
        if attempt:
            sleep(RETRY_WAITS_S[min(attempt - 1, len(RETRY_WAITS_S) - 1)])
        try:
            record = run_workflow(config, engine, adapter)
        except Exception as exc:  # noqa: BLE001 - toda excepción del motor o del flujo es infraestructura
            error = f"{type(exc).__name__}: {exc}"
        else:
            if record.stop_reason != "infra_failure":
                return record
            infra_record, error = record, record.infra_error
        print(f"[infra] {config.run_id} intento {attempt + 1}/{total}: {error}",
              file=sys.stderr, flush=True)
    attempts = infra_record.attempts if infra_record is not None else []
    return RunRecord(config=config, attempts=attempts, accepted=False,
                     stop_reason="infra_failure", audit=None, valid=False, infra_error=error)


def _is_done(store: RunStore, run_id: str, skip_infra_failed: bool) -> bool:
    if not store.has(run_id):
        return False
    return skip_infra_failed or store.load(run_id).stop_reason != "infra_failure"


def execute_block(configs: list[RunConfig], engines: dict[str, ChatEngine],
                  adapters: dict[str, LanguageAdapter], store: RunStore, *,
                  retries: int = 2, skip_infra_failed: bool = False,
                  sleep: Callable[[float], None] = time.sleep,
                  on_record: Callable[[int, int, RunRecord], None] | None = None) -> BlockSummary:
    """Ejecuta lo pendiente; los fallos de infraestructura guardados se repiten salvo
    skip_infra_failed. MAX_CONSECUTIVE_INFRA fallos seguidos abortan con BlockAborted."""
    summary = BlockSummary(total=len(configs))
    streak = 0
    for index, config in enumerate(configs):
        if _is_done(store, config.run_id, skip_infra_failed):
            summary.resumed += 1
            continue
        record = _run_with_retries(config, engines[config.model.name],
                                   adapters[config.task.language], retries, sleep)
        store.save(record)
        summary.executed += 1
        summary.accepted += record.accepted
        summary.valid += record.valid
        summary.invalid += not record.valid
        if on_record is not None:
            on_record(index, len(configs), record)
        streak = streak + 1 if record.stop_reason == "infra_failure" else 0
        if streak >= MAX_CONSECUTIVE_INFRA:
            raise BlockAborted(
                f"bloque abortado: {streak} ejecuciones seguidas con fallo de infraestructura "
                f"(última: {config.run_id}: {record.infra_error}); revise el servidor y reanude",
                summary,
            )
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
              skip_infra_failed: bool = False,
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
                         skip_infra_failed=skip_infra_failed, on_record=on_record)

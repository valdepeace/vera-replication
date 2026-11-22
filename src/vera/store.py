"""Almacen de trazas JSON atomico, con reanudacion."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

from .types import (
    Attempt,
    AuditOutcome,
    Condition,
    ModelSpec,
    RunConfig,
    RunRecord,
    Task,
    ValidationResult,
)


def _safe_name(run_id: str) -> str:
    readable = re.sub(r"[^A-Za-z0-9._-]+", "_", run_id).strip("_")
    digest = hashlib.sha1(run_id.encode("utf-8")).hexdigest()[:8]
    return f"{readable}-{digest}"


def _record_to_dict(record: RunRecord) -> dict:
    return asdict(record)


def _record_from_dict(d: dict) -> RunConfig | RunRecord:
    c = d["config"]
    config = RunConfig(
        block=c["block"],
        model=ModelSpec(**c["model"]),
        task=Task(**c["task"]),
        condition=Condition(c["condition"]),
        repetition=c["repetition"],
        seed=c["seed"],
        temperature=c["temperature"],
        prompt_version=c["prompt_version"],
        num_ctx=c["num_ctx"],
        num_predict=c["num_predict"],
        keep_alive=c["keep_alive"],
    )
    attempts = []
    for a in d["attempts"]:
        v = a["validation"]
        attempts.append(
            Attempt(
                **{**a, "validation": ValidationResult(**v) if v is not None else None}
            )
        )
    audit = d["audit"]
    return RunRecord(
        config=config,
        attempts=attempts,
        accepted=d["accepted"],
        stop_reason=d["stop_reason"],
        audit=AuditOutcome(audit) if audit is not None else None,
        valid=d["valid"],
        infra_error=d.get("infra_error"),  # ausente en registros anteriores al campo
    )


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _path(self, run_id: str) -> Path:
        return self.root / f"{_safe_name(run_id)}.json"

    def has(self, run_id: str) -> bool:
        return self._path(run_id).is_file()

    def save(self, record: RunRecord) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(record.config.run_id)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(
            json.dumps(_record_to_dict(record), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, target)

    def load(self, run_id: str) -> RunRecord:
        return _record_from_dict(json.loads(self._path(run_id).read_text(encoding="utf-8")))

    def load_all(self) -> Iterator[RunRecord]:
        if not self.root.is_dir():
            return
        for path in sorted(self.root.glob("*.json")):
            yield _record_from_dict(json.loads(path.read_text(encoding="utf-8")))

"""Bloques experimentales de VERA-01 y su expansión en ejecuciones."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from vera.models import MODELS
from vera.prompts import PROMPT_VERSION
from vera.types import Condition, RunConfig, Task

REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = REPO_ROOT / "benchmarks/vera01/replica"


@dataclass(frozen=True)
class BlockSpec:
    name: str
    models: list[str]
    temperature: float
    repetitions: int
    task_filter: Callable[[list[Task]], list[Task]]
    # Semilla común a todas las ejecuciones del bloque; None: semilla derivada del run_id.
    fixed_seed: int | None = None


DETERMINISTIC = BlockSpec(
    name="determinista",
    models=["llama3.1:8b", "qwen2.5-coder:7b"],
    temperature=0.0,
    repetitions=2,
    task_filter=lambda tasks: tasks[:10],  # los diez métodos de StringUtils, en su orden
    fixed_seed=42,
)

STATISTICAL = BlockSpec(
    name="estadistico",
    models=["llama3.1:8b", "qwen2.5-coder:7b", "qwen3:8b", "gemma4:e4b"],
    temperature=0.7,
    repetitions=15,
    task_filter=lambda tasks: list(tasks),
)

# Ampliación del bloque estadístico con el mismo prompt (vera01-p1), parámetros y tareas: Ornith 1.5 9B.
# Los dos MoE de 30B (qwen3-coder:30b y qwen3:30b-a3b) no superaron la puerta de velocidad
# (18,7 y 19,6 tok/s frente a un mínimo de 20) y quedan fuera, conforme a lo acordado.
EXTENSION = BlockSpec(
    name="ampliacion",
    models=["ornith-1.5:9b"],
    temperature=0.7,
    repetitions=15,
    task_filter=lambda tasks: list(tasks),
)

BLOCKS: dict[str, BlockSpec] = {b.name: b for b in (DETERMINISTIC, STATISTICAL, EXTENSION)}


def load_tasks(language: str) -> list[Task]:
    path = TASKS_ROOT / language / "tasks.json"
    return [Task(**d) for d in json.loads(path.read_text(encoding="utf-8"))]


def seed_for(run_id: str) -> int:
    """Semilla estable de 31 bits derivada del sha256 del run_id."""
    digest = hashlib.sha256(run_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def expand_block(block: BlockSpec, tasks: list[Task]) -> list[RunConfig]:
    """Ejecuciones agrupadas por modelo; dentro de cada modelo se recorren las
    repeticiones, luego las tareas, y se alternan las condiciones, de modo que
    la deriva temporal no recaiga sobre una sola condición."""
    selected = block.task_filter(tasks)
    configs: list[RunConfig] = []
    for model_name in block.models:
        model = MODELS[model_name]
        for repetition in range(1, block.repetitions + 1):
            for task in selected:
                for condition in Condition:
                    config = RunConfig(
                        block=block.name, model=model, task=task, condition=condition,
                        repetition=repetition, seed=0, temperature=block.temperature,
                        prompt_version=PROMPT_VERSION,
                    )
                    seed = block.fixed_seed if block.fixed_seed is not None else seed_for(config.run_id)
                    configs.append(replace(config, seed=seed))
    return configs

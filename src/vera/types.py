"""Tipos de dominio de VERA-01."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class Condition(str, Enum):
    BASELINE = "baseline"
    REPAIR = "repair"

    @property
    def max_repairs(self) -> int:
        return 0 if self is Condition.BASELINE else 3


class AuditOutcome(str, Enum):
    EMPTY = "EMPTY"
    TEST_FREE = "TEST_FREE"
    ASSERTION_FREE = "ASSERTION_FREE"
    NO_FOCAL = "NO_FOCAL"
    REAL = "REAL"


@dataclass(frozen=True)
class Task:
    id: str
    language: Literal["java", "python", "node"]
    project: str
    focal_name: str
    focal_source: str
    container: str
    test_name: str
    import_hint: str


@dataclass(frozen=True)
class ModelSpec:
    name: str
    engine: Literal["ollama", "llama-server"]
    base_url: str


@dataclass(frozen=True)
class RunConfig:
    block: str
    model: ModelSpec
    task: Task
    condition: Condition
    repetition: int
    seed: int
    temperature: float
    prompt_version: str
    num_ctx: int = 8192
    num_predict: int = 2048
    keep_alive: str = "30m"

    @property
    def run_id(self) -> str:
        return (
            f"{self.block}/{self.model.name}/{self.task.id}/"
            f"{self.condition.value}/r{self.repetition}"
        )


@dataclass
class ValidationResult:
    passed: bool
    diagnostic: str
    seconds: float
    infra_failure: bool = False


@dataclass
class Attempt:
    index: int
    kind: Literal["generate", "repair"]
    prompt: str
    raw_response: str
    parse_ok: bool
    parse_error: str | None
    code: str | None
    truncated: bool
    validation: ValidationResult | None
    prompt_tokens: int
    completion_tokens: int
    seconds: float


@dataclass
class RunRecord:
    config: RunConfig
    attempts: list[Attempt]
    accepted: bool
    stop_reason: Literal["accepted", "budget_exhausted", "infra_failure"]
    audit: AuditOutcome | None
    valid: bool
    # Tipo y mensaje del último fallo de infraestructura; None si no lo hubo.
    infra_error: str | None = None

    @property
    def total_prompt_tokens(self) -> int:
        return sum(a.prompt_tokens for a in self.attempts)

    @property
    def total_completion_tokens(self) -> int:
        return sum(a.completion_tokens for a in self.attempts)

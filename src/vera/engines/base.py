"""Contrato común de los motores de inferencia."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass
class ChatOptions:
    num_ctx: int
    num_predict: int
    temperature: float
    seed: int
    keep_alive: str


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    load_seconds: float
    total_seconds: float
    truncated: bool


class EngineError(Exception):
    """Fallo de infraestructura del motor, clasificado por `kind`."""

    def __init__(
        self,
        kind: Literal["connection", "server", "timeout", "model_missing"],
        message: str = "",
    ) -> None:
        super().__init__(message or kind)
        self.kind = kind


class ChatEngine(Protocol):
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        options: ChatOptions,
        json_schema: dict | None,
    ) -> ChatResult: ...

"""Contrato común de los adaptadores de lenguaje."""
from __future__ import annotations

from typing import Protocol

from vera.types import AuditOutcome, Task, ValidationResult


class LanguageAdapter(Protocol):
    def validate(self, task: Task, code: str) -> ValidationResult: ...

    def audit(self, task: Task, code: str) -> AuditOutcome: ...

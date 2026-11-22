"""Parser tolerante de la salida estructurada del modelo."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

ParseError = Literal["invalid_json", "missing_code", "empty_code"]

# Dos literales de cadena JSON unidos por `+`.
_STR = r'"(?:[^"\\\n]|\\.)*"'
_CONCAT = re.compile(r"(" + _STR + r")\s*\+\s*(" + _STR + r")")


@dataclass(frozen=True)
class ParseResult:
    code: str | None
    note: str | None
    error: ParseError | None


def _join_literals(text: str) -> str:
    def merge(m: re.Match[str]) -> str:
        return m.group(1)[:-1] + m.group(2)[1:]

    previous = None
    while previous != text:
        previous = text
        text = _CONCAT.sub(merge, text, count=1)
    return text


def _load(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_join_literals(text))


def parse_model_output(text: str) -> ParseResult:
    try:
        data = _load(text)
    except (json.JSONDecodeError, ValueError):
        return ParseResult(None, None, "invalid_json")
    if not isinstance(data, dict):
        return ParseResult(None, None, "invalid_json")
    note = data.get("note")
    note = note if isinstance(note, str) else None
    if "code" not in data:
        return ParseResult(None, note, "missing_code")
    code = data["code"]
    if not isinstance(code, str) or not code.strip():
        return ParseResult(None, note, "empty_code")
    return ParseResult(code, note, None)

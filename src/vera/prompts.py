"""Prompts versionados y esquema de salida estructurada."""
from __future__ import annotations

from vera.types import Task

PROMPT_VERSION = "vera01-p1"
MAX_DIAGNOSTIC_CHARS = 4000

OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["code", "note"],
}

_SYSTEM = (
    "You are an expert software engineer who writes unit tests. "
    "Answer with a single JSON object and nothing else: no Markdown, no code fences, "
    'no prose. The object has exactly two string fields: "code" (the complete test '
    'file) and "note" (one short sentence about the test).'
)

_LANGUAGE_RULES = {
    "java": (
        "Write a JUnit 5 test class (org.junit.jupiter.api) in Java.\n"
        "The file must start with: package org.generated;\n"
        "The public test class must be named exactly {test_name}.\n"
        "Import the class under test as {container}.\n"
        "Every test method must use @Test and real assertions."
    ),
    "python": (
        "Write a pytest test module in Python.\n"
        "Import the function under test with: {import_hint}\n"
        "Use plain test functions named test_* with assert statements."
    ),
    "node": (
        "Write an ES module test file for the Node.js built-in runner.\n"
        "Use: import {{ test }} from 'node:test'; and import assert from 'node:assert/strict';\n"
        "Import the function under test with: {import_hint}\n"
        "Every test must make real assertions."
    ),
}


def _task_block(task: Task) -> str:
    rules = _LANGUAGE_RULES[task.language].format(
        test_name=task.test_name,
        container=task.container,
        import_hint=task.import_hint,
    )
    return (
        f"Write unit tests for the {task.language} function {task.focal_name} "
        f"from {task.container}.\n\n"
        f"Source under test:\n{task.focal_source}\n\n"
        f"Rules:\n{rules}"
    )


def generation_messages(task: Task) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _task_block(task)},
    ]


def repair_messages(task: Task, previous_code: str, diagnostic: str) -> list[dict[str, str]]:
    trimmed = diagnostic[:MAX_DIAGNOSTIC_CHARS]
    content = (
        f"{_task_block(task)}\n\n"
        f"Your previous test file failed.\n\n"
        f"Previous test file:\n{previous_code}\n\n"
        f"Diagnostic:\n{trimmed}\n\n"
        "Return the complete corrected test file in the same JSON format."
    )
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": content},
    ]

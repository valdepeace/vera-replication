from vera.prompts import (
    MAX_DIAGNOSTIC_CHARS,
    OUTPUT_SCHEMA,
    PROMPT_VERSION,
    generation_messages,
    repair_messages,
)
from vera.types import Task


def make_task(language="java", **kw):
    base = dict(
        id=f"{language}-isBlank",
        language=language,
        project="demo",
        focal_name="isBlank",
        focal_source="public static boolean isBlank(CharSequence cs) { return true; }",
        container="org.apache.commons.lang3.StringUtils",
        test_name="StringUtils_isBlank_Test",
        import_hint="from targets import is_blank",
    )
    base.update(kw)
    return Task(**base)


def text_of(messages):
    return "\n".join(m["content"] for m in messages)


def test_constants():
    assert PROMPT_VERSION == "vera01-p1"
    assert MAX_DIAGNOSTIC_CHARS == 4000
    assert OUTPUT_SCHEMA["type"] == "object"
    assert OUTPUT_SCHEMA["properties"] == {"code": {"type": "string"}, "note": {"type": "string"}}
    assert sorted(OUTPUT_SCHEMA["required"]) == ["code", "note"]


def test_generation_messages_identical_for_both_conditions():
    task = make_task()
    first = generation_messages(task)
    second = generation_messages(make_task())
    assert first == second
    assert all(set(m) == {"role", "content"} for m in first)
    assert first[-1]["role"] == "user"


def test_prompt_includes_focal_source_and_language_rules():
    java = text_of(generation_messages(make_task("java")))
    assert "public static boolean isBlank(CharSequence cs)" in java
    assert "package org.generated;" in java
    assert "StringUtils_isBlank_Test" in java
    assert "JUnit 5" in java

    py_task = make_task("python", focal_source="def is_blank(s): ...", test_name="test_is_blank.py")
    py = text_of(generation_messages(py_task))
    assert "def is_blank(s): ..." in py
    assert "pytest" in py
    assert "from targets import is_blank" in py

    node_task = make_task(
        "node",
        focal_source="export function isBlank(s) {}",
        import_hint="import { isBlank } from './targets.mjs';",
        test_name="isBlank.test.mjs",
    )
    node = text_of(generation_messages(node_task))
    assert "export function isBlank(s) {}" in node
    assert "node:test" in node
    assert "node:assert/strict" in node
    assert "import { isBlank } from './targets.mjs';" in node


def test_prompt_asks_for_json_only():
    text = text_of(generation_messages(make_task()))
    assert "JSON" in text
    assert "Markdown" in text


def test_repair_messages_include_previous_code_and_diagnostic():
    task = make_task()
    msgs = repair_messages(task, "class PreviousTest {}", "cannot find symbol: foo")
    text = text_of(msgs)
    assert "class PreviousTest {}" in text
    assert "cannot find symbol: foo" in text
    assert "public static boolean isBlank(CharSequence cs)" in text


def test_diagnostic_is_truncated_to_4000_chars():
    diagnostic = "A" * 3990 + "B" * 10 + "Z" * 46_000
    assert len(diagnostic) == 50_000
    text = text_of(repair_messages(make_task(), "class T {}", diagnostic))
    assert "A" * 3990 + "B" * 10 in text
    assert "Z" not in text

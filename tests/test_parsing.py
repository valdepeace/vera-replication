import json

import pytest

from vera.parsing import ParseResult, parse_model_output


def test_plain_json():
    res = parse_model_output('{"code":"class A {}","note":"ok"}')
    assert res.code == "class A {}"
    assert res.note == "ok"
    assert res.error is None


def test_reconstructs_string_concatenation():
    res = parse_model_output('{"code": "a\\n" + "b", "note": "x"}')
    assert res.code == "a\nb"
    assert res.error is None


def test_invalid_json():
    assert parse_model_output("esto no es json").error == "invalid_json"


def test_truncated_json():
    assert parse_model_output('{"code": "class A {').error == "invalid_json"


def test_missing_code():
    res = parse_model_output('{"note": "sin codigo"}')
    assert res.error == "missing_code"
    assert res.code is None


@pytest.mark.parametrize("raw", ['""', '"   "', "null"])
def test_empty_code(raw):
    res = parse_model_output('{"code": ' + raw + "}")
    assert res.error == "empty_code"
    assert res.code is None


def test_markdown_fences_are_not_stripped():
    fence = "```java\nclass A {}\n```"
    res = parse_model_output('{"code": "' + fence.replace("\n", "\\n") + '"}')
    assert res.error is None
    assert res.code == fence.replace("\\n", "\n")


def test_result_is_frozen():
    res = parse_model_output('{"code":"x"}')
    assert isinstance(res, ParseResult)
    with pytest.raises(Exception):
        res.code = "y"


SURROGATE = chr(0xD800)
BS = "\\"


def test_lone_surrogate_escape_returns_to_source_text():
    # El modelo escribe la barra sin duplicar: json.loads da un sustituto suelto.
    raw = json.dumps({"code": f"const s = '{SURROGATE}';", "note": SURROGATE})
    res = parse_model_output(raw)
    assert res.error is None
    assert res.code == "const s = '" + BS + "ud800';"
    assert res.note == BS + "ud800"
    res.code.encode("utf-8")


def test_valid_surrogate_pair_is_kept_as_one_character():
    emoji = chr(0x1F600)
    res = parse_model_output(json.dumps({"code": f"x = '{emoji}'"}))
    assert res.code == f"x = '{emoji}'"

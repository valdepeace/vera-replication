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

from targets import chunk_text, normalize_whitespace


def test_fixture_baseline():
    assert normalize_whitespace("  a   b\n") == "a b"
    assert chunk_text("abcd", 2) == ["ab", "cd"]

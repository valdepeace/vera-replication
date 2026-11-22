from wsl_evaluator import to_wsl_path
from wsl_sandbox import truncate


def test_truncate_baseline():
    assert truncate("hello") == "hello"


def test_to_wsl_path_baseline():
    assert to_wsl_path(r"E:\work\file.py") == "/mnt/e/work/file.py"

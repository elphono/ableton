import pytest

from ableton_raw import coerce, windows_python


@pytest.mark.parametrize("text, expected", [
    ("12", 12),
    ("1.5", 1.5),
    ("true", True),
    ("FALSE", False),
    ("null", None),
    ("none", None),
    ("[1, 2]", [1, 2]),
    ('{"a": 1}', {"a": 1}),
    ("tracks[0]", "tracks[0]"),
    (":12", "12"),
    (":true", "true"),
])
def test_coerce_guesses_the_type(text, expected):
    result = coerce(text)
    assert result == expected
    assert type(result) is type(expected)


def test_explicit_python_wins_over_the_checkout(monkeypatch):
    monkeypatch.setenv("ABLETON_MCP_PYTHON", "/x/python.exe")
    monkeypatch.setenv("ABLETON_MCP_DIR", "/repo")
    assert windows_python() == "/x/python.exe"


def test_checkout_venv_is_used_when_no_explicit_python(monkeypatch):
    monkeypatch.delenv("ABLETON_MCP_PYTHON", raising=False)
    monkeypatch.setenv("ABLETON_MCP_DIR", "/repo")
    assert windows_python() == "/repo/.venv/Scripts/python.exe"

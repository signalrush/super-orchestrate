"""Tests for the _parse function — response parsing for all tool types."""
import json
import pytest
from claude_code_orchestrate.client import _parse


# --- Read ---

def test_parse_read_extracts_content():
    raw = json.dumps({"type": "text", "file": {"filePath": "/test.py", "content": "print(hello)"}})
    assert _parse("Read", raw) == "print(hello)"


def test_parse_read_preserves_multiline():
    raw = json.dumps({"type": "text", "file": {"filePath": "/f", "content": "a\nb\nc"}})
    assert _parse("Read", raw) == "a\nb\nc"


def test_parse_read_null_content_returns_raw():
    raw = json.dumps({"type": "text", "file": {"filePath": "/f", "content": None}})
    assert _parse("Read", raw) == raw


def test_parse_read_null_file_returns_raw():
    raw = json.dumps({"type": "text", "file": None})
    assert _parse("Read", raw) == raw


def test_parse_read_file_is_string_returns_raw():
    raw = json.dumps({"file": "not a dict"})
    assert _parse("Read", raw) == raw


def test_parse_read_missing_file_key_returns_raw():
    raw = json.dumps({"type": "text", "other": "stuff"})
    assert _parse("Read", raw) == raw


# --- Write ---

def test_parse_write_extracts_filepath():
    raw = json.dumps({"type": "create", "filePath": "/tmp/out.txt", "content": "hi"})
    assert _parse("Write", raw) == "/tmp/out.txt"


def test_parse_write_null_filepath_returns_raw():
    raw = json.dumps({"type": "create", "filePath": None, "content": "x"})
    assert _parse("Write", raw) == raw


def test_parse_write_missing_filepath_returns_raw():
    raw = json.dumps({"type": "create", "content": "hi"})
    assert _parse("Write", raw) == raw


# --- Edit ---

def test_parse_edit_extracts_diff_lines():
    raw = json.dumps({"structuredPatch": [{"lines": ["-old", "+new"]}]})
    result = _parse("Edit", raw)
    assert "-old" in result and "+new" in result


def test_parse_edit_multiple_patches():
    raw = json.dumps({"structuredPatch": [
        {"lines": ["-a", "+b"]},
        {"lines": ["-c", "+d"]},
    ]})
    result = _parse("Edit", raw)
    assert "-a" in result and "+d" in result


def test_parse_edit_empty_patch_returns_raw():
    raw = json.dumps({"structuredPatch": []})
    assert _parse("Edit", raw) == raw


def test_parse_edit_null_structured_patch_returns_raw():
    raw = json.dumps({"structuredPatch": None})
    assert _parse("Edit", raw) == raw


def test_parse_edit_null_patch_item_returns_raw():
    raw = json.dumps({"structuredPatch": [None]})
    assert _parse("Edit", raw) == raw


def test_parse_edit_null_lines_returns_raw():
    raw = json.dumps({"structuredPatch": [{"lines": None}]})
    assert _parse("Edit", raw) == raw


def test_parse_edit_lines_not_list_returns_raw():
    raw = json.dumps({"structuredPatch": [{"lines": "not a list"}]})
    assert _parse("Edit", raw) == raw


# --- Glob ---

def test_parse_glob_extracts_filenames_list():
    raw = json.dumps({"filenames": ["/a.py", "/b.py"], "numFiles": 2})
    assert _parse("Glob", raw) == ["/a.py", "/b.py"]


def test_parse_glob_empty_filenames():
    raw = json.dumps({"filenames": [], "numFiles": 0})
    assert _parse("Glob", raw) == []


def test_parse_glob_null_filenames_returns_raw():
    raw = json.dumps({"filenames": None, "numFiles": 0})
    assert _parse("Glob", raw) == raw


# --- Grep ---

def test_parse_grep_files_with_matches():
    raw = json.dumps({"mode": "files_with_matches", "filenames": ["/a.py"], "numFiles": 1})
    assert _parse("Grep", raw) == ["/a.py"]


def test_parse_grep_content_mode():
    raw = json.dumps({"mode": "content", "content": "main.py:10: TODO fix", "numMatches": 1})
    assert _parse("Grep", raw) == "main.py:10: TODO fix"


def test_parse_grep_count_mode():
    raw = json.dumps({"mode": "count", "counts": [{"file": "a.py", "count": 5}], "numMatches": 5})
    assert _parse("Grep", raw) == [{"file": "a.py", "count": 5}]


def test_parse_grep_null_filenames_returns_raw():
    raw = json.dumps({"filenames": None, "numFiles": 0})
    assert _parse("Grep", raw) == raw


def test_parse_grep_all_keys_null_returns_raw():
    raw = json.dumps({"filenames": None, "content": None, "counts": None})
    assert _parse("Grep", raw) == raw


# --- Bash ---

def test_parse_bash_extracts_stdout():
    raw = json.dumps({"stdout": "hello world", "stderr": "", "interrupted": False})
    assert _parse("Bash", raw) == "hello world"


def test_parse_bash_empty_stdout():
    raw = json.dumps({"stdout": "", "stderr": "", "interrupted": False})
    assert _parse("Bash", raw) == ""


def test_parse_bash_null_stdout_returns_raw():
    raw = json.dumps({"stdout": None, "stderr": "err", "interrupted": False})
    assert _parse("Bash", raw) == raw


def test_parse_bash_missing_stdout_returns_raw():
    raw = json.dumps({"stderr": "error only", "interrupted": False})
    assert _parse("Bash", raw) == raw


# --- General ---

def test_parse_unknown_tool_returns_raw():
    raw = json.dumps({"some": "data"})
    assert _parse("UnknownTool", raw) == raw


def test_parse_invalid_json_returns_raw():
    assert _parse("Read", "not json") == "not json"


def test_parse_none_input_returns_none():
    assert _parse("Read", None) is None


# --- Fuzz: no crash on any tool × malformed payload combination ---

_FUZZ_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Unknown"]
_FUZZ_PAYLOADS = [
    "not json", "42", "null", "true", '"s"', "[]", "{}",
    json.dumps({"file": None}), json.dumps({"file": 42}),
    json.dumps({"file": []}), json.dumps({"file": {"content": None}}),
    json.dumps({"filePath": None}), json.dumps({"filePath": []}),
    json.dumps({"structuredPatch": None}), json.dumps({"structuredPatch": "x"}),
    json.dumps({"structuredPatch": [None]}),
    json.dumps({"structuredPatch": [{"lines": None}]}),
    json.dumps({"structuredPatch": [{"lines": "x"}]}),
    json.dumps({"filenames": None}), json.dumps({"filenames": 42}),
    json.dumps({"content": None}), json.dumps({"counts": None}),
    json.dumps({"stdout": None}), json.dumps({"stdout": []}),
    None,
]


@pytest.mark.parametrize("tool", _FUZZ_TOOLS)
@pytest.mark.parametrize("payload", _FUZZ_PAYLOADS)
def test_parse_never_crashes(tool, payload):
    """_parse must never raise — it should return raw on any malformed input."""
    _parse(tool, payload)  # must not raise

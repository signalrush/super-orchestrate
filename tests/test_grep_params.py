"""Tests for Grep hyphenated parameter mapping (-i, -A, -B, -C, -n)."""
from unittest.mock import patch, MagicMock

import claude_code_orchestrate.client as client_mod


def _mock_transport():
    transport = MagicMock()
    transport.call_tool = MagicMock(return_value='{"filenames":["/a.py"],"numFiles":1}')
    return transport


def test_case_insensitive_maps_to_i():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        client_mod.Grep(pattern="TODO", case_insensitive=True)
        args = transport.call_tool.call_args[0][1]
        assert args["-i"] is True


def test_after_context_maps_to_A():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        client_mod.Grep(pattern="TODO", after_context=3)
        args = transport.call_tool.call_args[0][1]
        assert args["-A"] == 3


def test_before_context_maps_to_B():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        client_mod.Grep(pattern="TODO", before_context=2)
        args = transport.call_tool.call_args[0][1]
        assert args["-B"] == 2


def test_context_alias_maps_to_C():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        client_mod.Grep(pattern="TODO", context_alias=5)
        args = transport.call_tool.call_args[0][1]
        assert args["-C"] == 5


def test_line_numbers_maps_to_n():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        client_mod.Grep(pattern="TODO", line_numbers=True)
        args = transport.call_tool.call_args[0][1]
        assert args["-n"] is True


def test_none_params_stripped():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        client_mod.Grep(pattern="TODO", case_insensitive=None, after_context=None)
        args = transport.call_tool.call_args[0][1]
        assert "-i" not in args
        assert "-A" not in args


def test_all_params_combined():
    transport = _mock_transport()
    with patch.object(client_mod, "_transport", transport):
        client_mod.Grep(
            pattern="TODO", path="/src",
            case_insensitive=True, after_context=2, before_context=1,
            output_mode="content",
        )
        args = transport.call_tool.call_args[0][1]
        assert args == {
            "pattern": "TODO", "path": "/src",
            "-i": True, "-A": 2, "-B": 1,
            "output_mode": "content",
        }

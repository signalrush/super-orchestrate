"""Tests for _load_agent_definitions — frontmatter parsing from ~/.claude/agents/*.md."""
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import claude_code_orchestrate.client as client_mod


def _write_agent(agents_dir, filename, content):
    with open(os.path.join(agents_dir, filename), "w") as f:
        f.write(content)


def _write_agent_bytes(agents_dir, filename, content: bytes):
    with open(os.path.join(agents_dir, filename), "wb") as f:
        f.write(content)


def _load(tmpdir):
    client_mod._agent_defs = None
    with patch.object(Path, "home", return_value=Path(tmpdir)):
        return client_mod._load_agent_definitions()


class TestFrontmatterBasics:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.agents_dir = os.path.join(self.tmpdir, ".claude", "agents")
        os.makedirs(self.agents_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir)

    def test_valid_csv_tools(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\ntools: Read, Write, Bash\nmodel: sonnet\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].tools == ["Read", "Write", "Bash"]
        assert defs["a"].model == "sonnet"

    def test_yaml_list_tools(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\ntools:\n  - Read\n  - Write\nmodel: haiku\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].tools == ["Read", "Write"]
        assert defs["a"].model == "haiku"

    def test_yaml_list_tab_indent(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\ntools:\n\t- Read\n\t- Write\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].tools == ["Read", "Write"]

    def test_no_tools(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\ndescription: No tools\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].tools is None

    def test_empty_yaml_list_tools(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\ntools:\nmodel: haiku\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].tools is None
        assert defs["a"].model == "haiku"

    def test_uses_filename_stem_when_no_name(self):
        _write_agent(self.agents_dir, "my-agent.md", "---\ndescription: test\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert "my-agent" in defs

    def test_invalid_model_defaults_to_inherit(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\nmodel: gpt-4\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].model == "inherit"

    def test_no_frontmatter_skipped(self):
        _write_agent(self.agents_dir, "a.md", "Just plain markdown, no frontmatter.")
        defs = _load(self.tmpdir)
        assert "a" not in defs

    def test_incomplete_frontmatter_skipped(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: bad\n")
        defs = _load(self.tmpdir)
        assert "bad" not in defs

    def test_colon_in_value(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\ndescription: See http://example.com:8080/path\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].description == "See http://example.com:8080/path"

    def test_body_with_dashes(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\n---\nText before\n---\nText after\n")
        defs = _load(self.tmpdir)
        assert "---" in defs["a"].prompt
        assert "Text after" in defs["a"].prompt

    def test_empty_body(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\n---\n")
        defs = _load(self.tmpdir)
        assert defs["a"].prompt == ""

    def test_blank_lines_in_frontmatter(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\n\ndescription: test\n\nmodel: sonnet\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].description == "test"
        assert defs["a"].model == "sonnet"

    def test_no_agents_dir(self):
        empty_tmpdir = tempfile.mkdtemp()
        defs = _load(empty_tmpdir)
        assert defs == {}
        shutil.rmtree(empty_tmpdir)

    def test_definitions_cached(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\n---\nBody\n")
        with patch.object(Path, "home", return_value=Path(self.tmpdir)):
            client_mod._agent_defs = None
            d1 = client_mod._get_agent_definitions()
            d2 = client_mod._get_agent_definitions()
            assert d1 is d2


class TestFrontmatterListCoercion:
    """Fields parsed as YAML lists when a scalar is expected."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.agents_dir = os.path.join(self.tmpdir, ".claude", "agents")
        os.makedirs(self.agents_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir)

    def test_name_as_yaml_list_uses_first(self):
        _write_agent(self.agents_dir, "a.md", "---\nname:\n  - agent-a\n  - agent-b\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert "agent-a" in defs

    def test_description_as_yaml_list_joined(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\ndescription:\n  - line one\n  - line two\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].description == "line one line two"

    def test_model_as_yaml_list_uses_first(self):
        _write_agent(self.agents_dir, "a.md", "---\nname: a\nmodel:\n  - sonnet\n  - opus\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert defs["a"].model == "sonnet"


class TestFrontmatterEncoding:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.agents_dir = os.path.join(self.tmpdir, ".claude", "agents")
        os.makedirs(self.agents_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir)

    def test_utf8_bom_handled(self):
        _write_agent_bytes(self.agents_dir, "bom.md",
                           b"\xef\xbb\xbf---\nname: bom-agent\ndescription: BOM\n---\nBody\n")
        defs = _load(self.tmpdir)
        assert "bom-agent" in defs
        assert defs["bom-agent"].description == "BOM"

    def test_crlf_line_endings(self):
        _write_agent_bytes(self.agents_dir, "crlf.md",
                           b"---\r\nname: crlf\r\ntools: Read, Write\r\nmodel: haiku\r\n---\r\nBody\r\n")
        defs = _load(self.tmpdir)
        assert defs["crlf"].tools == ["Read", "Write"]
        assert defs["crlf"].model == "haiku"

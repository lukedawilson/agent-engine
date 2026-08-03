"""load_agent tests — ported from yosk's TestLoadAgent, retargeted at the
library signature which also builds the Agent via the SDK factory. Real
agent files on disk (fail-fast file policy); real LLM/Agent SDK objects
(constructed locally, no network)."""

from pathlib import Path

import pytest
from openhands.sdk import LLM
from openhands.sdk.agent.agent import Agent

from agent_engine.agents import load_agent


@pytest.fixture
def llm():
    return LLM(model="openai/test-model", api_key="sk-test")


@pytest.fixture
def agents_dir(tmp_path):
    d = tmp_path / "agents"
    d.mkdir()
    return d


def make_agent(dir: Path, name: str, frontmatter: str, body: str) -> Path:
    path = dir / f"{name}.agent.md"
    path.write_text(f"---\n{frontmatter}\n---\n{body}")
    return path


class TestLoadAgent:
    """load_agent parses agent files with the SDK's native AgentDefinition
    loader, keeping two pipeline policies on top: the file must exist (fail
    fast — the SDK's dir loader would silently skip it) and its frontmatter
    name must match its filename."""

    def test_builds_agent_from_file(self, agents_dir, llm):
        make_agent(agents_dir, "dev",
                   "name: dev\ntools: [terminal, file_editor]\n",
                   "# System prompt\nDo the work.")

        agent = load_agent(agents_dir, "dev", llm)

        assert isinstance(agent, Agent)

    def test_raises_if_file_missing(self, agents_dir, llm):
        with pytest.raises(FileNotFoundError):
            load_agent(agents_dir, "nonexistent", llm)

    def test_raises_if_no_frontmatter(self, agents_dir, llm):
        (agents_dir / "bad.agent.md").write_text("no frontmatter here\n")
        with pytest.raises(ValueError):
            load_agent(agents_dir, "bad", llm)

    def test_raises_if_missing_name_field(self, agents_dir, llm):
        make_agent(agents_dir, "bad", "tools: []\n", "# Body")
        with pytest.raises(ValueError):
            load_agent(agents_dir, "bad", llm)

    def test_raises_if_name_mismatches_filename(self, agents_dir, llm):
        make_agent(agents_dir, "dev", "name: other\ntools: []\n", "# Body")
        with pytest.raises(ValueError, match="does not match"):
            load_agent(agents_dir, "dev", llm)

    def test_frontmatter_with_extra_fields_ok(self, agents_dir, llm):
        make_agent(agents_dir, "extra",
                   "name: extra\ntools: [terminal]\nextra: ignored\n", "# Body")

        assert isinstance(load_agent(agents_dir, "extra", llm), Agent)

    def test_unknown_tool_name_fails(self, agents_dir, llm):
        """The SDK factory resolves frontmatter tool names against the
        registry — an unknown name fails loudly."""
        make_agent(agents_dir, "bad", "name: bad\ntools: [no_such_tool]\n", "# Body")
        with pytest.raises(ValueError):
            load_agent(agents_dir, "bad", llm)

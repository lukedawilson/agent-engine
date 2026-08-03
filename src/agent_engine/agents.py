"""Agent file loading + SDK factory mechanics.

The SDK's built-in tools are registered at import (its registry is global);
consumer tools are registered by extensions via `Registry.add_tool`."""

from pathlib import Path
from typing import TYPE_CHECKING

from openhands.sdk import LLM
from openhands.tools.file_editor import FileEditorTool  # noqa: F401 — registers "file_editor"
from openhands.tools.task_tracker import TaskTrackerTool  # noqa: F401 — registers "task_tracker"
from openhands.tools.terminal import TerminalTool  # noqa: F401 — registers "terminal"

if TYPE_CHECKING:
    from openhands.sdk.agent.agent import Agent


def load_agent(agents_dir: Path | str, name: str, llm: LLM) -> "Agent":
    """Load `<agents_dir>/<name>.agent.md` and build the Agent via the SDK
    factory (frontmatter tool names resolved against the registry, unknown →
    ValueError; the markdown body is delivered as the system prompt suffix).

    Two pipeline policies on top of the SDK's native AgentDefinition loader:
    the file must exist (fail fast — the SDK's dir loader would silently
    skip it) and its frontmatter name must match its filename. A file with
    no frontmatter or no name gets the SDK's stem fallback ("<name>.agent"),
    which can never match the stem — so both degenerate cases fail the name
    check."""
    from openhands.sdk.subagent.registry import agent_definition_to_factory
    from openhands.sdk.subagent.schema import AgentDefinition

    path = Path(agents_dir) / f"{name}.agent.md"
    if not path.is_file():
        raise FileNotFoundError(f"Agent file not found: {path}")

    agent_def = AgentDefinition.load(path)

    stem = path.name.removesuffix(".agent.md")
    if agent_def.name != stem:
        raise ValueError(
            f"Agent file {path} name {agent_def.name!r} does not match "
            f"filename {stem!r}")
    return agent_definition_to_factory(agent_def)(llm)

"""Supply-chain dependency dial (021): canonical policy injection and
missing-dependency declaration parsing.

The rule text lives HERE, in the engine, not in consumer `dev.agent.md` prose.
The hand-authored rule is exactly the class that deadlocked the NuGet cache
in 018. `deps_policy: locked` (the default) bounds the agent to the
human-owned lockfile and fails a run fast when an agent declares a missing
dependency; `deps_policy: open` injects the bootstrap protocol (the agent may
add exact-pinned manifest entries for the restore step to fetch).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentic_dev_loop.core.config import PipelineConfig

MISSING_DEPS_HEADER = "## Missing dependencies"

_LOCKED_TEMPLATE = (
    "You may only use dependencies already present in {lockfiles}. If the "
    "design requires a dependency that is not present, declare it in your "
    "final response under the fixed header `{header}` (one `name==version` "
    "per line) and finish what you can. Do not add it to the manifest."
)

_OPEN_TEXT = (
    "If the design needs a dependency that is not already present, add the "
    "exact-pinned entry to the dependency manifest directly (do not run a "
    "package-manager `add` command - it may need the network). Your offline "
    "builds may fail until the restore step fetches it - that is expected; "
    "write the code to match and leave the manifest entry in place."
)


def _lockfile_label(cfg: "PipelineConfig") -> str:
    if cfg.lockfiles:
        return ", ".join(f"`{name}`" for name in cfg.lockfiles)
    return "the lockfile"


def policy_injection(cfg: "PipelineConfig") -> str:
    """The canonical dependency-policy paragraph injected into every agent
    step's context, keyed on ``deps_policy`` and the declared lockfiles."""
    if cfg.deps_policy == "open":
        return _OPEN_TEXT
    return _LOCKED_TEMPLATE.format(
        lockfiles=_lockfile_label(cfg), header=MISSING_DEPS_HEADER)


def parse_missing_dependencies(text: str | None) -> list[str]:
    """Parse a final agent response for the fixed ``## Missing dependencies``
    section. Returns the declared pins (one non-empty line each) beneath the
    header, until the next ``## `` section or end of text. An absent header or
    an empty/malformed section yields an empty list - only a non-empty
    declaration triggers the fail-fast."""
    if not text:
        return []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == MISSING_DEPS_HEADER:
            pins: list[str] = []
            for rest in lines[i + 1:]:
                if rest.startswith("## "):
                    break
                stripped = rest.strip()
                if stripped:
                    pins.append(stripped)
            return pins
    return []


def extension_message(cfg: "PipelineConfig", pins: list[str]) -> str:
    """The fail-fast message naming the lockfile(s) and the declared pins."""
    return (f"Extend {_lockfile_label(cfg)} with these pins and re-run:\n\n"
            + "\n".join(pins))

"""Wheel-shipped Claude skill payload (BR-10): SKILL.md + workflow JS
template + version marker, installed idempotently to
`~/.claude/skills/agentic-dev-loop/` by `agentic-dev-loop-workflow
install-skill`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from agentic_dev_loop.core.projection import WORKFLOW_TEMPLATE, core_version

SKILL_NAME = "agentic-dev-loop"
VERSION_FILE = "VERSION"

SKILL_MD = """\
---
name: agentic-dev-loop
description: Export a Claude Dynamic Workflow from the pipeline.yaml you
  already trust — dev/test/review/qa steps, deterministic verdict routing,
  and the live graph visualiser, driven by Claude Code subagents.
---

# agentic-dev-loop

Turn a validated `pipeline.yaml` into a self-contained Claude Dynamic
Workflow. The deterministic loop (steps, verdicts, bounded retries, the
single gated commit) is baked into the generated JS at build time; runtime
never parses the YAML.

## Build (workflow creation — once)

1. Project the pipeline (validates the YAML and every agent step's prompt):
   `python -m agentic_dev_loop.core.project <pipeline.yaml>`
   — writes `.agentic-dev-loop/workflow.js` next to the pipeline.
2. Create a Claude Code workflow from that generated JS file.

## Run (workflow execution)

- The first step captures clean-at-start (empty `git status --porcelain`)
  so the commit shim can gate the single commit point.
- A viz step launches `python -m agentic_dev_loop.viz --pipeline
  <pipeline.yaml>` — the server issues an ingest token and serves the
  live graph on localhost; step subagents POST stage events to `/ingest`
  with that token.
- Agent steps re-read their `.agent.md` from the workspace at spawn (prompt
  reference, never embedded — earlier steps' prompt edits take effect).
- Command steps run in Claude Code's environment; exit code is the verdict.
- Verdict agents write `VERDICT: PASS/FAIL`; the JS routes `on_pass` /
  `on_fail` / `goto` with a bounded attempt counter; the failing subagent's
  final output becomes the retry note.
- The commit step invokes the docker-free shim, which refuses loudly unless
  the worktree was clean at run start.

## Engine-only fields

`isolation:`, per-step `network:`, and `setup:` are ignored in workflow mode
with no effect on the build or run — workflow steps run in Claude Code's own
environment (no Docker sandbox). The trust model is Claude Code's permission
model, not the engine's kernel isolation.
"""


def skill_dir() -> Path:
    """The installed skill directory (`~/.claude/skills/agentic-dev-loop/`)."""
    return Path("~/.claude/skills").expanduser() / SKILL_NAME


def install_skill(target: str | Path | None = None) -> Path:
    """Copy SKILL.md + the workflow template + a VERSION marker into the
    skill directory idempotently (overwrite). Skill files are never
    user-edited. Fails loudly when the target is missing or unwritable."""
    target = Path(target) if target is not None else skill_dir()
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    (target / "workflow.js.template").write_text(
        WORKFLOW_TEMPLATE, encoding="utf-8")
    (target / VERSION_FILE).write_text(core_version(), encoding="utf-8")
    return target

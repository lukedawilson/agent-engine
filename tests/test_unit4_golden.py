"""Unit-4 golden-render tests (TS-6): the deterministic loop — projection →
generated workflow JS — is the product, so its rendering is pinned
byte-for-byte against a committed golden file, and its router constructs are
asserted directly so a template regression can never slip through a stale
regeneration."""

from __future__ import annotations

from pathlib import Path

from agentic_dev_loop.core import (WORKFLOW_TEMPLATE, load_config,
                                   project_workflow, render_workflow_js)

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN = REPO_ROOT / "tests" / "golden" / "workflow.js.golden"
SHIPPED_PIPELINE = REPO_ROOT / "agentic-dev-loop" / "pipeline.yaml"
# Relative to the repo root so the baked prompt references are workspace-
# relative and the golden file stays machine-independent.
SHIPPED_AGENTS = Path("agentic-dev-loop") / "sdk_agents"

# Fixed stamps so the golden file pins rendering independent of the installed
# distribution version (which varies by environment).
VERSION = "GOLDEN"
HASH = "golden123"


def _render(monkeypatch) -> str:
    monkeypatch.chdir(REPO_ROOT)
    cfg = load_config(SHIPPED_PIPELINE)
    projection = project_workflow(cfg, SHIPPED_AGENTS, HASH)
    return render_workflow_js(WORKFLOW_TEMPLATE, projection, VERSION, HASH)


def test_rendered_js_matches_golden_byte_for_byte(monkeypatch):
    js = _render(monkeypatch)
    assert js == GOLDEN.read_text(encoding="utf-8")


def test_golden_embeds_the_deterministic_loop(monkeypatch):
    js = _render(monkeypatch)
    # Header stamp.
    assert js.startswith("// agentic-dev-loop workflow — core GOLDEN "
                         "— pipeline golden123\n")
    # Clean-at-start first step (BR-8).
    assert "git status --porcelain" in js
    assert "commitAllowed" in js
    # Viz launch step (FD-4).
    assert "python -m agentic_dev_loop.viz" in js
    assert "ingestToken" in js
    # Routing + attempt counter + retry-note injection (BR-7).
    assert "on_pass" in js and "on_fail" in js
    assert "state.attempt += 1" in js
    assert "max_attempts exceeded" in js
    assert "retryNote" in js
    # Verdict contract (BR-6).
    assert "VERDICT" in js and "parseVerdict" in js
    # Gated commit step (BR-8 / FR-4.6).
    assert "agentic-dev-loop-commit" in js
    # Prompt reference, not embed (BR-5).
    assert "dev.agent.md" in js

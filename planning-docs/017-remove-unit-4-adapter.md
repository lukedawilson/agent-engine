# 016 - Remove the unit-4 Claude-adapter surface (wontship)

Status: COMPLETED (2026-10-23) - removal shipped in release 1.0.0a7 (aidlc-state.md confirms). This document is the removal record.

## Decision record

User (verbatim, 2026-10-22): "In fact, forget it. Let's rip it out and mark unit 4 as wontship/wontdo. Is the refactoring into separate modules still beneficial, or should we just revert the whole release?"

Resolved: **keep the core/engine/viz module split; rip out only the Claude-adapter surface.** The split earned independent value (guard-tested dependency contracts, viz stdlib-only, core pydantic+PyYAML-only, cleaner test partitioning, 644 tests green). The adapter surface (projection, workflow runner, skill, commit shim, ingest) exists only to serve the Claude Workflow tool, which is now out of scope.

## Rip out (adapter surface - verified no in-repo consumers outside itself)

| Path | Notes |
| --- | --- |
| `src/agentic_dev_loop/core/projection.py`, `core/project.py` | Pipeline→workflow-JS projection. `core/__init__.py` re-exports them (trim those exports; keep config/results/verdict) |
| `src/agentic_dev_loop/workflow/` (whole package) | workflow.cli runner + `install_skill` (SKILL.md writer) + workflow.js.template |
| `src/agentic_dev_loop/engine/commit_shim.py` | Docker-free commit CLI - built for workflow mode; zero external consumers (grep-verified) |
| `src/agentic_dev_loop/viz/ingest.py` + `/ingest` route + token plumbing in `viz/server.py` | Only external workflow-mode posters used it; engine mode uses in-process VizBus. Remove route (server.py:377-381 region), `issue_ingest_token`, `ingest_token` params |
| `tests/test_unit4_workflow.py`, `tests/test_unit4_pbt.py`, `tests/golden/` | Unit-4 test suites + golden workflow.js |
| pyproject: `agentic-dev-loop-workflow` + `agentic-dev-loop-commit` scripts | Lines 47-48 |
| pyproject: `workflow` extra (empty `[]`) | Remove |
| `~/.claude/skills/agentic-dev-loop/` (host-side) | Remove the installed skill |
| README workflow-mode sections + `[engine]` install pin | See packaging below |
| COMPAT-SHIMS.md - any unit-4 shim entries | Audit and remove (pre-unit-4 entries stay) |

## Keep

- Module split: `core/{config,results,verdict}.py`, `engine/*` (minus commit_shim), `viz/{__init__,__main__,server}.py`
- Engine-mode live graph viz (predates unit-4)
- `agentic-dev-loop = agentic_dev_loop.engine.cli:main`
- All unit-4 historical docs (requirements FR-4.x, construction artifacts, intent doc) - left as history per ID-8 precedent; state file marks wontship

## Packaging (resolved 2026-10-22)

Restore the pre-unit-4 shape (user agreed): **openhands-sdk, openhands-tools, agent-client-protocol<1.0.0, langgraph, langgraph-checkpoint-sqlite move back into base `[project.dependencies]`** - base install = engine mode; extras reduced to `dev` only (`engine` and `workflow` extras removed); README pins become plain `agentic-dev-loop==1.0.0a7`; `agentic-dev-loop-workflow` and `agentic-dev-loop-commit` scripts removed.

## Verification (on removal)

1. `grep -rn "workflow\|projection\|commit_shim\|install_skill\|ingest" src/` - zero hits outside remaining files
2. Guard tests still pass (core import graph, viz fresh-import)
3. Full `pytest -m "not docker"` + docker-marked integration on host daemon
4. `uv pip install -e ".[dev]"` clean; `.venv/bin/agentic-dev-loop --version` works
5. Windows CI green (the UTF-8 pinning work must survive untouched)

## Bookkeeping (done in this pass)

- `aidlc-state.md`: unit-4 → WONTSHIP/WONTDO (2026-10-22), stale duplicate checkboxes removed
- `requirements.md`: Stage 4 heading annotated WONTSHIP
- `audit.md`: decision + raw quotes appended

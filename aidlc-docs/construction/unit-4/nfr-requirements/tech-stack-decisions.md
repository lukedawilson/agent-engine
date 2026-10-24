# Unit 4 Tech Stack Decisions - Claude Dynamic Workflows driver

| ID | Decision | Detail |
| --- | --- | --- |
| TS-1 | **Extras split** | `agentic-dev-loop[workflow]` = `core` + `viz` (no openhands-sdk/docker); full install unchanged. Workflow-mode devs install minimal; engine mode unchanged. (NFR-4.1) |
| TS-2 | **Hard module break** | No shims; `agentic_dev_loop.core` / `.engine` / `.viz` with clean boundaries + guard test; full old→new import migration list in release notes, incl. `agentic_dev_loop.extensions.aidlc` pipeline.yaml strings. (NFR-4.2) |
| TS-3 | **Projection in `core`** | pydantic + PyYAML only; `project_workflow` / `validate_prompt_refs` / `render_workflow_js` pure and dependency-light. |
| TS-4 | **Viz stdlib-only** | `http.server` + SSE event stream + token-authenticated POST ingest; no new deps; `issue_ingest_token` per launch. |
| TS-5 | **Wheel-shipped skill** | SKILL.md + workflow JS template + docs in the PyPI wheel; `agentic-dev-loop install-skill` → `~/.claude/skills/agentic-dev-loop/`; generated JS header records core version + pipeline hash. |
| TS-6 | **Golden template tests** | Deterministic rendering (projection → generated JS) pinned by golden files in CI - guards the deterministic loop, the product's core. (NFR-4.7) |
| TS-7 | **No journal, no MCP** | Workflow state lives in Claude Code; CC transcripts are the audit trail; subagents reach `core`/`viz` via shell/python. |
| TS-8 | **Existing CI, no new jobs** | `core`/`viz` unit+PBT+golden tests run in the existing ubuntu/windows matrix under `-m "not docker"`; docker-marked engine tests unchanged. Real CC workflow E2E = manual smoke. |

## Deferred

- Workflow-mode resume (journal-ready design; would bring `.agentic-dev-loop/workflow-state.json` with it)
- Interactive metering (intent pillar 1)
- Verification of Claude Code's native workflow resume semantics (needed before any future resume work)

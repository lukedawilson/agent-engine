# Unit 4 Functional Design Plan — Claude Dynamic Workflows driver

Status: in progress. Next stage after FD = NFR Requirements.

## Unit context (post-Requirements-Analysis, amended)

Unit-4 = the two parts of agentic-dev-loop drivable from Claude Dynamic Workflows: (1) parsing pipeline.yaml and creating the workflow steps from it (**build-time** parse — steps baked into a generated workflow JS at creation time), (2) the visualiser. NO Docker sandboxing from Claude Code. Deliverables: module split `core`/`engine`/`viz` (FR-4.1, guard-tested deps contract), skill `/agentic-dev-loop` with bundled workflow JS **template** (FR-4.3), command steps → subagent steps (FR-4.4), same VERDICT contract routed by the JS (FR-4.5), docker-free commit shim (FR-4.6), subagent-launched viz + HTTP ingest (FR-4.7), no MCP (FR-4.8), shared pipeline.yaml, engine-only fields ignored in workflow mode (FR-4.9).

## Domain exposition (DDD probes)

| Dimension | Finding |
| --- | --- |
| Concepts named | `core` module (PipelineConfig + parse + workflow projection), `engine` (unchanged runtime), `viz` module + HTTP ingest endpoint, Claude skill `/agentic-dev-loop`, workflow JS template + generated concrete JS, build step (Claude-with-tools), subagent steps (agent/command), commit shim, VizBus/event stream. NO new sandboxing concepts — explicitly excluded. |
| State ownership | Generated workflow JS owns step data + attempt counters + retry note (workflow state); `core` owns pipeline definition + projection; `viz` owns event stream/SSE; Claude Code owns subagent sessions; engine owns run state (engine mode unchanged). |
| Runtime contexts | Build time (workflow creation): Claude imports `.core`, parses, generates JS. Workflow run time: JS executes steps, spawns subagents, routes verdicts — no parsing, no imports. Load time (`core` in engine mode): same validate-fail-fast as today. |
| Change-togetherness | Projection lives in `core` (changes with config schema); ingest endpoint + server live in `viz`; commit shim is docker-free but reuses engine commit policy (real code, shared); skill = packaging (template JS + docs + build instructions). |
| Invariants | Same verdict contract both modes; one pipeline.yaml both modes; `core` never imports `engine`/`viz`/heavy deps (guard test); engine-only fields never crash workflow mode; no Docker anywhere on the workflow-mode path; generated JS self-contained at runtime. |
| Actors | Pipeline author (trusted, one YAML); build step Claude (trusted, has tools); subagents (untrusted-ish work horses under Claude Code's permission model); workflow JS (deterministic router); viz server (passive observer); human (reads viz, owns repo). |

## Open questions

### FD-1 — Projection shape: embed vs reference

[Answer]: B — embed step data, reference prompts. Generated JS carries each step's data (type, command, verdicts, on_pass/on_fail, max_attempts) plus a path to the agent's `.agent.md`; subagent steps re-read the prompt file from the workspace at spawn time. PLUS new requirement: the build step (core projection) MUST verify each agent prompt file exists and fail loudly if not — prompt-existence check at build time, mirroring engine-mode fail-fast. (Raw: "B / Should check the agent prompts exist and fail if they don't")

### FD-2 — Retry loop in generated JS

[Answer]: A — explicit retry note (engine-faithful). JS keeps an attempt counter in workflow state; on failure the failing subagent's final output becomes the retry note, injected into the next dev attempt's prompt (mirrors engine's notes channel). (Raw: "A")

### FD-3 — Commit shim clean-at-start in workflow mode

[Answer]: A — capture at workflow start. Generated JS's first step records `git status --porcelain` emptiness → `commit_allowed` flag in workflow state, before any subagent work; commit step's shim gates on that flag. Exact engine semantics (clean at START). (Raw: "A")

### FD-4 — Viz ingest endpoint + URL flow

[Answer]: A — token-authenticated ingest. Viz server generates a token at launch, written into workflow state; step subagents send it as a header on POSTs; browser's read-only SSE view needs no token; localhost-bound. (Raw: "A")

### FD-5 — Skill packaging + build trigger

[Answer]: A — wheel-shipped: SKILL.md + workflow JS template + docs ship in the PyPI wheel; `agentic-dev-loop install-skill` copies them into `~/.claude/skills/agentic-dev-loop/`. Invoking `/agentic-dev-loop` → Claude follows SKILL.md → runs the projection via the installed package (`python -m agentic_dev_loop.core.project`) → writes the generated workflow JS → creates the Claude Code workflow. Generated JS header records core version + pipeline hash. (Raw: "A ")

## Steps

- [x] Unit context analysis (requirements + intent doc + code facts)
- [x] Domain exposition (DDD probes)
- [x] Resolve open questions (FD-1..FD-5, inline one at a time)
- [x] Generate artifacts: business-logic-model.md, business-rules.md, domain-entities.md under aidlc-docs/construction/unit-4/functional-design/
- [x] DDD descent audit
- [x] Security-baseline compliance check (scoped)
- [x] PBT property identification
- [ ] Completion message + approval

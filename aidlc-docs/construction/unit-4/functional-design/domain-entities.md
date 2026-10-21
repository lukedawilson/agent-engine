# Unit 4 Functional Design — Domain Entities

## Trace List

| Entity | Source |
| --- | --- |
| `WorkflowProjection` (NEW, `core`) | FR-4.3 build-time parse + FD-1 |
| Generated workflow JS (NEW, skill artifact) | FR-4.3 + FD-5 |
| `ClaudeSkill` `/agentic-dev-loop` (NEW, wheel-shipped) | FR-4.3 + FD-5 |
| Viz ingest endpoint + token (NEW, `viz`) | FR-4.7 + FD-4 |
| Commit shim (NEW, engine-adjacent, docker-free) | FR-4.6 + Q4 |
| `PipelineConfig` + parse/validate (moved to `core`) | FR-4.1 |
| Engine graph/stages/sandbox (moved to `engine`, unchanged) | FR-4.1 |
| VizBus + viz server (moved to `viz`, unchanged) | FR-4.1 |
| Subagent steps (agent/command) | FR-4.4 + Q1 |
| Docker sandboxing | Explicitly NOT in unit-4 (FR-4.2) |

## New entities

### `WorkflowProjection` — frozen dataclass in `core`

Produced by `project_workflow(cfg, agents_dir, pipeline_hash)`. Fields: `pipeline_name`, `pipeline_hash`, `core_version`, `steps: list[ProjectedStep]`. `ProjectedStep`: `id`, `kind` (`agent` | `command` | `action`), `command` (command steps), `prompt_path` (agent steps — reference, BR-5), `verdicts`, `on_pass`, `on_fail`, `max_attempts`, `timeout`. Construction validates: steps well-formed, verdict routing targets exist, prompt refs exist (BR-4). Constructor validation = invariant behaviour, not anaemic.

### Generated workflow JS — skill artifact

`render_workflow_js(template, projection, core_version, pipeline_hash)` fills the wheel-shipped template: baked step data, routing (`on_pass`/`on_fail`/`goto`), attempt counter, clean-at-start first step, viz launch step, commit step. Header records core version + pipeline hash. Self-contained at runtime (no parsing, no imports).

### `IngestToken` + endpoint — `viz` module

Server issues a random token at launch (PBT: unique per launch); POST endpoint accepts stage events with the token header; SSE read-only stream tokenless; localhost-bound.

### Commit shim — docker-free, reuses engine commit policy

Same clean-at-start gate + trusted hooksPath + templated message as the engine's commit action, exposed as a subprocess-invocable helper without needing docker/openhands. Refuses loudly when `commit_allowed` is false.

## Pure functions (step-0, PBT targets)

| Function | Module |
| --- | --- |
| `project_workflow` / `validate_prompt_refs` / `render_workflow_js` | `core` |
| `parse_verdict` (existing, shared unchanged) | `core` |
| `clean_at_start_flag` | `core` |
| `make_ingest_event` / `issue_ingest_token` | `viz` |

## Modified entities

- **`PipelineConfig`** — moves to `core`; gains the projection entry point; engine-only fields (`isolation:`, `network:`, `setup:`) validated as today in engine mode, ignored-with-documented-semantics in workflow mode (BR-11).
- **Engine modules** (`graph`, `stages`, `isolation`, CLI) — re-homed under `engine` package; behaviour unchanged (guard-tested).
- **Viz** — re-homed under `viz`; gains the HTTP ingest endpoint; in-process VizBus unchanged.

## Descent Audit (DDD step descent)

| Behaviour | Placement | Verdict |
| --- | --- | --- |
| Parse + validate pipeline.yaml | `core` (projection entry) | Correct |
| Project steps for workflow | `core` (pure) | Correct |
| Render generated JS | `core` (pure) | Correct |
| Prompt existence check | `core` at build time | Correct (fail fast) |
| Route verdicts / attempts | Generated JS (workflow state) | Correct (deterministic router owns routing) |
| Execute command steps | Subagent (CC env) | Correct (executor outside domain model) |
| Capture clean-at-start | Generated JS step 1 → state; shim gates | Correct |
| Commit | Shim (engine policy, docker-free) | Correct |
| Stage events | Subagent → viz ingest (token) | Correct |
| SSE stream | `viz` server | Correct |
| Sandboxing | `engine` only — never on workflow path | Correct (excluded scope) |

## Requirements Traceability

| Requirement | Coverage |
| --- | --- |
| FR-4.1 module split | `core`/`engine`/`viz` + guard test (BR-2) |
| FR-4.2 scope (parse+viz, no Docker) | BR-3, KD-2 |
| FR-4.3 build-time parse + skill + template | BR-1, `WorkflowProjection`, generated JS |
| FR-4.4 command steps → subagents | ProjectedStep.kind, Q1 |
| FR-4.5 verdict contract | BR-6, shared `parse_verdict` |
| FR-4.6 commit shim | BR-8, Commit shim entity |
| FR-4.7 viz + ingest | BR-9, IngestToken |
| FR-4.8 no MCP | BR-13 |
| FR-4.9 shared pipeline.yaml | BR-11, BR-12 |

## Deferred / recorded amendments

- Interactive metering (intent pillar 1): out of unit-4 scope (FR-4.2) — recorded, not designed.
- Intent doc's MCP-tools architecture: superseded by skill + JS (FR-4.8) — amendment already applied to intent doc.

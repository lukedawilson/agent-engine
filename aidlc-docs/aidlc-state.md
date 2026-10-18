# AI-DLC State Tracking

## Project Information
- **Project Type**: Brownfield
- **Start Date**: 2026-10-17T10:58:41Z
- **Current Stage**: CONSTRUCTION - Unit 2 Infrastructure Design approved (2026-10-18); next = Unit 2 Code Generation

## Workspace State
- **Existing Code**: Yes
- **Reverse Engineering Needed**: Yes
- **Workspace Root**: /Users/luke/dev/work/agent-engine

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Intent
- **Primary Intent**: Guardrails and sandboxing for the agent-engine pipeline library, in two stages:
  1. SDK-level hardening — harden the existing tooling injection via what the OpenHands SDK provides
  2. Kernel-level isolation — proper kernel-level isolation for guardrails and sandboxing

## Execution Plan Summary
- **Total Stages**: 12 planned
- **Stages to Execute**: Application Design, Units Generation, Functional Design, NFR Requirements, Infrastructure Design, Code Generation, Build and Test
- **Stages to Skip**: User Stories (user confirmed), NFR Design (no perf/HA work; container infra covered by Infrastructure Design)
- **Unit Order**: Unit 1 output-passing fix + file-tool removal → Unit 2 SDK hardening → Unit 3 kernel isolation (vertical slices)

## Extension Configuration
- **Domain Standards**: Yes — enabled (Requirements Analysis, 2026-10-17)
- **Resiliency Baseline**: Yes (scoped) — enabled as directional guidance, desktop-tool scope (retries/recovery in; server load/HA/DR out) (Requirements Analysis, 2026-10-17)
- **Security Baseline**: Yes — enabled (Requirements Analysis, 2026-10-17)
- **Property-Based Testing**: Yes (Partial) — pure functions + serialization round-trips only (Requirements Analysis, 2026-10-17)

## Stage Progress
- [x] Workspace Detection — 2026-10-17T10:58:41Z
- [x] Reverse Engineering — completed 2026-10-17T10:58:41Z; artifacts at aidlc-docs/inception/reverse-engineering/
- [x] Requirements Analysis — approved by user 2026-10-17T12:15:00Z (directives: Unit 1 = findings/verdict-passing mechanism first; skip User Stories; units = vertical slices)
- [ ] User Stories — SKIPPED (user confirmed; internal tooling)
- [x] Workflow Planning — approved 2026-10-17T12:25:00Z (user restated 3 units: output-passing fix + file-tool removal, SDK hardening, kernel isolation)
- [x] Application Design — approved 2026-10-17T13:20:00Z (DDD amendments applied; domain diagrams approved)
- [x] Units Generation — approved 2026-10-17 (numeric unit names unit-1/2/3; story-map maps FR/NFR IDs; artifacts in aidlc-docs/inception/application-design/)
- [ ] NFR Design — SKIP (no perf/HA; infra in Infrastructure Design)

## Unit Progress

### unit-1 (output-passing fix + file-tool removal) — COMPLETE
- [x] Functional Design — approved 2026-10-17T14:35:00Z
- [x] NFR Requirements — approved 2026-10-17T15:00:00Z
- [x] Infrastructure Design — approved 2026-10-17 (all categories N/A)
- [x] Code Generation — approved 2026-10-18 (user: "Seems to work. Commit and push, mark unit complete")
- [x] Build and Test — full suite green: 373 passed (mechanical `test` command substance)

### unit-2 (SDK hardening) — IN PROGRESS
Scope FR-1.1 (tool-surface semantics — `tools:` as sole capability allowlist; no `filter_tools_regex`), FR-1.4 (task_tracker instruction removed), FR-1.5 (command-step shell hardening), FR-1.6 (action-step subprocess hardening), FR-1.7 (extension tool-registration validation)
- [x] Functional Design — approved 2026-10-18 (FD-1 drop task_tracker instruction; FD-2 capabilities + FinishTool + ThinkTool; FD-2b drop regex; FD-3 hybrid shell; FD-4 any-registered-name collision; FD-5 deeper subprocess hardening)
- [x] NFR Requirements — approved 2026-10-18 (NFR-1=C hybrid env; refined: LLM key included by default; `env_allowlist` optional key)
- [x] Infrastructure Design — approved 2026-10-18 (all 7 categories N/A; container infra deferred to unit-3)
- [ ] Code Generation — plan approved 2026-10-18; generation delegated to user's dev loop (self-hosting via `./trigger-agent-engine.sh --ai-dlc-unit U2`)
- [ ] Build and Test

### unit-3 (kernel isolation, opt-in) — NOT STARTED
Scope FR-2.1–FR-2.6 (container sandboxing via Docker Engine API; fail-fast when unavailable; macOS/Linux/Windows; profile defaults at FD; host-side commit)

- [ ] Operations (placeholder)

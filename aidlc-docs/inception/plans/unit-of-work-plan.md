# Unit of Work Plan - Guardrails & Sandboxing

## Decomposition Approach

Three units, already user-specified as vertical slices, executed in strict order. Each unit = its own Functional Design → Code Generation → Build and Test pass.

| Unit | Intent (user's words) | Scope mapping from requirements.md |
| --- | --- | --- |
| **Unit 1** - Output-passing fix | "Fix the way output is passed between stages (and then remove file writing tools from agents that no longer need them)" - "genuine bug-in-waiting", goes FIRST | FR-1.2 (pipeline captures final SDK response), FR-1.3 (drop file_editor) |
| **Unit 2** - SDK hardening | "SDK-level hardening" | FR-1.1 (expose `filter_tools_regex`/`include_default_tools`), FR-1.4 (task_tracker fix), FR-1.5 (command-step shell hardening), FR-1.6 (action-step subprocess hardening), FR-1.7 (extension tool registration validation) |
| **Unit 3** - Kernel isolation | "Kernel-level isolation" (opt-in) | FR-2.1–FR-2.6 (container sandboxing of terminal tool + command steps via Docker Engine API; fail-fast when unavailable; macOS/Linux/Windows; profile defaults at FD; host-side commit) |

## Question-category evaluation

| Category | Status | Justification |
| --- | --- | --- |
| Story grouping | ✅ Answered | User specified the three units and their order explicitly |
| Dependencies | ✅ Answered | Strict sequence 1→2→3, same package; U3 builds on U1/U2 shapes (Sandbox into `run_command`, capture path into `run_agent`) |
| Team alignment | ⏭ Skipped | Single developer + agent; no ownership boundaries |
| Technical considerations | ⏭ Skipped | One package, desktop tool; no per-unit deploy/scale differences |
| Business domain | ⏭ Skipped | Single bounded context (pipeline guardrails) - already modeled in Application Design |
| Code organization | ⏭ Skipped | Brownfield; existing `src/agent_engine/` structure retained |

## Open questions

### Question U-1: Unit naming / numbering

Unit numbers matter mechanically: the `ai-dlc` document loader resolves docs from `aidlc-docs/construction/unit-<N>/` and plans from `construction/plans/unit-<N>-*-code-generation-plan.md`. (Known integration gap - the ported commands reference `aidlc-docs/unit-{N}/`; reconcile here.)

A) Numeric: `unit-1` / `unit-2` / `unit-3` - matches the loader's expectation, keeps `--ai-dlc-unit 2` working (recommended)

B) Descriptive slugs: `unit-output-passing` / `unit-sdk-hardening` / `unit-kernel-isolation` - more readable, but the loader needs adjusting to accept them

X) Other

[Answer]: A - numeric: `unit-1` / `unit-2` / `unit-3`, matching the ai-dlc loader's `construction/unit-<N>/` expectation; keeps `--ai-dlc-unit` working

---

### Question U-2: Story-map source

`unit-of-work-story-map.md` is a mandatory artifact mapping **stories** to units - but User Stories was skipped (internal tooling). Map **requirements** (FR/NFR IDs) to units in the same artifact instead?

A) Yes - story-map maps FR/NFR IDs to units (recommended; requirements already carry stable IDs)

B) No - generate a minimal set of stories first, then map those

X) Other

[Answer]: A - story-map maps FR/NFR IDs to units; no stories generated

---

### Question U-3: Unit 2 scope confirmation

Confirm the Unit 2 mapping above: "SDK-level hardening" = the full Q1-answer-C surface **minus** output-passing - i.e. SDK tool-restriction knobs, `task_tracker` fix, command-step shell hardening (`shell=True` → argv), action-step subprocess review, extension tool-registration validation. Anything excluded (e.g. defer command-step hardening to Unit 3 since it overlaps the sandbox surface)?

A) Confirm mapping as written (recommended - Unit 2 hardens the host-side surfaces; Unit 3 replaces execution location)

B) Defer command-step shell hardening (FR-1.5) to Unit 3 - avoid touching `run_command` twice

X) Other

[Answer]: A - confirm mapping as written

---

## Generation steps (Part 2)

- [x] Generate `aidlc-docs/inception/application-design/unit-of-work.md` with unit definitions and responsibilities
- [x] Generate `aidlc-docs/inception/application-design/unit-of-work-dependency.md` with dependency matrix
- [x] Generate `aidlc-docs/inception/application-design/unit-of-work-story-map.md` mapping requirements (per U-2 answer) to units
- [x] Validate unit boundaries and dependencies
- [x] Ensure all requirements (FR/NFR) are assigned to units

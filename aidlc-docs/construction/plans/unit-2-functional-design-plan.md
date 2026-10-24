# Functional Design Plan - unit-2 (SDK-level hardening)

## Unit Context (from unit-of-work.md)

Always-on host-side hardening. Scope: FR-1.1 (tool-surface semantics), FR-1.4 (fix `task_tracker` no-op), FR-1.5 (harden command-step shell invocation), FR-1.6 (harden action-step subprocess calls), FR-1.7 (validate extension tool registration). Fixed policies preserved (FR-1.8, NFR-1 backward compat, NFR-2 fail-fast).

## FD Steps

- [x] Analyze unit-2 context and story-map assignments (FR-1.1, FR-1.4, FR-1.5, FR-1.6, FR-1.7)
- [x] Domain exposition (DOMAIN-01 - six probe dimensions, answered)
- [x] Resolve FD open questions (below)
- [x] Generate `aidlc-docs/construction/unit-2/functional-design/business-logic-model.md`
- [x] Generate `aidlc-docs/construction/unit-2/functional-design/business-rules.md`
- [x] Generate `aidlc-docs/construction/unit-2/functional-design/domain-entities.md`
- [x] Validate against DDD rules (descent audit; no new services; no single-impl interfaces)
- [x] Security-baseline compliance check (least privilege, input validation, credential hygiene on host surfaces)
- [x] Identify PBT properties (PBT-02) for the new pure functions (name validation, shell classification, pid validation)

## Domain Exposition (DOMAIN-01)

### Dimension 1 - Concepts named

- **Source**: FR-1.1 "tool-restriction knobs" wired "through the agent factory from `.agent.md` frontmatter"; FR-1.7 "tool registration", "collision", "reserved-name".
- **Proposed**: an agent's **tool surface** (capability allowlist `tools` + fixed infra tools FinishTool/ThinkTool) and the **tool-name registry** (the SDK's global name→resolver map). Command strings and subprocess calls are an *execution surface*, not domain objects.

### Dimension 2 - State ownership

- **Source**: FR-1.7 "extensions register tools into the SDK **global** registry"; FR-1.1 "`.agent.md` frontmatter".
- **Proposed**: the agent definition owns the *tool surface* (declarative); the SDK owns the *global registry* (authoritative, currently silently overwrites on duplicate - the FR-1.7 bug); agent-engine validates against the SDK registry at the boundary.

### Dimension 3 - Runtime contexts

- **Source**: FR-1.7 "fail fast at load"; FR-1.5/1.6 command/action execution.
- **Proposed**: tool registration + frontmatter parsing + name validation at **load** (graph build, once); command/action subprocess invocation at **run** (per step).

### Dimension 4 - Change-togetherness

- **Source**: FR-1.1 tool-restriction surface; `tools` allowlist already exists.
- **Proposed**: the tool surface (capabilities + infra) is one cohesive concept on the agent definition. Registration validation (FR-1.7) changes independently.

### Dimension 5 - Invariants & failure modes

- **Source**: NFR-2 fail-fast; FR-1.7 "collision detection… reserved-name rejection"; FR-1.1 "fail fast on unknown tool names".
- **Proposed** invariants: a registered tool name is unique process-wide; every frontmatter tool name resolves; subprocess inputs (pid tokens) are validated. Failure modes today: duplicate registration **silently overwrites** (SDK `register_tool` warns + clobbers). Both become load-time/run-time errors.

### Dimension 6 - Actors

- **Source**: FR-1.5/1.6/1.7 - surfaces authored by pipeline/extension authors, executed by (untrusted) agents.
- **Proposed**: pipeline author (YAML `command:`) and extension author (`add_tool`) are trusted authors validated at load; the **agent** is the untrusted runtime actor; the SDK global registry is shared mutable state that must be validated, never silently overwritten.

## Open Functional Questions

### Question FD-1 (FR-1.4): `task_tracker` no-op in `dev.agent.md`

`dev.agent.md` has `tools: [terminal]` but WORKFLOW step 3 says "create task tracker entries for each task". `task_tracker` is registered but not in dev's allowlist, so the instruction is a no-op.

A) Add `task_tracker` to dev's `tools:` list

B) Drop the "create task tracker entries" instruction - keep dev terminal-only

X) Other

[Answer]: B - drop the instruction; dev stays terminal-only (least-privilege tool surface; pipeline already captures progress via retry notes + final response)

---

### Question FD-2 (FR-1.1): what does `tools:` mean exactly?

The SDK auto-adds two built-in tools alongside `tools:` - `FinishTool` (the only way the agent signals "done") and `ThinkTool` (a reasoning scaffold with no environment access).

A) capabilities + FinishTool only - FinishTool auto-injected, ThinkTool dropped

B) capabilities + FinishTool + ThinkTool - both auto-injected as infra; `tools:` lists capabilities only

C) Literal strict - nothing auto-injected; authors list `finish` too; empty = truly nothing (never finishes)

X) Other

[Answer]: B - capabilities + FinishTool + ThinkTool. `tools:` is the exact *capability* allowlist; FinishTool (done signal) and ThinkTool (reasoning scaffold) are always present as infra. Empty `tools:` → agent can think + finish but touch nothing.

---

### Question FD-2b (FR-1.1): keep `filter_tools_regex`?

A) Drop `filter_tools_regex` - the explicit allowlist is the whole story

B) Keep it as an optional additive filter

X) Other

[Answer]: A - drop `filter_tools_regex`. No regex filtering surface to harden or test.

---

### Question FD-3 (FR-1.5): command-step shell invocation

A) Hybrid - `shlex`-split to argv (`shell=False`) when the command has no shell metacharacters; keep `shell=True` for complex commands; env hygiene in both

B) Keep `shell=True` always + env hygiene only

C) argv-only - always `shell=False`

X) Other

[Answer]: A - hybrid. Simple commands (no `&&`/`|`/`>`/`$`/`;`) run argv-style without the shell; commands using shell features keep `shell=True`; environment hygiene (no secret leakage into the child env) in both paths.

---

### Question FD-4 (FR-1.7): reserved-name / collision boundary

A) Collision = any name already in the SDK global registry (`list_registered_tools()`) + non-empty identifier

B) Narrower hardcoded reserved list

X) Other

[Answer]: A - any existing registry name (covers built-ins and prior extensions) plus non-empty identifier.

---

### Question FD-5 (FR-1.6): action-step subprocess hardening scope

A) Minimal - validate pid tokens numeric; explicit `shell=False`; mirror env hygiene

B) Deeper - also resolve binaries via `shutil.which` and drop privileges where possible

X) Other

[Answer]: B - deeper. Validate pid tokens numeric before `kill`/`ps`/`lsof`; resolve `git`/`lsof`/`ps`/`kill` via `shutil.which`; explicit `shell=False`; mirror command-step env hygiene.

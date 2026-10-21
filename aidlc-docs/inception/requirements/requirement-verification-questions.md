# Requirement Verification Questions

**Intent**: Two-stage guardrails & sandboxing for agent-engine —
1. Harden existing tooling injection via what the OpenHands SDK provides
2. Introduce proper kernel-level isolation

**Presentation mode**: inline in chat, one question at a time (AGENTS.md override).
Answers are recorded here as they are given.

---

## Question 1: Stage 1 Scope (SDK Hardening Surface)

Which surfaces should Stage 1 hardening cover?

A) Agent steps only — the OpenHands SDK surface: `tools:` allowlist validation, expose `filter_tools_regex` / `include_default_tools`, fix the `task_tracker` no-op

B) Agent steps + command steps — SDK surface plus subprocess shell hardening in `stages.py` (`_run_command`)

C) Everything — SDK surface, command steps, action-step subprocess calls, and extension tool registration

X) Other (please describe after [Answer]: tag below)

[Answer]: C — Everything: SDK surface, command steps, action-step subprocess calls, and extension tool registration

---

## Question 2: Stage 2 Platform Target

Which platforms must kernel-level isolation support?

A) macOS only — native primitives (sandbox-exec/Seatbelt, Virtualization.framework)

B) macOS + Linux — Landlock/seccomp/user namespaces on Linux; sandbox or VM on macOS

C) Cross-platform via container runtime — Docker/OrbStack abstraction; isolation through containers, not raw kernel APIs

D) macOS VM-based only — Virtualization.framework / tart VM

X) Other (please describe after [Answer]: tag below)

[Answer]: C — Cross-platform via container runtime. "C is better, because we will want to support Linux (and even, sigh, Windows)" — Docker Engine API abstraction; runtime chosen per platform

---

## Question 3: Stage 2 Isolation Scope

What gets sandboxed?

A) Agent terminal tool only — the LLM-driven shell

B) Terminal tool + command steps — both shell surfaces

C) Entire pipeline process — all steps including action steps

X) Other (please describe after [Answer]: tag below)

[Answer]: B — terminal tool + command steps. Rationale: sandbox everything the agent can influence — terminal (direct) and command steps (indirect, via agent-written test code/plugins executed by e.g. pytest). Action steps, LangGraph runtime, LLM calls, viz server, commit stay host-side (trusted code).

---

## Question 4: Isolation Profile Defaults

What default confinement should the sandbox enforce?

A) Read-only workspace + no network — deny-by-default, with explicit per-pipeline grants

B) Read-write workspace + network allowed — but no host paths outside the workspace (process/filesystem confinement only)

C) Profile-based — pipelines declare a sandbox profile (none / readonly / full); no universal default

X) Other (please describe after [Answer]: tag below)

[Answer]: DEFERRED to Functional Design (kernel-level unit). Intent recorded: isolation is OPTIONAL — users are not forced to use a container; mechanism and profile details to be discussed during FD.

---

## Question 5: Backward Compatibility Posture

How should hardening be rolled out against existing pipelines?

A) Default-on hardening — per-pipeline opt-out flags

B) Default-off — per-pipeline opt-in flags

C) Stage-dependent — Stage 1 default-on (cheap, SDK-level); Stage 2 opt-in (heavy, platform-dependent)

X) Other (please describe after [Answer]: tag below)

[Answer]: STAGE 2 = opt-in (user: 'this kernel isolation needs to be optional, we don't want to force users to use a container'). STAGE 1 = ALWAYS-ON, NO OPT-OUT (user: 'always on means no opt-out flags. We're guardrailed by design.')

---

## Question 6: Stage 2 Failure Mode When Isolation Is Unavailable

If the requested isolation mechanism is unavailable on the host (e.g. Linux-only feature on macOS, container runtime not installed), what should happen?

A) Fail fast — refuse to run the pipeline

B) Warn and run unsandboxed

C) Warn and fall back to reduced isolation — e.g. container instead of kernel API, or process-level limits

X) Other (please describe after [Answer]: tag below)

[Answer]: A — Fail fast: refuse to run the pipeline when requested isolation is unavailable.

---

## Question 7: Delivery Granularity

Should the two stages be delivered as separate units of work?

A) Two units — Stage 1 and Stage 2 developed, tested, and committed independently

B) One unit — single cohesive delivery

X) Other (please describe after [Answer]: tag below)

[Answer]: A — two (or more) units. Unit 1 = SDK-level hardening, executed FIRST. Unit 2+ = kernel-level isolation, with only intent specified at requirements time.

---

## Question: Security Extensions

Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)

B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)

X) Other (please describe after [Answer]: tag below)

[Answer]: A — Yes, enforce all SECURITY rules as blocking constraints

---

## Question: Domain Standards Extension

This extension forces a two-phase domain design flow at Application Design and Functional Design: the domain is exposed from the product requirements (exposition Q&A) before any model is proposed, and the proposed model is validated against `coding-standards-ddd.yaml` (descent audit, services as exceptions, no persistence abstractions). All rules are blocking; findings gate stage completion.

A) Yes — enforce the Domain Standards extension as blocking

B) No — do not enforce this extension

X) Other (describe after the [Answer]: tag below)

[Answer]: A — Yes, enforce the Domain Standards extension as blocking

---

## Question: Resiliency Extensions

Should the resiliency baseline be applied to this project?

**What this extension is.** Enabling it applies a set of **directional, design-time best practices** for building resilient systems, derived from the **AWS Well-Architected Framework (Reliability Pillar)** and resilience-review guidance. It steers requirements, design, and code toward fault tolerance, high availability, observability, and recoverability — covering 15 practice areas across business goals, change management, observability, high availability, disaster recovery, and continuous improvement.

**What this extension is NOT.** Enabling it does **not** make your workload production-ready, nor does it certify or guarantee any availability, RTO, or RPO target. It is a **starting point** that scaffolds good resiliency decisions early — it is not a substitute for a formal **AWS Well-Architected Review** of the built system.

Treat the output as a well-grounded **first draft of your resiliency posture** to build on and validate — not a finished, production-certified result.

A) Yes — apply the resiliency baseline as directional best practices and design-time guidance (recommended for business-critical workloads, as an informed starting point that you can validate and harden before go-live)

B) No — skip the resiliency baseline (suitable for PoCs, prototypes, and experimental projects where rapid iteration matters more than reliability)

X) Other (please describe after [Answer]: tag below)

[Answer]: A (scoped) — apply the resiliency baseline as directional best practices, but keep it light: this runs on someone's desktop. Retry/recovery-type guidance is useful; the full server treatment (load, scale, HA/DR) is out of scope.

---

## Question: Property-Based Testing Extension

Should property-based testing (PBT) rules be enforced for this project?

A) Yes — enforce all PBT rules as blocking constraints (recommended for projects with business logic, data transformations, serialization, or stateful components)

B) Partial — enforce PBT rules only for pure functions and serialization round-trips (suitable for projects with limited algorithmic complexity)

C) No — skip all PBT rules (suitable for simple CRUD applications, UI-only projects, or thin integration layers with no significant business logic)

X) Other (please describe after [Answer]: tag below)

[Answer]: B — Partial: enforce PBT rules only for pure functions and serialization round-trips

---

## Question (Follow-up): The file_editor Gap

Your Q3 answer (B) sandboxes the terminal tool and command steps — but the dev/review agents also carry **file_editor**, an agent-controlled file-mutation surface that would still run **host-side**, outside the sandbox.

- A) Sandboxed mode drops `file_editor` from the agent's tool list — the in-sandbox terminal becomes the only file-mutation path
- B) Route `file_editor`'s file operations through the container too
- C) Accept `file_editor` as a host-side surface — document it as residual risk
- X) Other

[Answer]: A, with a deeper rationale — the agent shouldn't have file_editor at all. It exists only so the dev agent can write its report (implementation-summary.md), and that mechanism has proven unreliable: agents often forget to write the report. Requirement added: a better mechanism for the agent to feed back its findings — do not rely on the agent writing its own report file. (See Question 12.)

---

## Question 12: Findings-feedback mechanism

The dev agent must feed its findings to the review/qa agents. Today that's an agent-written file, which agents forget. What should the mechanism be?

A) The pipeline captures the agent's final SDK response and writes the artifact itself — verdict parsing also reads from that captured response
B) Keep file artifacts, but pre-write a template the agent fills in
C) Hybrid — capture the final response always; agent-written files remain an optional supplement
X) Other

[Answer]: A — the pipeline captures the agent's final SDK response and writes the artifact itself. NOTE from user: the parsing logic (of the captured response into summary + verdicts) needs dedicated discussion during Functional Design — some parsing already exists and has had bugs in that area. Defer parsing-logic details to FD, but the capture mechanism itself is a Stage-1 requirement.

## Unit 4 — Claude Dynamic Workflows driver (2026-10-21)

Q1. In workflow mode (no Docker), what executes `command` steps?
[Answer]: A — subagents execute them; each command step becomes a subagent step running the command in Claude Code's own environment, reporting exit code/verdict. No engine process at runtime.

Q2. Module split boundaries?
[Answer]: A — three modules, the light one named `agentic_dev_loop.core` (pipeline model + parsing + workflow-schema projection), plus `engine` (graph/stages/sandbox/CLI) and `viz` (stdlib-only server + event model). "core" chosen over "model" to avoid LLM-model collision; creep risk mitigated by module contract + guard test.

Q3. How does pipeline.yaml become workflow steps?
[Answer]: A (REVERSED from B on 2026-10-21) — parse at BUILD time: at workflow creation, Claude (with tools) imports agentic_dev_loop.core, parses pipeline.yaml, and generates the concrete workflow JS with steps baked in. The skill's bundled JS is a template the build step fills. Runtime never parses. (Raw reversal: "You know what - I changed my mind. pipeline.yaml should be parsed at build time, not runtime")

Q4. Action steps (commit) in workflow mode?
[Answer]: C — small trusted CLI shim (docker-free) reusing the engine's commit logic (clean-at-start, hooksPath, templated message); workflow commit step = subagent invoking the shim.

Q5. Skill+workflow JS vs the intent doc's MCP-tools architecture?
[Answer]: Yes, drop MCP — skill + bundled workflow JS only; subagents reach core/viz via shell/python; ae_* MCP recommendation amended out.

Q6. How does the visualiser work in workflow mode?
[Answer]: A — subagent-launched live server (free-port fallback, URL surfaced); step subagents POST stage events to a new local HTTP ingest endpoint; browser keeps live SSE; engine mode in-process VizBus unchanged.

Q7. Verdict protocol and retry loops in workflow mode?
[Answer]: A — same verdict contract; verdict agents still write VERDICT: PASS/FAIL artifacts; subagents report verdicts in final output; workflow JS routes on_pass/on_fail/goto with its own max_attempts counter.

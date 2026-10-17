# Requirements — Guardrails & Sandboxing for agent-engine

## Unit Ordering (user directive)

1. **Unit 1 — Findings/verdict-passing mechanism** (Q12/FR-1.2, FR-1.3, parsing redesign): a genuine bug-in-waiting; fixed FIRST, before tool-hardening.
2. **Unit 2 — Tool-hardening** (remaining Stage-1 FRs).
3. **Unit 3+ — Kernel-level isolation** (Stage 2, opt-in).

**Units are vertical slices** — each delivers end-to-end user-visible behavior, not a horizontal layer.

## Intent Analysis

- **User request**: Address the intent in two stages — (1) harden the existing tooling injection via what the OpenHands SDK provides, (2) introduce proper kernel-level isolation for guardrails and sandboxing.
- **Request type**: Enhancement (security hardening) of an existing library.
- **Scope**: Multiple components — SDK tool surface, command steps, action-step subprocess calls, extension tool registration, plus a new optional isolation subsystem.
- **Complexity**: Complex. Two delivery units; second unit requires new architecture (container runtime integration), not just code changes.

## Stage 1 — SDK-Level Hardening (Unit 1) — ALWAYS-ON, no opt-out

Applies to every run, no opt-out flags ("we're guardrailed by design"). Existing pipelines must keep working.

### Functional Requirements

| ID | Requirement |
| --- | --- |
| FR-1.1 | **Expose the SDK's tool-restriction surface.** Wire the OpenHands SDK knobs that agent-engine currently ignores — `filter_tools_regex`, `include_default_tools` — through the agent factory so `.agent.md` frontmatter can express them. Fail fast on unknown tool names (already true; preserve). |
| FR-1.2 | **Replace agent-written reports with pipeline-captured responses.** The pipeline captures the agent's **final SDK response** and writes the artifact itself (implementation summary + verdicts parsed from the captured text). Agent file-writes stop being a feedback channel. |
| FR-1.3 | **Drop `file_editor` from shipped agents.** With FR-1.2 it has no remaining job. Its parsing logic (of captured responses into summary + verdicts) gets dedicated treatment during Functional Design — the existing verdict parser has had bugs; do not carry assumptions into the redesign. |
| FR-1.4 | **Fix tool-list/prompt consistency.** The `task_tracker` instruction in `dev.agent.md` is a no-op (tool not in its allowlist). Either add the tool or drop the instruction. |
| FR-1.5 | **Harden command-step shell invocation.** Review `stages.py` `_run_command` (`shell=True` → argv-list where possible; argument quoting; environment hygiene). Scope = harden what exists; kernel isolation is Stage 2. |
| FR-1.6 | **Harden action-step subprocess calls.** Review `actions.py` git/lsof/ps invocations for least-privilege and command-injection resistance. |
| FR-1.7 | **Harden extension tool registration.** Extensions register tools into the SDK **global** registry with no namespacing. Validate names at registration (collision detection against built-ins and other extensions; reserved-name rejection). Fail fast at load. |
| FR-1.8 | **Preserve existing fixed policies.** Fail-fast on missing config/secrets, single host-side commit point gated on clean worktree, verdict retry semantics, crash-safe resume. |

## Stage 2 — Kernel-Level Isolation (Unit 2+) — OPT-IN

Isolation is **optional** — no user is forced to use a container. Not requested ⇒ current behavior unchanged.

### Functional Requirements

| ID | Requirement |
| --- | --- |
| FR-2.1 | **Isolation scope**: the agent `terminal` tool **and** command steps run inside the isolation boundary (both are agent-influence channels — conftest argument: a planted test makes the trusted `pytest` command step execute malicious code). Action steps, LangGraph runtime, LLM calls, viz server, and commit stay host-side (trusted code). |
| FR-2.2 | **Mechanism**: container runtime via the **Docker Engine API** as the abstraction; concrete runtime chosen per platform (Docker Desktop / OrbStack / Colima / podman machine — all speak it). Sandboxed steps get their toolchain from a Linux dev image (image-defined toolchain, like CI); bind mounts carry workspace + state_dir. |
| FR-2.3 | **Failure mode**: isolation requested but no usable runtime available ⇒ **fail fast, refuse to run**. No silent fallback to unsandboxed execution. |
| FR-2.4 | **Platform support**: macOS, Linux, and Windows. Per-platform adaptation: daemon detection (unix socket vs npipe+WSL2), mount-path translation, CRLF/permission-metadata handling on Windows mounts. |
| FR-2.5 | **Profile defaults**: what the sandbox blocks by default (network, file paths, capabilities) — **deferred to Functional Design** ("we can discuss the mechanism during FD"). |
| FR-2.6 | **Host-side commit**: the commit action remains host-side native git (avoids Windows write-back pitfalls). |

### Open Questions (deferred to Functional Design)

- **Linux backend (Unit 3 FD)**: Docker vs native namespace isolation (bubblewrap/Landlock/seccomp). macOS and Windows must be Docker-based (sandboxed steps run a Linux dev image → need a Linux kernel → VM); Linux uniquely can isolate natively without a daemon. If a native-Linux backend is implemented, a shared interface is extracted at that point — the second implementation is the last responsible moment (per DDD rules; no single-implementation interfaces).

## Cross-Cutting / Non-Functional

| ID | NFR |
| --- | --- |
| NFR-1 | **Backward compatibility**: Stage 1 hardening must not break existing pipelines (YAML schema unchanged where possible). Stage 2 is opt-in so default behavior is unchanged. |
| NFR-2 | **Fail-fast culture** (existing policy): missing config/secrets, unknown tools, unknown actions, unavailable isolation — all refuse to run loudly, naming the problem. No silent degradation. |
| NFR-3 | **Security baseline (blocking)**: least privilege for all new subprocess/container surfaces, input validation, supply-chain integrity (image references pinned/digest-verifiable), credential hygiene (no secrets into container env or logs), audit/observability of what ran inside the sandbox. Cloud-shaped rules (network config, HTTP headers, alerting) marked N/A for this library. |
| NFR-4 | **Resiliency (scoped, desktop)**: retry/recovery guidance for transient container failures (image pull, daemon start). Server-grade load/HA/DR/RTO/RPO explicitly out of scope. |
| NFR-5 | **Domain standards (blocking)**: DDD domain model for the pipeline/isolation domain at design time — no persistence abstractions, no behaviourless aggregates; descent audit at validation. |
| NFR-6 | **Property-based testing (partial)**: PBT for pure functions and serialization round-trips (verdict parsing, config (de)serialization) with Hypothesis; property identification in Functional Design. |
| NFR-7 | **Testability**: the isolation backend must be testable without a running container (e.g., fake runtime speaking the same interface); no tests that silently skip when Docker is absent. |

## Key Requirements Summary

1. **Unit 1 (SDK hardening, always-on)**: expose SDK tool-restriction knobs; pipeline captures final agent responses (agent stops writing reports); drop `file_editor`; fix `task_tracker` no-op; harden command/action subprocess surfaces; validate extension tool registration.
2. **Unit 2 (kernel isolation, opt-in)**: container-based sandboxing of the terminal tool + command steps via Docker Engine API; fail fast when unavailable; macOS/Linux/Windows; profile defaults and parsing-logic redesign deferred to Functional Design.
3. **Fixed policies and fail-fast culture preserved; existing pipelines keep working.**

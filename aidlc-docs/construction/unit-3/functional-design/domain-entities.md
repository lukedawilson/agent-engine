# Domain Entities — unit-3 (always-on sandbox isolation)

Per DDD standards: descent audit applied; domain-standards extension enforced. The domain was exposed before this model was proposed (DOMAIN-01 in the plan); every concept below traces to an exposition answer (DOMAIN-03).

## Trace List (DOMAIN-03)

| Domain concept | Exposition answer it came from |
| --- | --- |
| Sandbox | Dimension 1 (FR-2.1's "isolation boundary" concept) + Dimension 2 (the Sandbox owns its request → result execution context) |
| Isolation profile | FR-2.5 "profile defaults" + FD-1 answer (what is blocked: network, writes, git mutations, capabilities) |
| Isolation backends (Docker / native) | FR-2.2 "concrete runtime chosen per platform" + FD-2/2b/2c answers (two concrete backends) |
| SandboxExecutionRequest / SandboxExecutionResult | Dimensions 2–3 (runtime contexts; the request → result flow each sandboxed execution owns) |
| PipelineConfig.isolation | Dimension 2 (PipelineConfig owns the isolation declaration) |
| Host-side set (action steps, LangGraph, LLM, viz, commit) | Dimension 1 — the trusted complement; explicitly NOT a domain object |
| Daemon | Dimension 2 — owns real container state; infrastructure, not our domain |

## New Entity

### `Sandbox` (NEW — descent step 3, `src/agent_engine/isolation.py`)

The isolation boundary: owns one sandboxed execution (create → exec → destroy → result). Rich behaviour, not a data holder:

- `run(request: SandboxExecutionRequest) -> SandboxExecutionResult` — the execution lifecycle; enforces the effective profile and the git-mutation guard; guarantees destruction on every path (BR-8.3).
- Two backend implementations behind one extracted surface: the Docker backend (macOS/Windows) and the native backend (Linux: bubblewrap + Landlock + seccomp). **The interface extraction is not premature**: two implementations exist from day one (FD-2), which is the last-responsible-moment criterion for extraction — not a violation of the no-single-implementation-interface rule.

## Value Objects

### `SandboxExecutionRequest` (NEW — descent step 1, carries invariant behaviour)

| Field | Meaning |
| --- | --- |
| `argv` | command + arguments to execute inside |
| `cwd` | working directory (must be under a mounted root) |
| `env` | scrubbed environment (BR-9.1) |
| `timeout` | per-step bound |
| `mounts` | workspace + state_dir bind mounts |

Behaviour: validation at construction — non-empty argv, cwd inside a mount, bounded sizes (SECURITY-05). Not anaemic.

### `SandboxExecutionResult` (NEW — descent step 1, carries invariant behaviour)

| Field | Meaning |
| --- | --- |
| `exit_code` | the verdict |
| `stdout` / `stderr` | captured output |
| `duration` | timing |
| `backend` | which backend ran it (audit, BR-11) |

Behaviour: `succeeded` / `is_timeout` predicates. Exit-code-is-the-verdict semantics unchanged (unit-2 BR-4.4).

## New Module — pure translation functions (descent step 0)

`src/agent_engine/isolation.py` also hosts the platform-independent pure functions — the bulk of NFR-7 testability:

| Function | Signature | Notes |
| --- | --- | --- |
| `resolve_effective_profile` | `(defaults, overrides) -> IsolationProfile` | merge + validate (BR-5) |
| `select_backend` | `(platform, probe, override) -> BackendChoice` | pure decision over probe results (BR-4) |
| `docker_create_payload` | `(profile, request) -> payload` | profile → Docker create payload (BR-5) |
| `bwrap_argv` | `(profile, request) -> list[str]` | profile → bubblewrap arguments (BR-5) |
| `landlock_ruleset` / `seccomp_policy` | `(profile) -> ruleset / BPF` | profile → kernel policy serialisation (BR-5) |
| `translate_mount_path` | `(host_path, platform) -> str` | per-platform mount translation incl. WSL2 (BR-4.5) |
| `is_git_mutation` | `(argv: list[str]) -> bool` | deny-by-default subcommand classifier (BR-6) |

All pure — the PBT-03 targets. The availability probe (daemon detection, bwrap/kernel-feature check) is an IO adapter beside them, faked in tests (FD-5).

## Modified Entities

### `PipelineConfig` (entity — modified, `src/agent_engine/config.py`)

- Gains the optional `isolation:` section (backend override, profile overrides, image override).
- Behaviour: `effective_profile()` resolves defaults + overrides; unknown keys fail at load (BR-5.3).
- Always-on: absence of the section means opinionated defaults (BR-2.4) — the section configures the sandbox, it never enables/disables it.

### `StagesRuntime._run_command` (module function — modified, `src/agent_engine/stages.py`)

- Routes command steps through `Sandbox.run` instead of a host subprocess (BR-1.1). Host-side env scrubbing (unit-2 `child_env`) feeds the request env (BR-9.1).

### `StagesRuntime.run_agent` / terminal-tool wiring (modified, `src/agent_engine/stages.py`)

- The agent's `terminal` tool becomes a trusted host-side wrapper that delegates to `Sandbox.run` (BR-1.1). The tool stays an SDK capability tool — only its execution path changes.

### `actions.py` (unchanged)

- Action steps (`commit`, `kill_listeners_on_port`, `git_worktree_clean`) remain host-side in-process (BR-1.2, BR-7). No change in this unit.

## Descent Audit (Domain Validation)

| Behaviour | Placement | Step | Verdict |
| --- | --- | --- | --- |
| Resolve effective profile | `resolve_effective_profile` | 0 static helper | Correct — pure merge/validate |
| Choose backend | `select_backend` | 0 static helper | Correct — pure decision; probe is a faked IO adapter |
| Translate profile → mechanism | payload/argv/Landlock/seccomp functions | 0 static helpers | Correct — pure, platform-independent |
| Translate mount paths | `translate_mount_path` | 0 static helper | Correct — pure, per-platform fixtures |
| Classify git mutations | `is_git_mutation` | 0 static helper | Correct — pure predicate |
| Validate request invariants | `SandboxExecutionRequest` constructor | 1 value object | Correct — VO with invariant behaviour |
| Predicates on results | `SandboxExecutionResult.succeeded` / `is_timeout` | 1 value object | Correct — VO with behaviour |
| Execute an isolated command | `Sandbox.run` | 3 new entity | Correct — owns the execution lifecycle; two backends (FD-2) |
| Own the isolation declaration | `PipelineConfig.effective_profile` | 2 method on existing entity | Correct — config owns its declaration |
| Route command steps into the sandbox | `_run_command` | 2 existing orchestration point | Correct — one caller (`make_command_node`) |
| Wire the terminal tool to the sandbox | terminal-tool wrapper | 2 existing tool wiring | Correct — host-side adapter; execution path only |

No delegating entity; no service-named value object; no per-endpoint service; no persistence abstraction (no Repository/DAO — DOMAIN-08 N/A, none proposed); the one extracted interface has two concrete implementations from day one.

## Requirements Traceability

| FR | Covered by | Note |
| --- | --- | --- |
| FR-2.1 (boundary) | BR-1; `Sandbox` + modified `_run_command` / terminal tool | Terminal tool + command steps inside; action/LLM/viz/commit host-side (FD-3 confirmed) |
| FR-2.2 (mechanism) | BR-3, BR-4; backends | **Amended by FD-2/2b/2c:** the abstraction is the `Sandbox` surface, not the Docker Engine API per se; Docker backend on macOS/Windows with harness-pinned image; native backend (host toolchain in namespaces, no image) on Linux. `requirements.md` FR-2.2 wording to be amended accordingly. |
| FR-2.3 (failure mode) | BR-2, BR-8 | **Amended by FD-4:** isolation is always on ⇒ fail fast ALWAYS, not only "when requested". `requirements.md` FR-2.3 + NFR-1 + `unit-of-work.md` opt-in wording to be amended accordingly. |
| FR-2.4 (platforms) | BR-4 | Daemon detection, mount translation, CRLF/permissions |
| FR-2.5 (profile defaults) | BR-5 | FD-1 default + FD-3c git block + FD-4b pinned image |
| FR-2.6 (host-side commit) | BR-6, BR-7 | Commit stays host-side; NEW: agent git mutations blocked by default (FD-3b/3c); residual hook risk accepted + recorded |
| NFR-1 (backward compat) | BR-2.4 | **Reframed by FD-4:** pipeline YAML/semantics unchanged; the sandbox runtime is a NEW environment requirement — loud startup failure on machines without one |
| NFR-2 (fail fast) | BR-8 | Loud, actionable errors |
| NFR-3 (security baseline) | BR-5/6/8/9/11 + Security-baseline mapping table | least privilege, supply chain, credential hygiene, audit |
| NFR-4 (resiliency, scoped) | BR-10 | Idempotent-infra retry only; server-grade out of scope |
| NFR-7 (testability) | BR-12 | Fake at Sandbox surface; pure logic everywhere; marked opt-in integration tests; CI Linux runner (user constraint) |

## Deferred Amendments (recorded, not applied here)

- `requirements.md`: FR-2.2 abstraction wording, FR-2.3 always-on wording, NFR-1 opt-in wording.
- `unit-of-work.md`: the "OPT-IN — not requested ⇒ behavior unchanged" bullet is overturned by FD-4.
- `unit-4-intent-claude-code-backend.md`: its opt-in assumption needs a matching amendment when unit-4 is planned.

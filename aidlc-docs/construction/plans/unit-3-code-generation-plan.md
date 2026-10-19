# Unit 3 Code Generation Plan — kernel-level sandboxing (always-on)

> **STATUS (2026-10-19)**: Plan approved as the basis for documentation. Per user directive
> ("Get the docs ready for the agentic-dev-loop to implement, but do NOT write code"), code
> execution is DEFERRED to the implementing agent. The implementation handoff spec lives at
> `aidlc-docs/construction/unit-3/code/implementation-spec.md` — it consolidates exact
> signatures, docker command templates, config schema, error catalog, SDK seam usage, CI and
> Dockerfile specs, and the test plan. The implementing agent works through the steps below
> against that spec.

**This plan is the single source of truth for Unit 3 Code Generation.** No implementation
happens outside its numbered steps; each step follows TDD (red → green → refactor) per repo
policy. All design decisions trace to approved FD / NFR / Infra artifacts.

## Unit Context

- **Unit**: unit-3 kernel-level sandboxing (always-on), the third and final vertical slice.
- **Dependencies**: unit-1 (output-passing), unit-2 (SDK hardening — `child_env`, `env_allowlist`, tool registry validation). Both COMPLETE; unit-3 builds on their Runtime/Registry/config surfaces.
- **Stories implemented** (story-map): FR-2.1 sandbox the terminal tool + command steps; FR-2.2 Sandbox surface abstraction with Docker backend; FR-2.3 no usable runtime ⇒ fail fast, no silent fallback; FR-2.4 macOS/Windows/Linux platform adaptation; FR-2.5 conservative default profile; FR-2.6 commit stays host-side. Plus NFR-3 (security), NFR-4 (fail fast/fail closed), NFR-6 (config serialisation, shared with unit-1), NFR-7 (testability) and BR-1..BR-13.
- **Domain entities owned**: `Sandbox` (abstract surface + Docker backend), `SandboxExecutionRequest`/`SandboxExecutionResult` VOs, `IsolationConfig`; modified `StepConfig` (`env:`, `setup:`), `PipelineConfig` (`isolation:`), `Runtime`/`StagesRuntime` wiring.
- **Service boundaries**: `src/agentic_dev_loop/isolation.py` owns all sandbox logic. `stages.py`, `agents.py`, `graph.py`, `cli.py`, `config.py` are modified in place. `actions.py` is UNCHANGED (commit + other actions stay host-side, in-process).
- **Project type**: brownfield Python library. Code at workspace root (`src/agentic_dev_loop/`, `tests/`); docs only in `aidlc-docs/construction/unit-3/code/` + repo docs. Never duplicate files (no `*_new.py`).

## Key Decisions (locked, traceable)

| ID | Decision | Source |
| --- | --- | --- |
| KD-1 | One module `src/agentic_dev_loop/isolation.py` — VOs, pure functions, `Sandbox` ABC, `DockerBackend`, probe, audit/stamp helpers | FD domain-entities |
| KD-2 | Image digest bootstrap: `DEFAULT_DEV_IMAGE_REF` constant is digest-pinned; until first publish the constant carries no digest and code fails fast unless `AGENTIC_DEV_LOOP_DEV_IMAGE` env override is set (explicit, loud — never silent). First publish via manual `workflow_dispatch`; the digest is pasted into the same PR. | SECURITY-07, Infra ID-1 |
| KD-3 | Two state dirs, distinct: `PipelineConfig.state_dir` (`.pr`, run state/checkpoint — unchanged) vs `IsolationConfig.state_dir` (default `~/.agentic-dev-loop/state` — stamps + audit JSONL) | Infra ID-3 |
| KD-4 | Terminal tool sandboxing via the SDK seam: `SandboxTerminalExecutor(ToolExecutor)` passed as `TerminalTool.create(conv_state, executor=...)`; per-run re-registration of the `terminal` registry name with a callable factory capturing the run's Sandbox, done inside `run_agent` before agent build. Seam + SDK version range recorded in `COMPAT-SHIMS.md` with a pinning test. | SDK investigation, FD-5 |
| KD-5 | Unit/e2e tests inject a fake `Sandbox` (interface-level fake per FD-5); real-Docker tests are marked `@pytest.mark.docker`, run locally when a daemon is present (Docker 29.3.0 present on dev machine) and always in CI. Never silently skipped — skipped only when the marker filter excludes them, with an explicit skip reason when no daemon. | FD-5, BR-12 |
| KD-6 | CLI gains `--refresh` (force re-provision) and `--clean-stamps` (clear stamp cache); `isolation.refresh` in config mirrors `--refresh` | NFR-5, Infra ID-3 |
| KD-7 | Containers run as root inside the container (portable across Docker Desktop/OrbStack/Colima uid remapping). Native-Linux host caveat (bind-mounted writes land root-owned) documented in `docs/setup.md` troubleshooting; `--user` mapping deferred. | Infra open-CG consideration |
| KD-8 | Execution container keeps `sleep infinity` as its command (the container is an exec target, not a one-shot); `docker exec` carries each request. | BR-1.3, NFR-2 |

## Story Traceability

| Story / Rule | Plan steps covering it |
| --- | --- |
| FR-2.1 terminal + command steps inside | Steps 2, 8, 9 |
| FR-2.2 Sandbox surface + Docker backend | Steps 4, 5 |
| FR-2.3 fail fast, no silent fallback | Steps 5, 7 |
| FR-2.4 platform adaptation (mount translation, daemon detection) | Steps 3, 5, 7, 11 |
| FR-2.5 default profile | Steps 2, 3 |
| FR-2.6 commit host-side | Step 8 (guard test: commit never routed to sandbox) |
| NFR-3.1 per-step env / BR-9 | Steps 1, 2, 8 |
| NFR-3.5 reliability (bounded retry on idempotent infra ops only) | Step 5 |
| NFR-3.6 auditability / BR-11 | Step 6 |
| NFR-3.7 supply chain (digest pin + verify) | Steps 5, 14 |
| NFR-4 fail fast/fail closed / BR-8 | Steps 5, 7, 8 |
| NFR-6 config serialisation | Steps 1, 10 (PBT round-trip incl. isolation section) |
| NFR-7 testability / BR-12 | Steps 10, 11, 12 |
| BR-13 provision phase + setup stamp | Steps 3, 6, 8 |
| BR-6 git-mutation guard | Steps 2, 8, 10 |
| ID-7 user setup guide | Step 15 |

## Files

**Created**

| Path | What |
| --- | --- |
| `src/agentic_dev_loop/isolation.py` | Sandbox ABC, DockerBackend, VOs, pure functions, probe, audit/stamp helpers |
| `tests/test_isolation.py` | Unit tests (fake runner, no docker) |
| `tests/test_isolation_pbt.py` | Hypothesis properties |
| `tests/test_isolation_integration.py` | Marked `docker` integration tests (real daemon) |
| `Dockerfile` | Dev image: python + node + git toolchain |
| `.github/workflows/ci.yml` | ubuntu-latest + windows-latest matrix: unit tests + marked docker tests |
| `.github/workflows/publish-image.yml` | Build/push dev image to GHCR (workflow_dispatch + main push) |
| `docs/setup.md` | 6-section user guide (ID-7 outline) |
| `aidlc-docs/construction/unit-3/code/code-generation-summary.md` | Doc summary (written at the end) |

**Modified**

| Path | What |
| --- | --- |
| `src/agentic_dev_loop/config.py` | `IsolationConfig` (image, refresh, memory/cpus caps, allow_git_mutations, state_dir; extra=forbid), `PipelineConfig.isolation: Optional[IsolationConfig]`, `StepConfig.env: Optional[dict[str, str|None]]`, `StepConfig.setup: Optional[str]` (command steps only) |
| `src/agentic_dev_loop/stages.py` | `_run_command` routes command steps through `Sandbox.run`; `make_command_node` resolves sandbox env + provision trigger; sandbox lifecycle on Runtime (create at start, destroy on end + error paths) |
| `src/agentic_dev_loop/agents.py` | `SandboxTerminalExecutor`, per-run `terminal` re-registration in `run_agent` |
| `src/agentic_dev_loop/graph.py` | Runtime carries Sandbox; load-time probe fail-fast; destroy wiring |
| `src/agentic_dev_loop/cli.py` | `--refresh`, `--clean-stamps`; docker probe in `main` fail-fast path |
| `tests/test_config.py`, `tests/test_stages.py`, `tests/test_agents.py`, `tests/test_cli.py`, `tests/test_e2e_fixtures.py`, `tests/conftest.py` | New cases + fake-Sandbox fixtures |
| `COMPAT-SHIMS.md` + `tests/test_sdk_compat.py` | Terminal-executor seam entry + pinning test |
| `README.md` | Link to `docs/setup.md` |

**Explicitly UNCHANGED**: `src/agentic_dev_loop/actions.py` (commit + actions stay host-side, in-process — FR-2.6).

## Generation Steps

- [x] **Step 1 — Config schema (red→green)**. Add `IsolationConfig` (fields: `image: Optional[str]`, `refresh: bool = False`, `memory: Optional[str]`, `cpus: Optional[float]`, `allow_git_mutations: bool = False`, `state_dir: str = "~/.agentic-dev-loop/state"`; `extra="forbid"` so unknown keys fail load per BR-5), `PipelineConfig.isolation`, `StepConfig.env` (dict of `str|None`, null = inherit), `StepConfig.setup` (validated: command steps only; agent/action steps reject at load per BR-13). Tests in `test_config.py` first: schema accepts/rejects, serialisation round-trip (NFR-6).
- [x] **Step 2 — Pure functions: policy** (`isolation.py`). `resolve_effective_profile(cfg)` (defaults per BR-5: network off, rootfs ro, writes only on mounts, caps dropped, git mutations blocked), `resolve_sandbox_env(step_env)` (fixed safe base PATH/HOME/LANG/LC_ALL/TERM + declared only; global `env_allowlist` never leaks; LLM key never auto-included), `is_git_mutation(argv)` (known-read set allowed; everything else — incl. unknown subcommands — is mutation, deny-by-default per BR-6). TDD in `test_isolation.py`.
- [x] **Step 3 — Pure functions: translation** (`isolation.py`). `translate_mount_path(path, host_platform)` (normalize + expanduser; identity idempotence; WSL2 specifics deferred), `setup_stamp_key(setup_cmd, lockfile_hashes)` (sha256 over cmd + package-lock.json/requirements.txt/*.csproj hashes), `docker_create_payload(...)` for execution container (KD-8 + BR-5 flag set: `--network none --read-only --cap-drop ALL --tmpfs /tmp --tmpfs /root`, mounts, caps 4g/2cpu, `sleep infinity`) and provision payload (network ON, rw rootfs, caps dropped, 8g/4cpu). TDD.
- [x] **Step 4 — VOs** (`isolation.py`). `SandboxExecutionRequest` (argv, cwd, env, timeout; constructor validation = invariant behaviour) and `SandboxExecutionResult` (exit_code, stdout, stderr, duration, backend, timed_out; `succeeded`/`is_timeout` predicates). TDD.
- [x] **Step 5 — Sandbox surface + Docker backend** (`isolation.py`). `Sandbox` ABC (`run(request) -> SandboxExecutionResult`, `close()`); `probe_docker(runner)` (shutil.which("docker") → `docker version --format` API ≥ 1.43 → `docker info` OSType==linux; actionable fail-fast messages pointing at `docs/setup.md`); `DockerBackend` with an injected command runner (no monkeypatching subprocess): `ensure_image` (pull @digest, bounded retry on pull/daemon-wait only — never on exec; digest re-verify via `docker inspect`; KD-2 env override), lazy `create_execution_container`, `docker exec` per request, `close()` stop+rm on all paths. Unit tests with fake runner; real-daemon variants live in Step 11.
- [x] **Step 6 — Provision phase, stamps, audit** (`isolation.py`). `provision(...)`: when the step declares `setup:` and the stamp (KD-3 location) misses or `refresh` is set → run provision container (network ON, setup cmd, cwd = workspace mount), destroy it, write stamp; setup failure = loud step failure, no stamp. `append_audit_record(state_dir, record)` → JSONL at `sandbox-audit.jsonl` with 5 MB rotation to `.1`; `clean_stamps(state_dir)`. TDD.
- [x] **Step 7 — CLI + load-time fail-fast** (`cli.py`). `--refresh`, `--clean-stamps` in `_core_parser`; `main` probe-then-build pattern extended with the docker probe (fail fast before graph build, actionable message). TDD in `test_cli.py` (probe faked via runner injection).
- [x] **Step 8 — stages.py wiring** (`stages.py`, `graph.py`). Runtime gains a `Sandbox` (created at start; probe already passed); `_run_command` builds `SandboxExecutionRequest` (cwd = workspace mount path, env = `resolve_sandbox_env(step.env)`) and returns `(exit_code, output, timed_out)` from the result; git-mutation guard rejects loudly before exec; `make_command_node` triggers provision on stamp miss; destroy on pipeline end + all error paths (try/finally). Guard test: commit/action steps are never routed to the sandbox (FR-2.6). TDD with fake Sandbox.
- [x] **Step 9 — Terminal tool seam** (`agents.py`). `SandboxTerminalExecutor(ToolExecutor)` executing `TerminalAction` → `Sandbox.run` (stateless exec per action; KD-4); per-run `terminal` re-registration in `run_agent` before agent build; executor closed with the sandbox. TDD with fake Sandbox + SDK-behaviour assertions.
- [x] **Step 10 — PBT suite** (`test_isolation_pbt.py`). Hypothesis properties: every generated execution payload contains `--network none`; all `-v` targets within {workspace, isolation state_dir}; `--cap-drop ALL` present; `resolve_sandbox_env` output ⊆ base+declared; stamp-key stability + divergence; request/result round-trip (PBT-02); mount-translation idempotence; git classifier deny-by-default; `select_backend` totality (exactly one backend per platform input).
- [x] **Step 11 — Docker integration tests** (`test_isolation_integration.py`, `@pytest.mark.docker`). Real daemon: probe passes; echo round-trip; network-none verification (no external reach); read-only rootfs + writable mounts; cap-drop sanity; git-mutation block end-to-end; provision + stamp skip-on-match + `refresh` re-provision. Run locally now (daemon present) and in CI.
- [x] **Step 12 — e2e fixtures** (`test_e2e_fixtures.py`, `conftest.py`). Fixtures inject a fake Sandbox by default (unit-2 e2e command-step flows keep passing); a marked `docker` variant runs the pipeline e2e against the real backend. TDD.
- [x] **Step 13 — SDK compat pinning** (`COMPAT-SHIMS.md`, `test_sdk_compat.py`). New shim entry: `TerminalTool.create(..., executor=...)` kwarg + registry callable-factory convention, with version range + removal criterion + canary/pinning test per the existing procedure.
- [x] **Step 14 — CI + image** (`.github/workflows/ci.yml`, `publish-image.yml`, `Dockerfile`). `ci.yml`: matrix ubuntu-latest/windows-latest — deps install, unit tests, marked docker tests (ubuntu: preinstalled; windows: verify/start Docker Desktop); `publish-image.yml`: build + push GHCR `latest` + digest manifest on `workflow_dispatch` and main push. `Dockerfile`: python base + node LTS + git. After first publish: paste digest into `DEFAULT_DEV_IMAGE_REF` (KD-2) in the same PR.
- [x] **Step 15 — Documentation** (`docs/setup.md`, `README.md`, `aidlc-docs/construction/unit-3/code/`). `docs/setup.md` per ID-7 outline (6 sections: engine install per OS; first run + digest-verified pull; pipeline.yaml walkthrough of `isolation:`/`env:`/`setup:`/`allow_git_mutations`; stamp caching + `--refresh`/`--clean-stamps`; troubleshooting with every fail-fast message + audit log location + Linux-host file-ownership caveat (KD-7); security notes). README link. Markdown summaries under `aidlc-docs/construction/unit-3/code/`.
- [x] **Step 16 — Full local run + integrity** — entire test suite green locally (unit + PBT + marked docker with local daemon), story-traceability table verified against completed steps, no duplicate files (brownfield rule), plan checkboxes all `[x]`.

## Scope guardrails

- Mocks only at external boundaries (SDK classes, docker CLI runner injection). File I/O and pure logic use real temp dirs and real implementations.
- No work outside the plan; if a blocker emerges, stop and report rather than improvising.
- Unit-4 intent-doc and inception amendments remain deferred (documented in FD/NFR deferred lists) — not part of this plan.

## Amendment Log — loop-mechanics hardening (2026-10-19, docs-first)

User directive (raw): "I don't want insurance, I want to be sure an agent won't break the loop mechanics mid-run, or start sandboxing before it has all the right setup etc." Plus: "Also, the plan needs to involve updating pipeline.yaml in this repo so it works with this Brave New World"

Decisions (all recorded in audit.md):
- **Q1 UNMOUNT + RELOCATE**: sandbox mount set = workspace ONLY (iso state dir never mounted; stamps/audit host-only). PipelineConfig.state_dir default `.pr` → `~/.agentic-dev-loop/runs/<pipeline-hash>/` (checkpoint DB + last-error.md out of the sandbox). Explicit state_dir configs keep working.
- **Q2 EAGER STARTUP**: probe → image → create+start execution container → pre-provision ALL declared setups (stamp-cached, `--refresh` respected) → then build graph and run steps. Zero infra operations mid-run; mid-run failure = step result or loud daemon death.
- **Q3 TRUSTED HOOKSPATH**: commit action runs git with `-c core.hooksPath=<trusted dir>`. FD BR-7 residual reclassified accepted → mitigated. This is the ONLY actions.py change.
- **PIPELINE.YAML MIGRATION**: `agentic-dev-loop/pipeline.yaml` — drop `state_dir: .pr`; test step uses `.venv-sandbox` venv built by a new `setup:` (provision has network); command gains `-m "not docker"`; `.gitignore` keeps `.pr/` + adds `.venv-sandbox/`. Fixture pipelines in tests declare explicit `state_dir:` under tmp_path (never real home).

Plan-step impacts:
- Step 3 (payload pure functions): signatures lose iso_state_dir; PBT single-mount invariant.
- Step 5 (DockerBackend): eager create/start in __init__; run() = exec only.
- Step 8 (Runtime wiring): eager startup sequence in Runtime.__init__; no step-boundary provision.
- Step 14 (actions): commit action hooksPath + guard tests.
- NEW Step 17: migrate agentic-dev-loop/pipeline.yaml + fixture pipelines + .gitignore + tests asserting the .pr default.
- Test plan gains 5 guard tests (startup-sequence, single-mount, host-only audit/stamps, default state_dir outside workspace, hooksPath argv).
All details live in implementation-spec.md §2.2/§3.3/§3.4/§4/§7/§7.1/§9/§10.

- 2026-10-19T18:45:00Z — package-rename amendment batch (docs-only): all module paths, env var, image, and state-dir references updated `agent-engine` → `agentic-dev-loop`.

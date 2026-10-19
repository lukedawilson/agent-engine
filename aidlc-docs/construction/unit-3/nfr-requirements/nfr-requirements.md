# NFR Requirements — unit-3 (kernel-level sandboxing, always-on)

## Assessment Summary

NFR assessment identified material requirements across security (dominant), performance (new to this unit — sandbox lifecycle overhead), reliability (scoped), testability, usability, and backward compatibility. Scalability and availability remain N/A (desktop library, single pipeline process — same as units 1–2). Two FD-internal conflicts were resolved (BR-9.1 vs BR-9.2 sandbox env secrets; BR-1.3 per-step lifecycle vs Docker startup cost), one major architectural fork was settled by the user (per-step `setup:` hook for stack-agnostic provisioning), and the native Linux backend was dropped by user directive (Docker everywhere, `Sandbox` surface retained). The FD artifacts were amended in place to match.

## Non-Functional Requirements

| ID | NFR | Detail |
| --- | --- | --- |
| NFR-3.1 | **Environment hygiene (sandbox)** | Sandboxed step env = fixed safe base (`PATH`/`HOME`/`LANG`/`LC_ALL`/`TERM`) + the step's declared `env:` mapping only (VAR: value, or null = inherit from host). The global `env_allowlist` never leaks into the sandbox; the LLM API key is never auto-included inside (declared explicitly or not at all). Host-side command/action steps keep unit-2 `child_env` unless the step declares `env:` — then the declared env IS the allowlist for that step. Satisfies SECURITY-06/12; resolves BR-9.1/BR-9.2. |
| NFR-3.2 | **Least privilege / network isolation** | Execution container: `--network none`, read-only rootfs, capabilities dropped, rw only on workspace/state_dir mounts, docker socket never mounted. Network exists only in the trusted provision phase (short-lived provision container, BR-13.3). Satisfies SECURITY-06/07/09. |
| NFR-3.3 | **Performance (sandbox lifecycle)** | Persistent-per-run lifecycle: execution container created lazily at the first sandboxed exec, `docker exec` per request (≈100–300ms), destroyed at pipeline end + error paths. Per-step container create/start/stop (~0.5–2s × every terminal call) is explicitly rejected (NFR-2). Setup hooks are stamp-cached so provisioning is paid once per dependency change, not per run. No formal latency SLO (desktop tool). |
| NFR-3.4 | **Fail fast / fail closed** | No usable Docker daemon ⇒ pipeline refuses to run — always, including the self-hosted dev loop — naming the missing runtime with install instructions. Setup failure, image pull failure, mount failure, unknown config keys: all loud. Every error path destroys the container (no leaked sandboxes). Satisfies SECURITY-15; BR-2/BR-8. |
| NFR-3.5 | **Reliability (scoped resiliency)** | Bounded retry ONLY for idempotent infrastructure ops (image pull, daemon-start wait). Sandboxed command execution is never retried (side effects). Mid-run daemon death = loud step failure with container cleanup. Server-grade load/HA/DR explicitly out of scope (NFR-4 scoped). |
| NFR-3.6 | **Auditability** | Every sandboxed execution is audit-logged host-side: argv, backend/image, exit code, duration — structured, no secrets. Sandboxed code cannot reach host logs. Satisfies SECURITY-03; BR-11. |
| NFR-3.7 | **Supply chain integrity** | Default dev image harness-pinned by digest (python+node+git), digest verified on pull; explicit `isolation.image` override only, never implicit `latest`. Satisfies SECURITY-10/13; BR-5.4. |
| NFR-3.8 | **Testability / PBT** | Fake at the `Sandbox` surface (unit tests need no container); all pure functions (profile resolution, backend selection, sandbox-env resolution, docker payload translation, mount translation, git classifier, stamp key) unit-tested on every platform with PBT-03 properties (network-off, writes-only-on-mounts, capability floor, env scrub, stamp stability) + PBT-02 round-trips. Real-backend integration tests marked + opt-in, NEVER silently skipped. CI: Docker-backend integration tests on ubuntu-latest AND windows-latest (NFR-6). |
| NFR-3.9 | **Backward compatibility** | Additive only: optional `isolation:` section (opinionated defaults when absent), optional per-step `env:`/`setup:` fields, `isolation.refresh` flag. No required keys, no renamed keys; existing pipelines' YAML loads unchanged. **New environment requirement** (per FD-4): a Docker daemon must exist on the machine — loud startup failure otherwise. |
| NFR-3.10 | **Usability** | Fail-fast messages name the missing runtime and give install instructions (Docker Desktop / OrbStack / Colima / podman machine). Provision stamp + `isolation.refresh` / `--refresh` make setup state legible and resettable. Setup failures surface the setup output. |

## Category Dispositions

| Category | Disposition | Justification |
| --- | --- | --- |
| Scalability | N/A | Desktop tool, single pipeline process |
| Performance | Applicable | NFR-3.3 — lifecycle overhead is the unit's real performance question; resolved by persistent-per-run + stamp caching |
| Availability | N/A | No uptime concept; crash-safe resume via checkpointing unchanged; mid-run failures are loud (NFR-3.4/3.5) |
| Security | Dominant | NFR-3.1/3.2/3.4/3.6/3.7 + FD Security-baseline mapping |
| Reliability | Applicable (scoped) | NFR-3.5 — idempotent-infra retry only; no command-execution retry |
| Maintainability | Covered | DDD binding + PBT extension rules; single retained interface |
| Usability | Applicable | NFR-3.10 — actionable failure messages, refresh flag |

## Security Baseline Rule Dispositions (blocking set)

| Rule | Disposition |
| --- | --- |
| SECURITY-01 (encryption) | N/A — library, no data stores |
| SECURITY-02 (network intermediary logging) | N/A — no network intermediaries |
| SECURITY-03 (application logging) | Applicable — NFR-3.6 (structured audit log, no secrets) |
| SECURITY-04 (HTTP headers) | N/A — no web endpoints |
| SECURITY-05 (input validation) | Applicable — request VO validation, config key validation (NFR-3.4; FD BR-5.3) |
| SECURITY-06 (least privilege) | Applicable — NFR-3.1/3.2 (declared-env-only, read-only root, dropped caps, no docker.sock) |
| SECURITY-07 (restrictive network config) | Applicable — NFR-3.2 (execution `--network none`; network only in trusted provision phase) |
| SECURITY-08 (access control) | N/A — no application endpoints |
| SECURITY-09 (hardening) | Applicable — harness-controlled image, fail-closed errors, cleanup on all paths (NFR-3.4) |
| SECURITY-10 (supply chain) | Applicable — NFR-3.7 (digest-pinned image, no `latest`) |
| SECURITY-11 (secure design) | Applicable — defense in depth: kernel-level sandboxing + git guard + env scrub + frozen terminal (FD BR-5/6/9/13) |
| SECURITY-12 (credential management) | Applicable — NFR-3.1 (no secrets into sandbox env unless declared; no hardcoded credentials) |
| SECURITY-13 (integrity verification) | Applicable — NFR-3.7 (digest verified on pull) |
| SECURITY-14 (alerting/monitoring) | N/A — desktop library; audit log covers observability (NFR-3.6) |
| SECURITY-15 (fail-safe defaults) | Applicable — NFR-3.4 (fail closed, resource cleanup on error paths) |

## Amendment (2026-10-19) — loop-mechanics hardening

- **NFR-3.2**: mount minimization — sandbox mount set = workspace only (Q1).
- **NFR-3.3**: lifecycle = eager startup (Q2); startup latency = probe + pull(cached) + create + provision(stamp-cached); per-exec ~100-300ms unchanged.
- **NFR-3.9**: state_dir DEFAULT changes (`.pr` → `~/.agentic-dev-loop/runs/<pipeline-hash>/`); explicit configs keep working. Migration note for existing pipelines.
- **NFR-3.4**: fail-fast set unchanged; provision failure now aborts at startup (AE-SBX-009).

## Amendment (2026-10-19) — package rename

- Package references updated `agent-engine` → `agentic-dev-loop` throughout (module paths, default image `ghcr.io/lukedawilson/agentic-dev-loop/dev`, env var `AGENTIC_DEV_LOOP_DEV_IMAGE`, user state dirs `~/.agentic-dev-loop/*`). No design change.

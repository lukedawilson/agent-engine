# Unit 3 Infrastructure Design — kernel-level sandboxing (always-on)

Unit-3 infrastructure is a **desktop-tool runtime footprint**: the Docker-based sandbox
that every pipeline run depends on. There is no cloud deployment — the "deployment
environments" are developer machines (macOS / Windows / Linux) and CI runners.

## Threat model & terminology (ID-8)

"Kernel-level sandboxing" is the accurate term: the **host kernel performs the
enforcement** — namespaces, cgroups, seccomp-BPF syscall filters, and capability
checks. "Kernel-level isolation" would overclaim a separate kernel per sandbox
(VM / gVisor class), which containers do not have.

| Host | Boundary reality | Residual risk |
| --- | --- | --- |
| macOS / Windows | Docker Desktop / OrbStack run containers inside a Linux VM — the host OS is protected by a hardware-virtualization boundary | container→VM escape, cross-container interference |
| Linux | Plain Docker shares the host kernel; confinement is kernel-enforced | kernel-exploit escape (0-day class) only |

Proportionate to the threat model (agent-influenced damage — exfiltration, repo
mutation, host tampering — not state-actor kernel exploits). Escalation path for
stronger boundaries is the retained `Sandbox` seam: gVisor (`--runtime=runsc`)
or Kata/Firecracker microVMs are a future `runtime:` knob on the same
`docker` CLI transport — no architectural change.

## Logical component → infrastructure mapping

| # | Logical component | Infrastructure choice | Source |
| --- | --- | --- | --- |
| 1 | Docker daemon | Any compliant engine (Docker Desktop, OrbStack, Colima, Rancher Desktop, podman docker-compat) via `docker` CLI; engine API floor ≥ 1.43 (Engine 24); Windows requires Linux-containers mode | ID-2, BR-4 |
| 2 | Pinned dev image | `ghcr.io/lukedawilson/agentic-dev-loop/dev` — python + node + git, built/published by CI, digest-pinned in code, rebuilt on toolchain bumps | ID-1, NFR-3.7 |
| 3 | Image registry | GHCR (public repo → anonymous pulls); digest verified after pull; bounded retry on pull/daemon-wait only (BR-10) | ID-1, NFR-3.7 |
| 4 | Execution container | Per-run container: `--network none --read-only --cap-drop ALL`, tmpfs scratch at `/tmp` + `/root`, rw bind mounts for workspace + state_dir; lazy create, `docker exec` per request, destroy at pipeline end + all error paths | BR-3, BR-5, BR-8, BR-13 |
| 5 | Provision container | Short-lived, network ON (bridge w/ DNS), rw rootfs, `--cap-drop ALL`, same bind mounts; destroyed after `setup:` completes | BR-13 |
| 6 | Bind mounts / state_dir | Host `state_dir` defaults to `~/.agentic-dev-loop/state`; stamps under `state_dir/stamps/` (one per setup key); audit at `state_dir/sandbox-audit.jsonl`; no named volumes — containers are ephemeral | ID-3, ID-5 |
| 7 | CI workflows | GitHub-hosted `ubuntu-latest` + `windows-latest`; publishes the dev image to GHCR; runs the full suite + Docker-backend integration tests | ID-6 |
| 8 | Audit log sink | Host-side JSONL + existing Python logger; 5 MB rotation with one rolled file | ID-5, BR-11 |

## Category dispositions

| Category | Disposition | Detail |
| --- | --- | --- |
| Deployment Environment | PARTIAL | Dev-machine matrix (macOS/Windows/Linux) + GitHub-hosted CI runners. No cloud deployment. |
| Compute | YES | Docker daemon on dev machines + CI. Default caps: execution `--memory 4g --cpus 2`, provision `--memory 8g --cpus 4`; per-pipeline override in `isolation:` | ID-4 |
| Storage | YES | `~/.agentic-dev-loop/state` (stamps + audit), bind-mounted workspace, daemon-local image storage, ephemeral containers only | ID-3 |
| Messaging | N/A | Synchronous local pipeline; no queues or events. |
| Networking | YES | Execution = `--network none`; provision = default bridge; image pull host-side via `docker` CLI. No port publishing ever (viz is host-side). |
| Monitoring | PARTIAL | Host-side audit JSONL + logger; no cloud observability (desktop tool — justified). |
| Shared Infrastructure | YES | Dev image + GHCR registry + CI workflows serve all pipeline runs and all units — see `aidlc-docs/construction/shared-infrastructure.md`. |

## Engine baseline (ID-2)

- Detection probe (load time, fail fast): `docker` CLI on PATH → `docker version --format` engine API ≥ 1.43 → `docker info` `OSType == "linux"` (Windows: fail fast with instructions to switch Docker Desktop to Linux containers).
- Fail-fast messages name the missing runtime + install instructions (BR-2, NFR-3.4).
- WSL2 mount-path specifics deferred (tech-stack-decisions.md) — the `docker` CLI performs npipe/WSL2 transport negotiation.

## Image & supply chain (ID-1)

- Default: `ghcr.io/lukedawilson/agentic-dev-loop/dev` pinned by immutable digest; per-pipeline `isolation.image` override (digest required for non-tag references per SECURITY-07).
- CI publish job builds from a committed Dockerfile and pushes `latest` + digest-tagged manifests; the harness consumes the digest constant, bumped in the same commit as the toolchain change.
- Pull path: host-side `docker pull <image>@<digest>` with bounded retry (BR-10); digest re-verified via `docker inspect` after pull.

## Resource caps (ID-4)

- Execution container: `--memory 4g --cpus 2`; provision container: `--memory 8g --cpus 4` (installs/builds are heavier).
- Overridable per-pipeline via the `isolation:` section; values validated at load (positive, parseable).

## Storage layout (ID-3)

```text
~/.agentic-dev-loop/state/
├── stamps/                # one marker per setup key (setup_cmd + lockfile hashes)
└── sandbox-audit.jsonl    # one JSON record per sandboxed execution (rotates at 5 MB)
```

- Provision outputs (node_modules, build artifacts) live in the bind-mounted workspace — never in state_dir.
- No named volumes, no daemon-side persistence: containers are ephemeral; all durable state is host-side.

## Monitoring & audit (ID-5)

- One JSON record per execution: timestamp, pipeline/step identity, request digest (argv/cwd/env keys, not values), backend, container id, duration, exit code, timeout flag.
- Human-readable mirror via the existing Python logger (INFO).
- 5 MB size cap → rotate to `sandbox-audit.jsonl.1`, overwrite. Host-side only — nothing inside the sandbox writes audit records (BR-11).

## Container hardening recap (per execution container)

| Flag | Value | Rule |
| --- | --- | --- |
| `--network` | `none` | BR-5, NFR-3.2 |
| `--read-only` | rootfs ro | BR-5 |
| `--cap-drop` | `ALL` | BR-5 |
| tmpfs | `/tmp`, `/root` | writable scratch without disk |
| `-v` | workspace, state_dir (rw) | BR-5, FD-1 |
| `--memory --cpus` | 4g / 2 (execution), 8g / 4 (provision) | ID-4 |

## CI (ID-6)

- Workflows live under `.github/workflows/` (first CI in the repo, ships with unit-3):
  - `ci.yml` — ubuntu-latest + windows-latest matrix: unit tests (pure logic) + marked Docker-backend integration tests; Docker preinstalled on ubuntu, Docker Desktop verified/started on windows.
  - `publish-image.yml` — builds + pushes the dev image to GHCR on main, tagged with digest refs.
- Integration tests are opt-in at runtime (never silently skipped) but always run in CI.

## User setup guide (deliverable — ID-7)

A human onboarding guide ships WITH the repo (e.g. `docs/setup.md`, linked from
README) because adoption now involves three moving parts: a Docker engine, the
dev image, and the pipeline.yaml contract. The guide is **written at Code
Generation**; the infra design fixes its outline:

1. **Prerequisites** — install a compliant Docker engine per OS (Docker Desktop on macOS/Windows incl. Linux-containers mode; Docker Engine / OrbStack / Colima / podman on Linux); verify with `docker run hello-world`; engine API ≥ 1.43.
2. **First run** — what happens automatically: load-time probe, digest-verified image pull (bounded retry), `~/.agentic-dev-loop/state/` creation; troubleshooting pull failures (offline, auth, digest mismatch).
3. **Writing pipeline.yaml** — walkthrough of the `isolation:` section (image override, resource caps, refresh), per-step `env:` (fixed safe base + declared vars only; `null` = inherit from host; LLM key handling), per-step `setup:` (command steps only; runs in the provision container with network ON; outputs land in the workspace; stamp-cached), and git-mutation blocking (`allow_git_mutations`).
4. **Stamp caching & refresh** — how the stamp key is computed (setup cmd + lockfile hashes), when setup re-runs, `isolation.refresh` / `--refresh`, `--clean-stamps`.
5. **Troubleshooting** — every fail-fast message (no daemon, engine too old, Windows-containers mode), where the audit log lives, OOM at the resource caps.
6. **Security notes** — what the sandbox blocks (network, read-only rootfs, capabilities, git mutations), what stays host-side (commit action), and the accepted git-hooks caveat.

## Open code-generation considerations (recorded, not decided here)

- Container user identity: dev images run as root inside the container (portable across Docker Desktop/OrbStack/Colima uid remapping); on native-Linux hosts, evaluate `--user $(id -u):$(id -g)` so bind-mounted writes land with host ownership. Decide at Code Generation with tests.
- WSL2 file-sharing path translation (Windows host paths under `\\wsl$` vs `C:\`) — deferred; `docker` CLI + Docker Desktop WSL2 integration handles most cases.

## Amendment (2026-10-19) — loop-mechanics hardening

- **Mount table**: execution + provision containers mount ONLY the workspace (Q1). isolation state_dir (`~/.agentic-dev-loop/state`) is host-only — stamps/audit unreachable by the sandbox.
- **Storage layout**: NEW user-level runs dir `~/.agentic-dev-loop/runs/<pipeline-hash>/` holds checkpoint DB + last-error.md (PipelineConfig.state_dir default, Q1).
- **Lifecycle**: container create+start and all provision runs move to startup (eager, Q2); per-request `docker exec` only during steps.
- **Commit action**: `git -c core.hooksPath=<trusted dir>` (Q3) — hooks residual mitigated.

## Amendment (2026-10-19) — package rename

- Package references updated `agent-engine` → `agentic-dev-loop` throughout (module paths, default image `ghcr.io/lukedawilson/agentic-dev-loop/dev`, env var `AGENTIC_DEV_LOOP_DEV_IMAGE`, user state dirs `~/.agentic-dev-loop/*`). No design change.

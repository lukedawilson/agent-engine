# Unit 3 Infrastructure Design Plan — kernel-level sandboxing (always-on)

## Unit Context

Unit-3 maps the **runtime infrastructure of the always-on sandbox** — a desktop-tool
footprint, not a cloud deployment. From the functional design (BR-3/BR-4, BR-13) and
NFR requirements (NFR-3.1..3.10, TS-1..TS-9), the logical components that need
infrastructure mapping are:

1. **Docker daemon** — external runtime dependency on every dev machine (macOS/Windows/Linux) and CI runner.
2. **Pinned dev image** — shared, digest-pinned image providing python + node + git toolchain.
3. **Image registry** — distribution + pull path for the default image and per-pipeline overrides.
4. **Execution container** — `--network none`, bind-mounted workspace/state_dir, per-run lifecycle.
5. **Provision container** — short-lived, network ON, runs the per-step `setup:` command.
6. **Bind mounts / state_dir** — workspace rw mount, stamp-cache location, host-path translation (incl. WSL2).
7. **CI workflows** — ubuntu + windows runners exercising the Docker backend.
8. **Audit log sink** — host-side record of sandboxed executions (BR-11).

Repo facts: `lukedawilson/agentic-dev-loop` is **PUBLIC** on GitHub; no `.github/workflows/` exists yet (first CI ships with unit-3).

## Category Applicability Analysis (mandated 7 categories)

| Category | Applicable? | Justification |
| --- | --- | --- |
| Deployment Environment | PARTIAL | No cloud deployment — desktop library + CI. Applicable as the dev-machine environment matrix (macOS/Windows/Linux) and CI runner choice. |
| Compute Infrastructure | YES | The sandbox compute surface = the Docker daemon on user machines and CI; engine baseline, container resource caps. |
| Storage Infrastructure | YES | state_dir (stamp cache), bind-mounted workspace, image storage inside the daemon, ephemeral containers (no named volumes). |
| Messaging Infrastructure | N/A | Synchronous local pipeline; no queues, events, or async processing anywhere in the design. |
| Networking Infrastructure | YES | Container network modes (provision = network ON, execution = `--network none`), registry pull path, daemon networking. No port publishing (viz is host-side). |
| Monitoring Infrastructure | PARTIAL | Host-side audit log (BR-11) + existing Python logging; no cloud observability/alerting (justified: desktop tool). |
| Shared Infrastructure | YES | The pinned dev image is shared across pipelines and machines (registry, digest pinning, anonymous-pull posture). |

## Infrastructure Design Steps

- [x] Step 1 — Analyze FD + NFR artifacts; list logical components needing infrastructure (above)
- [x] Step 2 — Category applicability analysis with justifications (table above)
- [x] Step 3/4/5 — Collect answers to ID-1..ID-7, write back to [Answer]: tags
- [x] Step 6a — Generate `aidlc-docs/construction/unit-3/infrastructure-design/infrastructure-design.md`
- [x] Step 6b — Generate `aidlc-docs/construction/unit-3/infrastructure-design/deployment-architecture.md`
- [x] Step 6c — Evaluate whether `shared-infrastructure.md` is warranted (pinned image shared across units → likely YES, decided in ID-1)
- [ ] Step 7-9 — Completion message → approval → audit + aidlc-state.md update

## Open Questions

### ID-1 — Default dev image source & registry (Shared Infrastructure / supply chain)

Repo is PUBLIC, so GHCR anonymous pulls would work. Options: publish our own image via CI vs pin a third-party digest vs adopt community image.

**Q:** Where should the pinned default dev image (python + node + git) come from?

[Answer]: A — publish our own `agentic-dev-loop/dev` image to GHCR via a CI job; digest-pinned in code, rebuilt when toolchain bumps ship. Provision stays fast (toolchain baked in); anonymous pulls OK (public repo).

### ID-2 — Docker engine baseline & mode detection (Compute / Deployment Environment)

Which engines do we support: any modern docker-CLI-compatible daemon, or a certified list? Windows: require Linux-containers mode?

**Q:** What is the supported engine matrix and detection baseline?

[Answer]: A — any compliant daemon reachable via `docker` CLI with a minimum engine API version floor (≥ 1.43 / Engine 24). Docker Desktop, OrbStack, Colima, Rancher Desktop, podman docker-compat all pass. Windows: probe `docker info` OSType and fail fast with switch instructions if in Windows-containers mode.

### ID-3 — state_dir location & stamp-cache eviction (Storage)

**Q:** Where does state_dir live by default, and what is the stamp-cache eviction policy?

[Answer]: A — `~/.agentic-dev-loop/state` (Path.home()-based, per-user). Stamps under `state_dir/stamps/`, one stamp per setup key; growth bounded by distinct setups used; manual cleanup via a CLI clean command. Provision outputs stay in the workspace (not state_dir).

### ID-4 — Container resource caps (Compute)

**Q:** Should execution/provision containers get default memory/CPU caps (overridable per-pipeline)?

[Answer]: A — conservative defaults on both containers (execution: `--memory 4g --cpus 2`; provision: `--memory 8g --cpus 4`), overridable per-pipeline via the `isolation:` section.

### ID-5 — Audit log sink (Monitoring)

**Q:** Where does the host-side audit log go (file/console/format/rotation)?

[Answer]: A — JSONL appended to `state_dir/sandbox-audit.jsonl` (one record per execution: request digest, backend, duration, exit code, container id) + human-readable line via existing Python logger. Rotation: 5MB size cap with one rolled `.1` file. Host-side only.

### ID-6 — CI runners & Docker provisioning (Deployment Environment)

**Q:** GitHub-hosted runners (ubuntu-latest + windows-latest) with Docker preinstalled, or self-hosted?

[Answer]: A — GitHub-hosted runners: ubuntu-latest (Docker preinstalled) + windows-latest (Docker Desktop preinstalled; workflow verifies/starts engine). Public repo = free standard minutes. CI publishes the dev image to GHCR (ID-1) and runs Docker-backend integration tests.

### ID-7 — User setup instructions (change request, raised during review)

**Q:** Where should the setup instructions live and who is the audience?

**User request (raw)**: "Also need to provide proper setup instructions for the users' agents, since setup is more complex (e.g. on setting up the dev images, writing the pipeline.yaml file, etc.)"

[Answer]: A — human onboarding guide shipped WITH the repo (e.g. `docs/setup.md` linked from README). Infra design specifies the deliverable + full outline now; the guide itself is written at Code Generation.

### ID-8 — "kernel-level" terminology (change request, raised during review)

**User question (raw)**: "does docker truly count as 'kernel-level isolation'?" then "Can we accurately call it kernel-level sandboxing?"

[Answer]: YES to "kernel-level sandboxing" — the kernel performs the enforcement (namespaces, cgroups, seccomp-BPF, capabilities), which is exactly what Docker/runc delivers. NO to "kernel-level isolation" — that implies a separate kernel per sandbox (VM/gVisor class), which containers don't have. Resolution: adopt "kernel-level sandboxing" across construction docs + state; keep the threat-model section (shared kernel on Linux hosts, VM boundary on macOS/Windows via Docker Desktop/OrbStack, gVisor/Kata as documented escalation path via the Sandbox seam); queue requirements.md / unit-of-work.md / unit-4 doc terminology fixes as deferred amendments.

## Amendment Log

- 2026-10-19T13:41:15Z — plan created at Infrastructure Design stage start.
- 2026-10-19T14:05:00Z — change request during review: user setup guide added as a unit-3 deliverable (ID-7, answer A).
- 2026-10-19T14:20:00Z — change request during review: terminology amended to "kernel-level sandboxing" (ID-8).
- 2026-10-19T18:45:00Z — package-rename amendment batch (docs-only): repo renamed on GitHub (`lukedawilson/agentic-dev-loop`); image path, state dirs, and module references updated throughout this plan.

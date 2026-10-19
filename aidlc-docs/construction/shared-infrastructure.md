# Shared Infrastructure (Construction)

Infrastructure shared across units and all pipeline runs, first defined during
unit-3 Infrastructure Design (2026-10-19). Units 1-2 had no infrastructure
(all categories N/A — they deferred container infra to unit-3).

## 1. Docker sandbox runtime

- **What**: any compliant Docker daemon (engine API ≥ 1.43 / Engine 24) reachable via the `docker` CLI; Windows requires Linux-containers mode.
- **Who uses it**: every unit-3+ pipeline run (always-on isolation) and all CI jobs.
- **Governed by**: `aidlc-docs/construction/unit-3/infrastructure-design/infrastructure-design.md` (engine baseline, container hardening, resource caps).

## 2. Pinned dev image + GHCR registry

- **What**: `ghcr.io/lukedawilson/agent-engine/dev` (python + node + git), digest-pinned in code; published by CI on main; per-pipeline `isolation.image` override.
- **Who uses it**: all sandboxed pipelines on all machines (default image), CI.
- **Governed by**: SECURITY-07 (digest pinning + post-pull verification); publish flow in CI `publish-image.yml` (ships with unit-3).

## 3. CI workflows

- **What**: `.github/workflows/ci.yml` (ubuntu-latest + windows-latest matrix: unit tests + Docker-backend integration tests) and `publish-image.yml` (image build/push). First CI in the repo — ships with unit-3.
- **Who uses it**: the whole repo (units 1-3 tests run together; future units extend the matrix).

## 4. Per-user state directory

- **What**: `~/.agent-engine/state/` — provision stamps (`stamps/`) and the sandbox audit log (`sandbox-audit.jsonl`).
- **Who uses it**: all pipelines on a machine; shared across projects (one stamp per setup key).

## Change process

- Digests and engine-version floors change via normal commits; toolchain bumps must bump the image digest constant in the same commit.
- CI workflow changes follow the same per-unit design/approval flow as code.

## 5. Per-user run state (added 2026-10-19, Q1)

- `~/.agent-engine/runs/<pipeline-hash>/` — default PipelineConfig.state_dir: checkpoint DB + last-error.md + per-run artifacts, OUTSIDE the sandbox mount.

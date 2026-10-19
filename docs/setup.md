# Sandboxed execution setup

The agentic-dev-loop sandbox is **always on** (unit-3): the agent `terminal`
tool and command steps run inside a Docker-based, kernel-enforced boundary.
There is no opt-out — the `isolation:` section configures the sandbox, it never
disables it. This guide covers the three moving parts: the Docker engine, the
dev image, and the `pipeline.yaml` contract.

## 1. Prerequisites

Install a compliant Docker engine with **Engine API ≥ 1.43** (Engine 24):

- **macOS / Windows** — [Docker Desktop](https://www.docker.com/products/docker-desktop/).
  On Windows, ensure **Linux containers mode** is active (Docker Desktop →
  Settings → General → "Use the WSL 2 based engine" / Linux containers).
- **Linux** — Docker Engine, [OrbStack](https://orbstack.dev/),
  [Colima](https://github.com/abiosoft/colima), or a podman docker-compat
  machine.

Verify the engine:

```bash
docker run --rm hello-world
docker version --format '{{.Server.APIVersion}}'   # must be >= 1.43
docker info --format '{{.OSType}}'                 # must be "linux"
```

If the API is older, or `OSType` is not `linux`, the pipeline refuses to run
with a fail-fast message pointing here.

## 2. First run

On first run the pipeline probes the daemon, then pulls the **digest-pinned**
dev image (`ghcr.io/lukedawilson/agentic-dev-loop/dev`) and verifies its
digest — the supply-chain check refuses to continue on a mismatch. Later runs
reuse the local image cache; the pull is retried (bounded) only on
connection/timeout errors, never on auth/not-found.

Until the first image is published, the pinned digest constant is empty and
startup fails fast with `AE-SBX-005`. For a pre-publish dev loop, point the
engine at any image (tag or digest) via an environment override:

```bash
export AGENTIC_DEV_LOOP_DEV_IMAGE=ghcr.io/lukedawilson/agentic-dev-loop/dev:latest
```

The override wins over the pinned digest and over any per-pipeline
`isolation.image:` — it is the explicit, never-silent escape hatch.

## 3. Writing pipeline.yaml

The `isolation:` section is optional (opinionated defaults apply when absent):

```yaml
isolation:
  image: ghcr.io/org/custom-dev@sha256:...  # override (digest required)
  refresh: false          # force re-provision of every setup: hook
  memory: 4g              # execution-container memory cap
  cpus: 2                 # execution-container cpu cap
  allow_git_mutations: false
  state_dir: ~/.agentic-dev-loop/state   # host-only stamps + audit (never mounted)
```

- **`env:` (per step)** — `VAR: value` sets it in the sandbox; `VAR: null`
  inherits the host value. The sandbox env is the fixed safe base
  (`PATH`/`HOME`/`LANG`/`LC_ALL`/`TERM`) **plus declared vars only** — the
  global `env_allowlist` never leaks in and the LLM key is never auto-added.
- **`setup:` (command steps only)** — a trusted author command (e.g.
  `python -m venv .venv-sandbox && .venv-sandbox/bin/pip install -e ".[dev]"`)
  that runs in the **provision container with network ON** at startup, before
  any step executes. Outputs land in the bind-mounted workspace. Agent and
  action steps reject `setup:` at load.
- **Git mutations** are blocked by default inside the sandbox (commit, push,
  branch/tag create/delete, rebase, …); reads (`status`/`log`/`diff`) always
  work. `allow_git_mutations: true` re-allows them per-pipeline.
- **`state_dir` (run state)** defaults to
  `~/.agentic-dev-loop/runs/<pipeline-hash>/` — the checkpoint DB and
  `last-error.md` live there, **outside** the workspace mount, unreachable by
  the sandbox. An explicit `state_dir:` keeps working unchanged; pointing it
  inside the workspace is an author-accepted exposure.

## 4. Caching

Every `setup:` hook is **stamp-cached** in
`~/.agentic-dev-loop/state/stamps/`, keyed by the setup command plus the
sha256 of the workspace's lockfiles (`package-lock.json`, `requirements.txt`,
`*.csproj`). A matching stamp skips the hook — provisioning is paid once per
dependency change, not per run.

- `isolation.refresh: true` (or the CLI `--refresh` flag) forces re-provision
  of every declared setup.
- `agentic-dev-loop … --clean-stamps` deletes the cached stamps and exits.

## 5. Troubleshooting

Every fail-fast error points here (`AE-SBX-<NNN>`):

| Code | Cause | Fix |
| --- | --- | --- |
| AE-SBX-001 | `docker` not on PATH | install an engine (§1) |
| AE-SBX-002 | daemon unreachable | start your engine (§1) |
| AE-SBX-003 | engine API < 1.43 | upgrade Docker (§1) |
| AE-SBX-004 | `OSType` ≠ linux | switch Docker Desktop to Linux containers (§1) |
| AE-SBX-005 | no pinned digest, no env override | set `AGENTIC_DEV_LOOP_DEV_IMAGE` (§2) |
| AE-SBX-006 | image pull failed after retries | check connectivity/credentials (§2) |
| AE-SBX-007 | post-pull digest mismatch | supply-chain check failed; re-pull |
| AE-SBX-008 | git mutation blocked | set `isolation.allow_git_mutations: true` (§3) |
| AE-SBX-009 | `setup:` command failed | inspect its output tail; stamp not written |
| AE-SBX-010 | container create/start/exec failure | inspect the docker error |
| AE-SBX-012 | daemon lost mid-run | restart the engine; cleanup is best-effort |

The audit trail of every sandboxed execution is at
`~/.agentic-dev-loop/state/sandbox-audit.jsonl` (rotates at 5 MB); run state
is under `~/.agentic-dev-loop/runs/`.

**Linux-host note**: containers run as root inside the container, so
bind-mounted writes can land root-owned in your workspace. Recover with
`sudo chown -R $USER <workspace>`.

## 6. Security notes

This is **kernel-level sandboxing** — the host kernel enforces the boundary via
namespaces, cgroups, capability checks and seccomp-BPF syscall filters. The
execution container runs `--network none` (no egress), `--read-only` rootfs,
`--cap-drop ALL`, with writes only on the single bind-mounted workspace. The
network exists only in the trusted provision phase. The Docker socket is never
mounted. Action steps, the LangGraph runtime, LLM calls, the viz server, and
the commit action stay host-side.

Git hooks during the commit action are **mitigated**, not a residual risk: the
commit action runs `git -c core.hooksPath=<trusted dir>`, so repo hooks in
`.git/hooks` never execute. Residual risks: an agent can mutate setup outputs
inside the writable workspace (the git-mutation guard and the dirty-at-start
commit gate limit persistence), and an explicit in-workspace `state_dir`
choice is the author's accepted exposure.

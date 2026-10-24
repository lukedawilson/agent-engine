# Tech Stack Decisions - unit-3 (kernel-level sandboxing, always-on)

## Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| TS-1 | **Docker transport**: `docker` CLI subprocess, resolved via `shutil.which("docker")` (NFR-3) | The CLI transparently handles unix socket, npipe, WSL2, and docker contexts; zero new runtime dependencies (no new supply-chain surface in a security-focused unit); consistent with unit-2's binary-resolution pattern. Structured data read from CLI output (create/start return codes + IDs, `docker inspect --format` for digest/state). |
| TS-2 | **Default dev image**: one harness-pinned digest image with python + node + git (the shipped pipeline's needs); per-pipeline `isolation.image` override for dotnet/C#/exotic stacks (NFR-3.7, user-confirmed) | Single small image keeps pull/pinning simple; override covers everything else rather than a fat all-SDK image. |
| TS-3 | **New module**: `src/agentic_dev_loop/isolation.py` - `Sandbox` surface + `DockerSandbox` backend + pure functions (`resolve_effective_profile`, `select_backend`, `resolve_sandbox_env`, `docker_create_payload`, `setup_stamp_key`, `translate_mount_path`, `is_git_mutation`) | A module, not a service (DDD descent step 0/3). Native backend dropped by user directive; `Sandbox` surface retained as the extension seam. |
| TS-4 | **Per-step `env:` mapping** on `StepConfig` (NFR-1) | `config.py`: optional `env: dict[str, str | None]` (null = inherit from host). Sandbox env = fixed safe base + declared env only; host-side steps keep `child_env` unless they declare env. `env_allowlist` stays on `PipelineConfig` (backward compat). |
| TS-5 | **Persistent-per-run lifecycle** (NFR-2) | Lazy-create the execution container at the first sandboxed exec; `docker exec` per request; destroy at pipeline end + error paths. Rejects the ~0.5–2s per-step container tax during agent conversations. |
| TS-6 | **Provision phase**: per-step `setup:` hook (command steps only) runs in a short-lived provision container with network ON; execution container is `--network none` (BR-13) | Docker networking is container-level (cannot flip per-exec), so the phases cannot share a container. Setup runs inside the backend environment, never on the host (ABI correctness). |
| TS-7 | **Stamp caching**: `setup_stamp_key(setup_cmd, lockfile_hashes)` → stamp in `state_dir`; skip setup on match; `isolation.refresh` / `--refresh` forces re-provision (NFR-5) | Runtime analogue of Docker layer caching (builder cache rejected: bind-mount shadowing, fragile auto-staging, deps hidden in images). Lockfiles: package-lock.json / requirements.txt / *.csproj. |
| TS-8 | **CI**: two new workflows ship with unit-3 - Docker-backend integration tests on ubuntu-latest and windows-latest (NFR-6) | Repo has no CI today; FD BR-12.4 promised the Linux workflow; user added Windows. Real-backend tests marked + opt-in, never silently skipped. |
| TS-9 | **No new runtime dependencies** anywhere in unit-3 | Stdlib + `docker` CLI + existing deps only; `hypothesis` already present (PBT-03 properties for the pure functions). |

## Deferred (out of unit-3)

| Item | Deferred to |
| --- | --- |
| Native Linux backend (bwrap + Landlock + seccomp) | Dropped from this intent by user directive (2026-10-19); `Sandbox` surface retained as the extension seam for a future backend |
| WSL2-runtime specifics if GitHub windows runners expose WSL2 | Default npipe path shipped now; WSL2 translation is pure-function-covered (mount translation fixtures) |
| lima/VM-based local Linux dev loop | Not needed - Docker-backend CI on ubuntu-latest covers Linux runtime |

## Amendment (2026-10-19) - package rename

- Package references updated `agent-engine` → `agentic-dev-loop` throughout (module paths, default image `ghcr.io/lukedawilson/agentic-dev-loop/dev`, env var `AGENTIC_DEV_LOOP_DEV_IMAGE`, user state dirs `~/.agentic-dev-loop/*`). No design change.

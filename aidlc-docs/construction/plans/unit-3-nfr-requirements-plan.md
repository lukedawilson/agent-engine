# NFR Requirements Plan - unit-3 (kernel-level sandboxing, always-on)

## Unit Context (from functional-design, amended by NFR-stage decisions)

Unit 3 adds the always-on sandbox (BR-2): agent `terminal` tool + command steps execute inside a sandbox; fail fast when no usable runtime; host-side commit unchanged; agent git mutations blocked by default.

**NFR-stage amendments to the FD (user-directed, 2026-10-19):**

1. **Native Linux backend DROPPED (keep the interface)** - user directive: "drop native linux sandboxing from this intent (but keep the interface)". Docker is now the only backend on all three platforms (Docker Desktop / OrbStack / Colima / podman machine on macOS+Linux; npipe/WSL2 on Windows). The extracted `Sandbox` surface is retained as the extension seam for future backends. Consequence list: BR-3.2 (native bwrap+Landlock+seccomp) removed; BR-4 backend-selection simplifies to daemon detection + image resolve (`backend:` override knob removed - no second backend to select); bwrap_argv/landlock_ruleset/seccomp_policy pure functions dropped from the FD; NFR-4 (kernel-feature strictness) withdrawn; FD-5 Linux coverage now = Docker-backend integration tests on a GitHub Actions ubuntu runner (docker preinstalled; the userns/apparmor concern evaporates).
2. **Per-step `env:` mapping** (NFR-1) - sandbox env = fixed safe base + the step's declared env only; `env_allowlist` never leaks into the sandbox; LLM key never auto-included inside (resolves BR-9.1/BR-9.2).
3. **Persistent-per-run lifecycle** (NFR-2) - Docker: lazy container at first sandboxed exec, `docker exec` per request, destroyed at pipeline end + error paths (amends BR-1.3).
4. **`docker` CLI subprocess transport** (NFR-3) - `shutil.which("docker")`; zero new runtime dependencies.
5. **Per-step `setup` hook** (NFR-5, in progress) - stack-agnostic provisioning (user: "The code could be anything - nodejs, react, C#... So all the sandboxes need to be able to somehow access a working dev environment"). Setup = trusted author command per command step, runs INSIDE the backend environment with network ON; outputs land in the bind-mounted workspace; execution phase stays frozen (network off). Agent terminal never runs setup, never gets network. One pinned "dev" image (python+node+git) + per-pipeline `image:` override for dotnet/C#/exotic stacks. Caching approach: pending (Docker-layer-cache question).

NFR posture: security dominant (mapped in FD business-rules + security-baseline dispositions); performance material (per-step lifecycle overhead - resolved by persistent-per-run); scalability/availability N/A (desktop library, single pipeline process). The repo has no CI workflows; FD BR-12.4 promises the Linux workflow ships with unit-3; Windows coverage open (NFR-6).

## NFR Steps

- [x] Analyze unit-3 functional-design artifacts for NFR implications
- [x] Resolve NFR open questions (NFR-1..NFR-6 answered; NFR-4 withdrawn - native backend dropped)
- [x] Generate `aidlc-docs/construction/unit-3/nfr-requirements/nfr-requirements.md`
- [x] Generate `aidlc-docs/construction/unit-3/nfr-requirements/tech-stack-decisions.md`
- [x] Security-baseline dispositions table (blocking set)

## Open Questions

### Question NFR-1: secrets in the sandbox environment (BR-9.1 vs BR-9.2)

[Answer]: Per-step declared env (follow-up A). User (raw): "I thought we decided this already! The pipeline.yaml steps get respective env sections with the env vars their corresponding steps can see." Follow-up confirmed: StepConfig gains an optional `env:` mapping (VAR: value, or null = inherit from host). Resolved design: sandboxed step env = fixed safe base (PATH/HOME/LANG/LC_ALL/TERM) + that step's declared env ONLY - the global `env_allowlist` never leaks into the sandbox and the LLM key is never auto-included inside (declared explicitly or not at all); host-side command/action steps keep unit-2 `child_env` unless the step declares env, in which case the declared env IS the allowlist for that step (key included only if declared). `env_allowlist` stays on PipelineConfig for backward compatibility. Agent steps' declared env applies to their sandboxed terminal. Resolves BR-9.1/BR-9.2: no secrets in the sandbox unless the author explicitly declares them.

### Question NFR-2: sandbox lifecycle - per-step ephemeral vs persistent per run (BR-1.3)

[Answer]: A - Persistent per run. Docker: one container created lazily at the first sandboxed exec, `docker exec` per request, container destroyed at pipeline end (and on all error paths - BR-8.3). Per-command statelessness preserved (matches today's terminal semantics); lifecycle is backend-internal behind the single `Sandbox.run(request)` surface. BR-1.3 amended accordingly: per-request exec semantics, per-run container lifecycle.

### Question NFR-3: Docker daemon transport (tech stack)

[Answer]: A - `docker` CLI subprocess, resolved via `shutil.which("docker")` (unit-2 binary-resolution pattern). The CLI transparently handles unix socket, npipe, WSL2, and docker contexts; zero new runtime dependencies. Structured data (image digest verification, container IDs) read from CLI output (e.g. `docker create`/`docker start` return codes + IDs; `docker inspect --format` for digest/state).

### Question NFR-4: native backend kernel-feature strictness - WITHDRAWN

Withdrawn 2026-10-19 by user directive: "drop native linux sandboxing from this intent (but keep the interface)". Docker is the only backend on all platforms; bwrap/Landlock/seccomp content is removed from the FD (BR-3.2, the native-backend entity, and the bwrap_argv/landlock_ruleset/seccomp_policy pure functions).

### Question NFR-5: toolchain delivery - per-step `setup` hook (stack-agnostic provisioning)

User (raw): "The code could be anything - nodejs, react, C#, we're not platform-specific. So all the sandboxes need to be able to somehow access a working dev environment. We could give each step in pipeline.yaml a pre-command or hook which prepares everything and gives it to the sandbox. Examples would be: setup: npm i && npm run build / setup: dotnet build."

Agreed design (user confirmed points 1, 2, 3, 5):

1. **Setup runs INSIDE the backend environment, never on the host** - host-side `npm i` on macOS would produce darwin binaries that cannot run in the Linux sandbox; ABI correctness requires the provision phase to run in the container.
2. **Separate provision/execution network contexts** - Docker networking is container-level (cannot flip network per-exec): the provision phase runs in its own short-lived provision container with network ON (destroyed after), and the execution container is created with `--network none`. This is a deliberate consequence of the design.
3. **One pinned "dev" image** (python+node+git - the shipped pipeline's needs) + per-pipeline `image:` override for dotnet/C#/exotic stacks.
4. **Caching**: OPEN - user asked "why not just leverage docker's caching?" - see discussion.
5. **Accepted risk (recorded)**: the workspace is writable inside the sandbox (BR-5.1), so the agent can mutate setup outputs (e.g. poison `node_modules` before a later `npm test` step). Host containment still holds; git-mutation guard + commit dirty-at-start policy limit persistence.

Also agreed: agent terminal never runs setup, never gets network - frozen, full stop.

[Answer]: Setup-hook design agreed (points 1, 2, 3, 5 above) + **stamp caching approved**: skip setup on stamp match; stamp written to `state_dir` keyed by (setup command + lockfile hash: package-lock.json / requirements.txt / *.csproj); a pipeline-level `isolation.refresh` (or CLI `--refresh`) flag forces re-provision. Docker's native builder layer-cache rejected for this design (see discussion: bind-mount shadowing, fragile auto-staging of arbitrary setup strings, deps hidden in images); stamp caching is the runtime analogue of layer caching.

### Question NFR-6: Windows coverage - CI or not (FR-2.4)

The repo has no CI workflows at all; FD BR-12.4 promises the Linux CI workflow ships with unit-3 (now = Docker-backend integration tests on ubuntu-latest). FR-2.4 claims macOS/Linux/Windows support - but the dev loop here is macOS, and Windows runtime paths would otherwise never execute anywhere.

A) Add a Windows CI job too (recommended) - GitHub Actions windows runner (Docker Desktop is on the GitHub runner images) running the Docker-backend integration tests; gives FR-2.4 real automated coverage; pure translation logic already unit-tested everywhere

B) Linux CI only - Windows support delivered but runtime-untested (documented); Windows-specific logic (npipe, mount translation, CRLF) covered only by unit tests of the pure translation functions

C) No CI at all - contradicts FD BR-12.4; not an option

X) Other

[Answer]: A - Add a Windows CI job: GitHub Actions windows runner (Docker Desktop on the GitHub runner images) running the Docker-backend integration tests. FR-2.4 gets real automated coverage; Windows-specific pure translation logic already unit-tested everywhere. Linux CI job = Docker-backend integration tests on ubuntu-latest (docker preinstalled).

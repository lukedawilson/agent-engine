# Unit 3 Code Generation Summary — kernel-level sandboxing (always-on)

Implemented per `implementation-spec.md` and the 16-step plan (TDD). All 580
tests pass locally (unit + PBT + marked Docker integration, real daemon).

## Files created

| Path | What |
| --- | --- |
| `src/agentic_dev_loop/isolation.py` | `Sandbox` ABC, `DockerBackend`, VOs, pure functions, probe, audit/stamp helpers, eager `startup_sandbox` |
| `tests/test_isolation.py` | VOs, pure functions, DockerBackend (fake runner), provision/stamps/audit, startup sequence |
| `tests/test_isolation_pbt.py` | Hypothesis properties (network-off, single-mount, cap-drop, env-scrub, stamp key, mount idempotence, git deny-by-default, selection totality, round-trips) |
| `tests/test_isolation_integration.py` | `@pytest.mark.docker` real-daemon tests (probe, echo, no-network, read-only rootfs, git guard, provision/stamp/refresh) |
| `Dockerfile` | python:3.12-slim + git/node/coreutils dev image |
| `.github/workflows/ci.yml` | ubuntu/windows matrix: `-m "not docker"` + `-m docker` |
| `.github/workflows/publish-image.yml` | build/push dev image to GHCR + digest print |
| `docs/setup.md` | 6-section user guide (ID-7) |

## Files modified

| Path | Change |
| --- | --- |
| `config.py` | `IsolationConfig` (extra=forbid), `PipelineConfig.isolation`, `StepConfig.env`/`setup`, state_dir default relocation at load |
| `stages.py` | `Runtime.sandbox`; `_run_command` sandbox routing; `make_command_node` sandbox env; `run_agent` terminal re-registration |
| `agents.py` | `SandboxTerminalExecutor`, `register_sandbox_terminal` (per-run `terminal` re-registration) |
| `graph.py` | eager startup + `try/finally` sandbox close; state_dir expanduser |
| `cli.py` | `--refresh`, `--clean-stamps` |
| `actions.py` | commit action runs git with trusted `core.hooksPath` (the ONLY actions.py change, Q3) |
| `tests/*` + `conftest.py` | `FakeSandbox` fixture; guard tests (Q1/Q2/Q3) |
| `COMPAT-SHIMS.md` + `test_sdk_compat.py` | terminal-seam entry + canary |
| `README.md`, `agentic-dev-loop/pipeline.yaml`, `.gitignore`, `pyproject.toml` | sandbox section; `.venv-sandbox` migration; `docker` marker |

## Deviations flagged (spec vs design artifacts)

- `DockerBackend.__init__` keeps an `iso_state_dir` param (host-only audit sink),
  consistent with the implementation-spec §2.3 exact signature; the Q1
  amendment ("iso_state_dir param dropped") is honoured where it matters — the
  mount set is EXACTLY `{workspace}` and the iso state dir is never mounted.
- `SandboxExecutionRequest` gains two optional host-side fields (`pipeline`,
  `step`) for the BR-11 audit record; the container never sees them.
- `_run_command` gained an optional `sandbox=` keyword (backward-compatible) so
  the sandboxed path could reuse the existing signature while the host path
  stays byte-for-byte unit-2.

## Guard tests landed

1. Startup sequence performs exactly probe → inspect → create → start →
   provision*, run phase is exec-only (Q2).
2. Mount set == {workspace}; iso state dir never in any docker argv (Q1).
3. Audit record exists even when exec fails; host-side only (Q1).
4. Pipeline default `state_dir` resolves outside the workspace (Q1).
5. Commit argv carries `core.hooksPath`; `.git/hooks` never execute (Q3).

#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT"

# The engine must run from an OUT-OF-WORKSPACE install (020): the sandbox
# mounts exactly this repo, so an in-repo `.venv` would be agent-writable and
# the next run would execute agent-modified engine code in the host. pipx
# installs into `~/.local/pipx/venvs` — outside the mount set, so the startup
# self-check accepts it:
#   pipx install agentic-dev-loop   # or `pipx install .` for a local snapshot
# An existing install is upgraded on EVERY run (below) — the engine evolves
# fast and a stale install rejects newer pipeline configs at load time
# (e.g. `deps_policy` in v1.0.0a11 rejected by an a10 install).
#
# The pipeline reads the LLM key from the HOST environment (api_key_env:).
# Do not create a `.env` file here — the engine refuses a run when the
# workspace contains `.env*` (019); export the key instead:
#   export OPENAI_API_KEY=...

if ! command -v agentic-dev-loop >/dev/null 2>&1; then
  echo "error: agentic-dev-loop is not on PATH" >&2
  echo "       install it outside the workspace with pipx and re-run:" >&2
  echo "         pipx install agentic-dev-loop" >&2
  exit 1
fi

# Keep the pipx-managed install current. pipx upgrade is a no-op (a fast
# index check) when the latest release is already installed. Fail fast on
# upgrade failure — running the loop with a stale engine is worse than
# not running it.
if ! pipx upgrade agentic-dev-loop; then
  echo "error: 'pipx upgrade agentic-dev-loop' failed —" >&2
  echo "       the engine install may not be pipx-managed, or the index is unreachable" >&2
  exit 1
fi

exec agentic-dev-loop "$ROOT/agentic-dev-loop/pipeline.yaml" "$@"

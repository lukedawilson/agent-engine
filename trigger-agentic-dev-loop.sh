#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT"

# The pipeline reads the LLM key from the HOST environment (api_key_env:).
# Do not create a `.env` file here — the engine refuses a run when the
# workspace contains `.env*` (019); export the key instead:
#   export OPENAI_API_KEY=...

exec "$ROOT/.venv/bin/agentic-dev-loop" \
  "$ROOT/agentic-dev-loop/pipeline.yaml" \
  "$@"

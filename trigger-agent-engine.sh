#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT"

# Load local secrets (e.g. OPENAI_API_KEY) if present, so the pipeline's
# `api_key_env:` resolves without an explicit export. Never committed.
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  set +a
fi

exec "$ROOT/.venv/bin/agent-engine" \
  "$ROOT/agent-engine/pipeline.yaml" \
  "$@"

#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT"
exec "$ROOT/.venv/bin/python" "$ROOT/viz_demo.py" "$@"

#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

cd "$ROOT"

# Default: flood the attempt-1 dev node with 600 console lines so the
# sidebar's tailing (bottom-anchored scrolling, 500-line eviction with the
# "…N lines omitted" counter) is visible. Any explicit args override this.
if [ "$#" -eq 0 ]; then
    set -- --flood 600
fi

exec "$ROOT/.venv/bin/python" "$ROOT/viz_demo.py" "$@"

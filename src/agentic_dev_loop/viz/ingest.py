"""Workflow-mode viz ingest: the token-authenticated stage-event shape (BR-9).

The viz server issues a random token at launch; step subagents POST stage
events with that token; the read-only SSE view stays tokenless. These two
helpers are stdlib-only so the ingest surface never drags a heavy dep into
the workflow path.
"""

from __future__ import annotations

import secrets

TOKEN_BYTES = 32


def issue_ingest_token() -> str:
    """A fresh, unguessable ingest token (unique per launch, PBT-guarded)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def make_ingest_event(step: str, status: str, output: str) -> dict:
    """Shape a stage event for the HTTP ingest endpoint. `status` is one of
    ``started`` / ``finished`` / ``failed``; `output` is the step's console
    or verdict text. Pure and deterministic given its inputs."""
    return {"type": "stage", "step": step, "status": status, "output": output}

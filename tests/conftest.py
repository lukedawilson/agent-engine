"""Shared test doubles. FakeAgents replaces `stages.run_agent` — the SDK
network boundary (the ONLY permitted stub per repo mock policy); everything
else runs real: real files, real git, real checkpoint DB."""

import sys
from pathlib import Path

# `viz_demo.py` lives at the repo root (a demo script, not part of the
# package), and plain `pytest` does not put the working directory on
# sys.path (unlike `python -m pytest`). Insert the repo root — idempotently —
# so the suite passes under any invocation, including CI.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest

from agentic_dev_loop.stages import AgentResult


class FakeAgents:
    """Scripted stand-in for stages.run_agent. Behaviors are per-agent lists
    consumed in call order (the last one repeats):

      ("ok",)                                — run finishes, no final response
      ("write", path, content)               — writes an artifact, finishes
                                               (final response = content)
      ("truncated",)                         — cut short, no final response
      ("write_truncated", path, content)     — writes, then is cut short
      ("raise",)                             — run_agent internally fails
                                               (its contract: never raise,
                                               return ok=False)
      ("crash",)                             — KeyboardInterrupt escapes the
                                               graph (process-death resume)

    Capture mirroring: for steps that capture (produces/artifact), ("ok",)
    and ("truncated",) — which produce no final response — return
    capture_error="empty_response", exactly as the real run_agent does.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self.calls: list[dict] = []
        self.script: dict[str, list[tuple]] = {}
        monkeypatch.setattr("agentic_dev_loop.stages.run_agent", self)

    def set(self, agent: str, behaviors: list[tuple]) -> None:
        self.script[agent] = list(behaviors)

    def agents_called(self) -> list[str]:
        return [c["agent"] for c in self.calls]

    def messages_for(self, agent: str) -> list[str]:
        return [c["message"] for c in self.calls if c["agent"] == agent]

    def __call__(self, agent, message, runtime, max_iterations=500, step=None):
        self.calls.append({"agent": agent, "message": message,
                           "max_iterations": max_iterations})
        n = sum(1 for c in self.calls if c["agent"] == agent)
        behaviors = self.script.get(agent) or [("ok",)]
        b = behaviors[min(n - 1, len(behaviors) - 1)]
        kind = b[0]
        if kind == "raise":
            return AgentResult(ok=False)
        if kind == "crash":
            raise KeyboardInterrupt()
        captures = step is not None and (step.artifact is not None or step.produces)
        response = None
        capture_error = None
        if kind in ("write", "write_truncated"):
            (runtime.state_dir / b[1]).write_text(b[2])
            response = b[2]
        elif kind == "respond":
            response = b[1]
        elif captures:
            capture_error = "empty_response"
        return AgentResult(ok=True, truncated=kind in ("truncated", "write_truncated"),
                           response=response, capture_error=capture_error)


@pytest.fixture
def fake_agents(monkeypatch):
    return FakeAgents(monkeypatch)

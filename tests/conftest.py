"""Shared test doubles. FakeAgents replaces `stages.run_agent` — the SDK
network boundary (the ONLY permitted stub per repo mock policy); everything
else runs real: real files, real git, real checkpoint DB."""

import pytest

from agent_engine.stages import AgentResult


class FakeAgents:
    """Scripted stand-in for stages.run_agent. Behaviors are per-agent lists
    consumed in call order (the last one repeats):

      ("ok",)                                — run finishes, writes nothing
      ("write", path, content)               — writes an artifact, finishes
      ("truncated",)                         — cut short, writes nothing
      ("write_truncated", path, content)     — writes, then is cut short
      ("raise",)                             — run_agent internally fails
                                               (its contract: never raise,
                                               return ok=False)
      ("crash",)                             — KeyboardInterrupt escapes the
                                               graph (process-death resume)
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch):
        self.calls: list[dict] = []
        self.script: dict[str, list[tuple]] = {}
        monkeypatch.setattr("agent_engine.stages.run_agent", self)

    def set(self, agent: str, behaviors: list[tuple]) -> None:
        self.script[agent] = list(behaviors)

    def agents_called(self) -> list[str]:
        return [c["agent"] for c in self.calls]

    def messages_for(self, agent: str) -> list[str]:
        return [c["message"] for c in self.calls if c["agent"] == agent]

    def __call__(self, agent, message, runtime, max_iterations=500):
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
        if kind in ("write", "write_truncated"):
            (runtime.state_dir / b[1]).write_text(b[2])
        return AgentResult(ok=True, truncated=kind in ("truncated", "write_truncated"))


@pytest.fixture
def fake_agents(monkeypatch):
    return FakeAgents(monkeypatch)

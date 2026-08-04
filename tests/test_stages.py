"""Stage nodes, routers, context assembly, and the run_agent port.

The yosk hardcoded stages (dev/checks/review/qa + bump) become per-step node
and router closures built from the pipeline config; the fixed policies
(hygiene, verdict-first truncation, unclear-verdict retry, notes) stay here."""

import dataclasses
from types import SimpleNamespace

import pytest
from langgraph.graph import END
from openhands.sdk import LLM
from openhands.sdk.conversation.state import ConversationExecutionStatus

from agent_engine.config import PipelineConfig
from agent_engine.registry import default_registry
from agent_engine.stages import (
    Runtime, build_context, make_agent_node, make_bump_node, make_router,
    run_agent,
)


def make_cfg(steps, **over):
    base = {"name": "t", "llm": {"model": "m", "api_key_env": "K"},
            "agents_dir": "agents", "steps": steps}
    base.update(over)
    return PipelineConfig.model_validate(base)


STEPS = [
    {"name": "dev", "agent": "dev", "produces": ["implementation-summary.md"],
     "on_pass": "checks"},
    {"name": "checks", "agent": "checks", "artifact": "ci-fix.md",
     "verdicts": {"pass": "PASS", "fail": "FAIL"},
     "on_pass": "review", "on_fail": {"goto": "dev", "retry": True}},
    {"name": "review", "agent": "review", "artifact": "review-findings.md",
     "verdicts": {"pass": "APPROVED", "fail": "NEEDS CHANGES"},
     "on_pass": "success"},  # no on_fail — fail is fatal, unclear retries entry
]


@pytest.fixture
def runtime(tmp_path):
    state_dir = tmp_path / ".pr"
    state_dir.mkdir()
    return Runtime(cfg=make_cfg(STEPS), registry=default_registry(),
                   llm=LLM(model="openai/test-model", api_key="sk-test"),
                   agents_dir=tmp_path / "agents", state_dir=state_dir,
                   workspace=tmp_path)


def make_state(**over):
    state = {"subject": "plan plan.md", "docs": {"plan.md": "THE PLAN"},
             "context": "CTX", "attempt": 1, "max_attempts": 3, "notes": [],
             "failed": False, "outcome": None, "commit_allowed": False,
             "step_verdicts": {}, "retry_target": None, "thread_id": "t1"}
    state.update(over)
    return state


class TestBuildContext:
    def test_subject_docs_and_generated_output_paths(self, runtime):
        ctx = build_context(runtime, {"plan.md": "THE PLAN", "std.yaml": "STD"},
                            "plan plan.md", [])
        assert "You are working on plan plan.md." in ctx
        assert "## plan.md\n\nTHE PLAN" in ctx
        assert "## std.yaml\n\nSTD" in ctx
        assert "## Expected output paths" in ctx
        assert "dev agent writes: `.pr/implementation-summary.md`" in ctx
        assert "checks agent writes: `.pr/ci-fix.md`" in ctx
        assert "review agent writes: `.pr/review-findings.md`" in ctx
        assert "Previous attempt feedback" not in ctx

    def test_notes_section_only_when_notes(self, runtime):
        ctx = build_context(runtime, {}, "s", ["note one", "note two"])
        assert "## Previous attempt feedback\n\nnote one\n\nnote two" in ctx

    def test_output_paths_workspace_relative_for_subdirectory_pipeline(self, tmp_path):
        """yosk layout: the pipeline YAML lives in a subdirectory while the
        workspace is the repo root — the prompt path must reach the real
        state_dir; state_dir.name alone sends agents to the wrong directory
        (U18 burned 3 attempts on an unfindable ci-fix.md)."""
        state_dir = tmp_path / "agent-engine" / ".pr"
        state_dir.mkdir(parents=True)
        rt = Runtime(cfg=make_cfg(STEPS), registry=default_registry(),
                     llm=LLM(model="openai/test-model", api_key="sk-test"),
                     agents_dir=tmp_path / "agents", state_dir=state_dir,
                     workspace=tmp_path)
        ctx = build_context(rt, {}, "s", [])
        assert "checks agent writes: `agent-engine/.pr/ci-fix.md`" in ctx

    def test_output_paths_absolute_when_state_dir_outside_workspace(self, tmp_path):
        state_dir = tmp_path / "state" / ".pr"
        state_dir.mkdir(parents=True)
        workspace = tmp_path / "ws"
        workspace.mkdir()
        rt = Runtime(cfg=make_cfg(STEPS), registry=default_registry(),
                     llm=LLM(model="openai/test-model", api_key="sk-test"),
                     agents_dir=tmp_path / "agents", state_dir=state_dir,
                     workspace=workspace)
        ctx = build_context(rt, {}, "s", [])
        assert f"checks agent writes: `{state_dir}/ci-fix.md`" in ctx


class TestAgentNode:
    def test_pass_verdict(self, runtime, fake_agents):
        fake_agents.set("checks", [("write", "ci-fix.md", "all good\nVERDICT: PASS\n")])
        update = make_agent_node(runtime, runtime.cfg.steps[1])(make_state())
        assert update["step_verdicts"] == {"checks": "pass"}
        assert update["failed"] is False
        assert "notes" not in update

    def test_fail_verdict_surfaces_artifact_and_retry_target(self, runtime, fake_agents):
        fake_agents.set("checks", [("write", "ci-fix.md", "broken build\nVERDICT: FAIL\n")])
        update = make_agent_node(runtime, runtime.cfg.steps[1])(make_state(attempt=2))
        assert update["step_verdicts"] == {"checks": "fail"}
        assert update["retry_target"] == "dev"
        (note,) = update["notes"]
        assert "broken build" in note and "attempt 2" in note

    def test_verdicts_merge_with_prior_steps(self, runtime, fake_agents):
        fake_agents.set("checks", [("write", "ci-fix.md", "VERDICT: PASS")])
        state = make_state(step_verdicts={"dev": "pass"})
        update = make_agent_node(runtime, runtime.cfg.steps[1])(state)
        assert update["step_verdicts"] == {"dev": "pass", "checks": "pass"}

    def test_missing_artifact_is_unclear(self, runtime, fake_agents):
        update = make_agent_node(runtime, runtime.cfg.steps[1])(make_state())
        assert update["step_verdicts"] == {"checks": None}
        (note,) = update["notes"]
        assert "did not write `.pr/ci-fix.md` on attempt 1" in note
        assert update["retry_target"] == "dev"  # on_fail's goto

    def test_unclear_note_carries_workspace_relative_path(self, tmp_path, fake_agents):
        state_dir = tmp_path / "agent-engine" / ".pr"
        state_dir.mkdir(parents=True)
        rt = Runtime(cfg=make_cfg(STEPS), registry=default_registry(),
                     llm=LLM(model="openai/test-model", api_key="sk-test"),
                     agents_dir=tmp_path / "agents", state_dir=state_dir,
                     workspace=tmp_path)
        update = make_agent_node(rt, rt.cfg.steps[1])(make_state())
        (note,) = update["notes"]
        assert "did not write `agent-engine/.pr/ci-fix.md` on attempt 1" in note

    def test_unparseable_verdict_surfaces_content(self, runtime, fake_agents):
        fake_agents.set("checks", [("write", "ci-fix.md", "I am undecided")])
        update = make_agent_node(runtime, runtime.cfg.steps[1])(make_state())
        (note,) = update["notes"]
        assert "unparseable" in note
        assert "VERDICT: PASS" in note and "VERDICT: FAIL" in note
        assert "I am undecided" in note

    def test_unclear_retries_entry_step_when_no_fail_route(self, runtime, fake_agents):
        # review has no on_fail — the unclear-retry policy targets the entry step
        update = make_agent_node(runtime, runtime.cfg.steps[2])(make_state())
        assert update["retry_target"] == "dev"

    def test_verdict_first_truncation_passes(self, runtime, fake_agents):
        fake_agents.set("checks", [("write_truncated", "ci-fix.md", "VERDICT: PASS")])
        update = make_agent_node(runtime, runtime.cfg.steps[1])(make_state())
        assert update["step_verdicts"] == {"checks": "pass"}
        assert "notes" not in update

    def test_truncated_without_verdict_notes_cut_short(self, runtime, fake_agents):
        fake_agents.set("checks", [("write_truncated", "ci-fix.md", "partial findings")])
        update = make_agent_node(runtime, runtime.cfg.steps[1])(make_state())
        assert update["step_verdicts"] == {"checks": None}
        (note,) = update["notes"]
        assert "cut short" in note and "partial findings" in note

    def test_agent_failure_sets_failed(self, runtime, fake_agents):
        fake_agents.set("checks", [("raise",)])
        update = make_agent_node(runtime, runtime.cfg.steps[1])(make_state())
        assert update == {"failed": True}

    def test_plain_agent_step_runs_and_continues(self, runtime, fake_agents):
        update = make_agent_node(runtime, runtime.cfg.steps[0])(make_state())
        assert update == {"failed": False}
        assert fake_agents.calls[0]["max_iterations"] == 500  # default budget

    def test_max_iterations_from_step(self, runtime, fake_agents):
        step = make_cfg([{"name": "qa", "agent": "qa", "artifact": "qa.md",
                          "verdicts": {"pass": "PASS", "fail": "FAIL"},
                          "max_iterations": 200, "on_pass": "success"}]).steps[0]
        make_agent_node(runtime, step)(make_state())
        assert fake_agents.calls[0]["max_iterations"] == 200


class TestRouter:
    def test_failed_goes_to_end(self, runtime):
        router = make_router(runtime, runtime.cfg.steps[0])
        assert router(make_state(failed=True)) == END

    def test_plain_step_routes_on_pass(self, runtime):
        router = make_router(runtime, runtime.cfg.steps[0])
        assert router(make_state()) == "checks"

    def test_pass_routes_on_pass(self, runtime):
        router = make_router(runtime, runtime.cfg.steps[1])
        assert router(make_state(step_verdicts={"checks": "pass"})) == "review"

    def test_fail_retry_while_attempts_remain(self, runtime):
        router = make_router(runtime, runtime.cfg.steps[1])
        assert router(make_state(attempt=1, step_verdicts={"checks": "fail"})) == "bump"

    def test_fail_retry_exhausted_ends(self, runtime):
        router = make_router(runtime, runtime.cfg.steps[1])
        assert router(make_state(attempt=3, step_verdicts={"checks": "fail"})) == END

    def test_unclear_retries_then_exhausts(self, runtime):
        router = make_router(runtime, runtime.cfg.steps[1])
        assert router(make_state(attempt=1, step_verdicts={"checks": None})) == "bump"
        assert router(make_state(attempt=3, step_verdicts={"checks": None})) == END

    def test_fail_without_route_ends(self, runtime):
        router = make_router(runtime, runtime.cfg.steps[2])  # review: no on_fail
        assert router(make_state(step_verdicts={"review": "fail"})) == END

    def test_pass_to_success_terminal(self, runtime):
        router = make_router(runtime, runtime.cfg.steps[2])
        assert router(make_state(step_verdicts={"review": "pass"})) == "success"

    def test_default_on_pass_is_next_step(self, runtime):
        cfg = make_cfg([{"name": "a", "agent": "a"}, {"name": "b", "agent": "b"}])
        runtime = dataclasses.replace(runtime, cfg=cfg)
        router = make_router(runtime, cfg.steps[0])
        assert router(make_state()) == "b"

    def test_last_step_default_on_pass_is_success(self, runtime):
        cfg = make_cfg([{"name": "a", "agent": "a"}, {"name": "b", "agent": "b"}])
        runtime = dataclasses.replace(runtime, cfg=cfg)
        router = make_router(runtime, cfg.steps[1])
        assert router(make_state()) == "success"

    def test_plain_goto_on_fail_routes_directly(self, runtime):
        cfg = make_cfg([
            {"name": "a", "agent": "a"},
            {"name": "c", "agent": "c", "artifact": "c.md",
             "verdicts": {"pass": "PASS", "fail": "FAIL"}, "on_fail": "a"},
        ])
        runtime = dataclasses.replace(runtime, cfg=cfg)
        router = make_router(runtime, cfg.steps[1])
        assert router(make_state(step_verdicts={"c": "fail"})) == "a"


class TestBumpNode:
    def test_consumes_attempt_resets_verdicts_rebuilds_cleans(self, runtime):
        for stale in ("ci-fix.md", "implementation-summary.md", "last-error.md"):
            (runtime.state_dir / stale).write_text("stale")
        state = make_state(attempt=1, notes=["N1"],
                           step_verdicts={"checks": "fail"})
        update = make_bump_node(runtime)(state)
        assert update["attempt"] == 2
        assert update["step_verdicts"] == {}
        assert update["failed"] is False
        assert "## Previous attempt feedback\n\nN1" in update["context"]
        assert "## plan.md\n\nTHE PLAN" in update["context"]
        for stale in ("ci-fix.md", "implementation-summary.md", "last-error.md"):
            assert not (runtime.state_dir / stale).exists()


class FakeConversation:
    """Boundary stub for the SDK's network-driving Conversation."""

    def __init__(self, status, **kwargs):
        self.state = SimpleNamespace(execution_status=status)
        self.kwargs = kwargs
        self.messages = []
        self.closed = False

    def send_message(self, message):
        self.messages.append(message)

    def run(self):
        pass

    def close(self):
        self.closed = True


class TestRunAgent:
    def test_missing_agent_file_reports_last_error(self, runtime):
        result = run_agent("ghost", "msg", runtime)
        assert result.ok is False
        err = (runtime.state_dir / "last-error.md").read_text()
        assert "Agent run failed" in err and "ghost.agent.md" in err

    def _write_agent(self, runtime):
        runtime.agents_dir.mkdir()
        (runtime.agents_dir / "dev.agent.md").write_text(
            "---\nname: dev\ntools: [terminal]\n---\nDo the work.")

    def test_finished_run_is_not_truncated(self, runtime, monkeypatch):
        self._write_agent(runtime)
        convs = []
        monkeypatch.setattr(
            "agent_engine.stages.Conversation",
            lambda **kw: convs.append(FakeConversation(ConversationExecutionStatus.FINISHED, **kw)) or convs[-1])
        result = run_agent("dev", "the task", runtime, max_iterations=200)
        assert result.ok and not result.truncated
        (conv,) = convs
        assert conv.messages == ["the task"]
        assert conv.kwargs["max_iteration_per_run"] == 200
        assert conv.kwargs["workspace"] == str(runtime.workspace)
        assert conv.closed

    def test_unfinished_run_is_truncated(self, runtime, monkeypatch):
        self._write_agent(runtime)
        monkeypatch.setattr(
            "agent_engine.stages.Conversation",
            lambda **kw: FakeConversation(ConversationExecutionStatus.ERROR, **kw))
        result = run_agent("dev", "msg", runtime)
        assert result.ok and result.truncated

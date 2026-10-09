"""Graph builder + run_pipeline behavioral tests.

The yosk-equivalent YAML below must reproduce the hardcoded loop's behavior:
dev → check → review → port_sweep → qa → commit, retries to dev, failure on
exhaustion/exception. run_agent is stubbed (the SDK network boundary);
everything else — files, git, checkpoints — is real.

NOTE: port_sweep params use port 18099 with an impossible match string so a
test run can never kill a real local dev server (topology is unchanged)."""

import argparse
import queue
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest

from agent_engine.config import load_config
from agent_engine.graph import build_graph, run_pipeline
from agent_engine.llm import build_llm
from agent_engine.registry import default_registry, load_extensions
from agent_engine.stages import Runtime
from agent_engine.viz import VizBus

YOSK_YAML = """\
name: yosk-construction
extensions:
  - agent_engine.extensions.aidlc:AidlcExtension
additional_files:
  - coding-standards-ddd.yaml
llm:
  model: openai/deepseek-v4-pro
  base_url: https://api.deepseek.com
  api_key_env: TEST_LLM_KEY
  extra_body: { chat_template_kwargs: { thinking: false } }
state_dir: .pr
max_attempts: 3
agents_dir: sdk_agents
steps:
  - name: dev
    agent: dev
    produces: implementation-summary.md
    on_pass: check
  - name: check
    agent: check
    artifact: ci-fix.md
    verdicts: { pass: PASS, fail: FAIL }
    on_pass: review
    on_fail: { goto: dev, retry: true }
  - name: review
    agent: review
    artifact: review-findings.md
    verdicts: { pass: APPROVED, fail: NEEDS CHANGES }
    on_pass: port_sweep
    on_fail: { goto: dev, retry: true }
  - name: port_sweep
    action: kill_listeners
    params: { port: 18099, match: agent-engine-test-no-such-proc }
    on_pass: qa
  - name: qa
    agent: qa
    artifact: qa-report.md
    verdicts: { pass: PASS, fail: FAIL }
    max_iterations: 200
    on_pass: commit
  - name: commit
    action: commit
    params: { message: "feat: construct {subject} (agent dev loop)" }
    on_pass: success
"""


# The command step exercises a real subprocess: dev writes `.pr/fix.marker`
# (the marker), the mechanical `test` gate passes only when it exists, and a
# missing marker rewinds to dev with the gate's output in the retry note.
COMMAND_STAGE_YAML = """\
name: command-stage
llm:
  model: openai/deepseek-v4-pro
  base_url: https://api.deepseek.com
  api_key_env: TEST_LLM_KEY
state_dir: .pr
max_attempts: 3
agents_dir: sdk_agents
steps:
  - name: dev
    agent: dev
    produces: implementation-summary.md
    on_pass: test
  - name: test
    command: python -c "import sys; import pathlib; print('test output'); sys.exit(0 if pathlib.Path('.pr/fix.marker').exists() else 1)"
    on_pass: commit
    on_fail: { goto: dev, retry: true }
  - name: commit
    action: commit
    params: { message: "feat: construct {subject} (agent dev loop)" }
    on_pass: success
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repo with the yosk-equivalent pipeline committed clean."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pipeline.yaml").write_text(YOSK_YAML)
    (repo / "coding-standards-ddd.yaml").write_text("STANDARDS")
    (repo / "plan.md").write_text("THE PLAN")
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "init")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("TEST_LLM_KEY", "sk-test")
    return repo


def args(**over):
    base = {"plan": Path("plan.md"), "resume": None, "max_attempts": None}
    base.update(over)
    return argparse.Namespace(**base)


def script_all_pass(fake_agents):
    fake_agents.set("dev", [("write", "implementation-summary.md", "built it")])
    fake_agents.set("check", [("write", "ci-fix.md", "VERDICT: PASS")])
    fake_agents.set("review", [("write", "review-findings.md", "VERDICT: APPROVED")])
    fake_agents.set("qa", [("write", "qa-report.md", "VERDICT: PASS")])


class TestTopology:
    def test_yosk_pipeline_node_set(self, repo):
        cfg = load_config(Path("pipeline.yaml"))
        registry = default_registry()
        load_extensions(cfg.extensions, registry)
        runtime = Runtime(cfg=cfg, registry=registry, llm=build_llm(cfg.llm),
                          agents_dir=repo / "sdk_agents", state_dir=repo / ".pr",
                          workspace=repo)
        nodes = set(build_graph(runtime).get_graph().nodes)
        assert {"dev", "check", "review", "port_sweep", "qa", "commit",
                "bump", "success"} <= nodes

    def test_unknown_action_fails_at_build(self, repo):
        (repo / "bad.yaml").write_text(YOSK_YAML.replace(
            "action: kill_listeners", "action: no_such_action"))
        cfg = load_config(Path("bad.yaml"))
        runtime = Runtime(cfg=cfg, registry=default_registry(),
                          llm=build_llm(cfg.llm), agents_dir=repo / "sdk_agents",
                          state_dir=repo / ".pr", workspace=repo)
        with pytest.raises(ValueError, match="no_such_action.*port_sweep|port_sweep.*no_such_action"):
            build_graph(runtime)


class TestRunPipeline:
    def test_happy_path_commits(self, repo, fake_agents):
        script_all_pass(fake_agents)
        ok, attempts = run_pipeline("pipeline.yaml", args())
        assert (ok, attempts) == (True, 1)
        assert fake_agents.agents_called() == ["dev", "check", "review", "qa"]
        assert git(repo, "log", "-1", "--pretty=%s") == \
            "feat: construct plan plan.md (agent dev loop)"
        (dev_msg,) = fake_agents.messages_for("dev")
        assert "THE PLAN" in dev_msg and "STANDARDS" in dev_msg
        assert "You are working on plan plan.md." in dev_msg

    def test_test_fail_retries_from_dev(self, repo, fake_agents):
        script_all_pass(fake_agents)
        fake_agents.set("check", [
            ("write", "ci-fix.md", "broken build\nVERDICT: FAIL"),
            ("write", "ci-fix.md", "VERDICT: PASS"),
        ])
        ok, attempts = run_pipeline("pipeline.yaml", args())
        assert (ok, attempts) == (True, 2)
        assert fake_agents.agents_called() == \
            ["dev", "check", "dev", "check", "review", "qa"]
        second_dev = fake_agents.messages_for("dev")[1]
        assert "broken build" in second_dev  # fail note reached the next attempt

    def test_exhaustion_fails(self, repo, fake_agents):
        fake_agents.set("check", [("write", "ci-fix.md", "VERDICT: FAIL")])
        ok, attempts = run_pipeline("pipeline.yaml", args())
        assert (ok, attempts) == (False, 3)
        assert fake_agents.agents_called() == ["dev", "check"] * 3
        assert git(repo, "log", "-1", "--pretty=%s") == "init"  # no commit

    def test_max_attempts_cli_override(self, repo, fake_agents):
        fake_agents.set("check", [("write", "ci-fix.md", "VERDICT: FAIL")])
        ok, attempts = run_pipeline("pipeline.yaml", args(max_attempts=1))
        assert (ok, attempts) == (False, 1)
        assert fake_agents.agents_called() == ["dev", "check"]

    def test_agent_exception_fails_run(self, repo, fake_agents):
        script_all_pass(fake_agents)
        fake_agents.set("review", [("raise",)])
        ok, attempts = run_pipeline("pipeline.yaml", args())
        assert (ok, attempts) == (False, 1)
        assert fake_agents.agents_called() == ["dev", "check", "review"]
        assert git(repo, "log", "-1", "--pretty=%s") == "init"

    def test_unclear_verdict_retries_with_content(self, repo, fake_agents):
        script_all_pass(fake_agents)
        fake_agents.set("check", [
            ("write", "ci-fix.md", "undecided prose"),
            ("write", "ci-fix.md", "VERDICT: PASS"),
        ])
        ok, attempts = run_pipeline("pipeline.yaml", args())
        assert (ok, attempts) == (True, 2)
        second_dev = fake_agents.messages_for("dev")[1]
        assert "unparseable" in second_dev and "undecided prose" in second_dev

    def test_stale_artifact_deleted_between_attempts(self, repo, fake_agents):
        script_all_pass(fake_agents)
        fake_agents.set("check", [
            ("write", "ci-fix.md", "VERDICT: FAIL"),
            ("ok",),  # writes nothing — must be unclear, not a stale FAIL re-read
            ("write", "ci-fix.md", "VERDICT: PASS"),
        ])
        ok, attempts = run_pipeline("pipeline.yaml", args())
        assert (ok, attempts) == (True, 3)
        third_dev = fake_agents.messages_for("dev")[2]
        assert "did not write `.pr/ci-fix.md` on attempt 2" in third_dev

    def test_dirty_worktree_at_start_skips_commit(self, repo, fake_agents):
        (repo / "dirty.txt").write_text("not mine")
        script_all_pass(fake_agents)
        ok, attempts = run_pipeline("pipeline.yaml", args())
        assert (ok, attempts) == (True, 1)
        assert git(repo, "log", "-1", "--pretty=%s") == "init"
        assert git(repo, "status", "--porcelain")  # dirty file untouched

    def test_missing_additional_file_fails_fast(self, repo, fake_agents):
        (repo / "coding-standards-ddd.yaml").unlink()
        with pytest.raises(FileNotFoundError, match="coding-standards-ddd.yaml"):
            run_pipeline("pipeline.yaml", args())
        assert fake_agents.calls == []

    def test_empty_loader_docs_fail_fast(self, repo, fake_agents):
        (repo / "empty.yaml").write_text(YOSK_YAML.replace(
            "agent_engine.extensions.aidlc:AidlcExtension",
            "sample_ext:EmptyLoaderExtension"))
        with pytest.raises(RuntimeError, match="empty"):
            run_pipeline("empty.yaml", args(empty=True, plan=None))
        assert fake_agents.calls == []


class TestCommandStep:
    def _write(self, repo: Path, text: str) -> None:
        (repo / "commandstage.yaml").write_text(text)
        git(repo, "add", "-A")
        git(repo, "commit", "-m", "add command stage")

    def test_dev_writes_marker_then_test_passes(self, repo, fake_agents):
        self._write(repo, COMMAND_STAGE_YAML)
        fake_agents.set("dev", [("write", "fix.marker", "")])
        ok, attempts = run_pipeline("commandstage.yaml", args())
        assert (ok, attempts) == (True, 1)
        assert fake_agents.agents_called() == ["dev"]
        assert git(repo, "log", "-1", "--pretty=%s") == \
            "feat: construct plan plan.md (agent dev loop)"

    def test_test_fail_retries_from_dev(self, repo, fake_agents):
        self._write(repo, COMMAND_STAGE_YAML)
        fake_agents.set("dev", [("ok",), ("write", "fix.marker", "")])
        ok, attempts = run_pipeline("commandstage.yaml", args())
        assert (ok, attempts) == (True, 2)
        assert fake_agents.agents_called() == ["dev", "dev"]
        second_dev = fake_agents.messages_for("dev")[1]
        assert "test output" in second_dev and "attempt 1" in second_dev

    def test_timeout_exhausts_run_and_kills_process_group(self, repo,
                                                          fake_agents):
        yaml = COMMAND_STAGE_YAML.replace(
            "    command: python -c \"import sys; import pathlib; print('test output'); sys.exit(0 if pathlib.Path('.pr/fix.marker').exists() else 1)\"",
            "    command: sleep 3\n    timeout: 0.2")
        self._write(repo, yaml)
        fake_agents.set("dev", [("write", "fix.marker", "")])
        start = time.monotonic()
        ok, attempts = run_pipeline("commandstage.yaml", args())
        elapsed = time.monotonic() - start
        assert (ok, attempts) == (False, 3)
        assert fake_agents.agents_called() == ["dev"] * 3
        assert all("timed out" in m for m in fake_agents.messages_for("dev")[1:])
        assert elapsed < 5.0  # killpg cut the 3s sleeps short

    def test_fail_forever_with_cli_max_attempts(self, repo, fake_agents):
        yaml = COMMAND_STAGE_YAML.replace(
            "sys.exit(0 if pathlib.Path('.pr/fix.marker').exists() else 1)",
            "sys.exit(1)")
        self._write(repo, yaml)
        fake_agents.set("dev", [("write", "fix.marker", "")])
        ok, attempts = run_pipeline("commandstage.yaml", args(max_attempts=2))
        assert (ok, attempts) == (False, 2)
        assert fake_agents.agents_called() == ["dev"] * 2
        assert git(repo, "log", "-1", "--pretty=%s") == "add command stage"


class TestResume:
    def sole_thread_id(self, repo) -> str:
        db = repo / ".pr" / "loop-checkpoints.sqlite"
        with sqlite3.connect(db) as conn:
            (tid,) = conn.execute("SELECT DISTINCT thread_id FROM checkpoints").fetchone()
        return tid

    def test_resume_from_crash(self, repo, fake_agents):
        script_all_pass(fake_agents)
        fake_agents.set("review", [
            ("crash",),  # process death mid-run (escapes the graph)
            ("write", "review-findings.md", "VERDICT: APPROVED"),
        ])
        with pytest.raises(KeyboardInterrupt):
            run_pipeline("pipeline.yaml", args())

        ok, attempts = run_pipeline(
            "pipeline.yaml", args(plan=None, resume=self.sole_thread_id(repo)))
        assert (ok, attempts) == (True, 1)
        # dev and test completed before the crash — only review onward re-ran
        assert fake_agents.agents_called() == \
            ["dev", "check", "review", "review", "qa"]
        assert git(repo, "log", "-1", "--pretty=%s") == \
            "feat: construct plan plan.md (agent dev loop)"

    def test_resume_unknown_thread_fails(self, repo):
        run_pipeline_args = args(plan=None, resume="no-such-thread")
        with pytest.raises(ValueError, match="no-such-thread"):
            run_pipeline("pipeline.yaml", run_pipeline_args)


def drain_events(bus: VizBus) -> list[dict]:
    q = bus.subscribe()
    events = []
    while True:
        try:
            events.append(q.get_nowait())
        except queue.Empty:
            return events


class TestVizStream:
    def test_programmatic_bus_never_sweeps(self, repo, fake_agents, monkeypatch):
        script_all_pass(fake_agents)
        swept = []
        monkeypatch.setattr("agent_engine.graph.kill_listeners_on_port",
                            lambda *a, **k: swept.append(a))
        ok, attempts = run_pipeline("pipeline.yaml", args(), viz_bus=VizBus())
        assert (ok, attempts) == (True, 1)
        assert swept == []

    def test_stream_path_matches_invoke(self, repo, fake_agents):
        script_all_pass(fake_agents)
        bus = VizBus()
        ok, attempts = run_pipeline("pipeline.yaml", args(), viz_bus=bus)
        assert (ok, attempts) == (True, 1)
        events = drain_events(bus)
        assert [e["type"] for e in events][0] == "run_started"
        assert [e["type"] for e in events][-1] == "run_finished"
        started = [e["node"] for e in events if e["type"] == "node_started"]
        assert started == ["dev", "check", "review", "port_sweep", "qa",
                           "commit", "success"]
        assert events[0]["subject"] == "plan plan.md"
        assert events[0]["max_attempts"] == 3
        assert events[-1]["success"] is True
        assert events[-1]["attempts"] == 1

    def test_stream_path_failure_returns_same(self, repo, fake_agents):
        fake_agents.set("check", [("write", "ci-fix.md", "VERDICT: FAIL")])
        bus = VizBus()
        ok, attempts = run_pipeline("pipeline.yaml", args(), viz_bus=bus)
        assert (ok, attempts) == (False, 3)
        events = drain_events(bus)
        assert events[-1]["type"] == "run_finished"
        assert events[-1]["success"] is False
        assert events[-1]["attempts"] == 3

    def test_stream_path_captures_node_console(self, repo, fake_agents):
        script_all_pass(fake_agents)
        bus = VizBus()
        ok, attempts = run_pipeline("pipeline.yaml", args(), viz_bus=bus)
        assert (ok, attempts) == (True, 1)
        events = drain_events(bus)
        dev_console = [e for e in events if e["type"] == "console"
                       and "Running dev agent..." in e["text"]]
        assert dev_console
        assert all(e["node"] == "dev" for e in dev_console)
        assert all(e["stream"] == "stdout" for e in dev_console)

    def test_resume_via_stream_continues(self, repo, fake_agents):
        script_all_pass(fake_agents)
        fake_agents.set("review", [
            ("crash",),  # process death mid-run (escapes the stream)
            ("write", "review-findings.md", "VERDICT: APPROVED"),
        ])
        with pytest.raises(KeyboardInterrupt):
            run_pipeline("pipeline.yaml", args(), viz_bus=VizBus())

        db = repo / ".pr" / "loop-checkpoints.sqlite"
        with sqlite3.connect(db) as conn:
            (tid,) = conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints").fetchone()

        ok, attempts = run_pipeline(
            "pipeline.yaml", args(plan=None, resume=tid), viz_bus=VizBus())
        assert (ok, attempts) == (True, 1)
        assert fake_agents.agents_called() == \
            ["dev", "check", "review", "review", "qa"]

"""CLI tests — two-phase argparse: the pipeline YAML determines which
extension flags exist (a loader's flag appears only when its extension is
listed in the pipeline's `extensions:`). Pipeline runs are real; FakeAgents
stubs only the SDK network boundary."""

import sqlite3
import subprocess
from pathlib import Path

import pytest

from agent_engine.cli import build_parser, main

PLAIN_YAML = """\
name: tiny
llm:
  model: openai/deepseek-v4-pro
  base_url: https://api.deepseek.com
  api_key_env: TEST_LLM_KEY
agents_dir: sdk_agents
steps:
  - name: dev
    agent: dev
    produces: implementation-summary.md
    on_pass: success
"""

RESUME_YAML = """\
name: tiny-resume
llm:
  model: openai/deepseek-v4-pro
  base_url: https://api.deepseek.com
  api_key_env: TEST_LLM_KEY
agents_dir: sdk_agents
steps:
  - name: dev
    agent: dev
    produces: implementation-summary.md
    on_pass: checks
  - name: checks
    agent: checks
    artifact: ci-fix.md
    verdicts: { pass: PASS, fail: FAIL }
    on_pass: success
    on_fail: failure
"""

RETRY_YAML = """\
name: tiny-retry
llm:
  model: openai/deepseek-v4-pro
  base_url: https://api.deepseek.com
  api_key_env: TEST_LLM_KEY
max_attempts: 1
agents_dir: sdk_agents
steps:
  - name: dev
    agent: dev
    produces: implementation-summary.md
    on_pass: checks
  - name: checks
    agent: checks
    artifact: ci-fix.md
    verdicts: { pass: PASS, fail: FAIL }
    on_pass: success
    on_fail: { goto: dev, retry: true }
"""


def with_extensions(yaml_text: str, *refs: str) -> str:
    block = "extensions:\n" + "".join(f"  - {r}\n" for r in refs)
    return block + yaml_text


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repo with the plain pipeline + a plan doc."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pipeline.yaml").write_text(PLAIN_YAML)
    (repo / "plan.md").write_text("THE PLAN")
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "init")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("TEST_LLM_KEY", "sk-test")
    return repo


def write_pipeline(repo: Path, name: str, text: str) -> str:
    (repo / name).write_text(text)
    return name


class TestHelp:
    def test_core_and_builtin_loader_flags(self, repo, capsys):
        with pytest.raises(SystemExit) as e:
            main(["pipeline.yaml", "--help"])
        assert e.value.code == 0
        out = capsys.readouterr().out
        assert "--resume" in out
        assert "--max-attempts" in out
        assert "--viz" in out
        assert "--viz-port" in out
        assert "--plan" in out  # built-in plan loader is always present

    def test_extension_flags_only_when_configured(self, repo, capsys):
        write_pipeline(repo, "aidlc.yaml", with_extensions(
            PLAIN_YAML, "agent_engine.extensions.aidlc:AidlcExtension"))
        with pytest.raises(SystemExit) as e:
            main(["aidlc.yaml", "--help"])
        assert e.value.code == 0
        assert "--ai-dlc-unit" in capsys.readouterr().out

        with pytest.raises(SystemExit):
            main(["pipeline.yaml", "--help"])
        assert "--ai-dlc-unit" not in capsys.readouterr().out

    def test_no_pipeline_shows_core_surface(self, repo, capsys):
        with pytest.raises(SystemExit) as e:
            main(["--help"])
        assert e.value.code == 0
        assert "--resume" in capsys.readouterr().out


class TestRun:
    def test_success_returns_zero(self, repo, fake_agents):
        fake_agents.set("dev", [("write", "implementation-summary.md", "done")])
        assert main(["pipeline.yaml", "--plan", "plan.md"]) == 0

    def test_failure_returns_one(self, repo, fake_agents):
        write_pipeline(repo, "retry.yaml", RETRY_YAML)
        fake_agents.set("dev", [("write", "implementation-summary.md", "done")])
        fake_agents.set("checks", [("write", "ci-fix.md", "VERDICT: FAIL")])
        assert main(["retry.yaml", "--plan", "plan.md"]) == 1

    def test_max_attempts_overrides_config(self, repo, fake_agents):
        write_pipeline(repo, "retry.yaml", RETRY_YAML)  # YAML says max_attempts: 1
        fake_agents.set("dev", [("write", "implementation-summary.md", "done")])
        fake_agents.set("checks", [("write", "ci-fix.md", "VERDICT: FAIL")])
        assert main(["retry.yaml", "--plan", "plan.md",
                     "--max-attempts", "2"]) == 1
        assert fake_agents.agents_called().count("dev") == 2

    def test_resume_threads_through(self, repo, fake_agents):
        write_pipeline(repo, "resume.yaml", RESUME_YAML)
        fake_agents.set("dev", [("write", "implementation-summary.md", "done")])
        fake_agents.set("checks", [
            ("crash",),  # process death mid-run
            ("write", "ci-fix.md", "VERDICT: PASS"),
        ])
        with pytest.raises(KeyboardInterrupt):
            main(["resume.yaml", "--plan", "plan.md"])

        db = repo / ".pr" / "loop-checkpoints.sqlite"
        with sqlite3.connect(db) as conn:
            (tid,) = conn.execute(
                "SELECT DISTINCT thread_id FROM checkpoints").fetchone()

        assert main(["resume.yaml", "--resume", tid]) == 0
        # dev completed before the crash — only checks re-ran on resume
        assert fake_agents.agents_called() == ["dev", "checks", "checks"]


class TestViz:
    def test_viz_flags_parse(self, repo):
        args = build_parser("pipeline.yaml").parse_args(
            ["pipeline.yaml", "--viz", "--viz-port", "9"])
        assert args.viz is True
        assert args.viz_port == 9

    def test_lifecycle_serves_and_keeps_alive(self, repo, fake_agents, monkeypatch):
        import queue

        fake_agents.set("dev", [("write", "implementation-summary.md", "done")])
        captured = {}

        def fake_serve_viz(bus, topology, subject, port):
            captured["bus"] = bus
            captured["topology"] = topology
            captured["subject"] = subject
            captured["port"] = port
            return object(), object()

        def interrupt():
            raise KeyboardInterrupt

        monkeypatch.setattr("agent_engine.viz.serve_viz", fake_serve_viz)
        opened = []
        monkeypatch.setattr("webbrowser.open", opened.append)
        monkeypatch.setattr("agent_engine.viz.wait_for_interrupt", interrupt)

        code = main(["pipeline.yaml", "--plan", "plan.md", "--viz"])
        assert code == 0
        assert "dev" in captured["topology"]
        assert "success" in captured["topology"]
        assert captured["subject"] == "plan plan.md"
        assert captured["port"] == 8321
        assert opened == ["http://127.0.0.1:8321"]

        events = []
        q = captured["bus"].subscribe()
        while True:
            try:
                events.append(q.get_nowait())
            except queue.Empty:
                break
        assert any(e["type"] == "run_started" for e in events)
        assert any(e["type"] == "run_finished" for e in events)

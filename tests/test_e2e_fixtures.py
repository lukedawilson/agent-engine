"""Historical-fixture e2e: the failures that shaped the dev loop's policies,
replayed against the SHIPPED example pipeline (examples/self/) —
a byte-identical copy per test, so state_dir, agents_dir and additional_files
resolve exactly as they would in a consumer's repo.

run_agent is stubbed (the SDK network boundary, via the fake_agents fixture);
files, git, checkpoints, verdict parsing and routing are all real. The
example's verbatim port sweep (port 8321, match "agent-engine") is
neutralized at the OS boundary (_listening_pids) because a contributor's
real process may be listening on that port — kill behavior itself is covered
in test_actions.py.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from agent_engine.agents import load_agent
from agent_engine.cli import main
from agent_engine.config import load_config
from agent_engine.llm import build_llm
from agent_engine.registry import default_registry

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "self"


def _passing_scripts(fake_agents, **overrides):
    scripts = {
        "dev": [("ok",)],
        "checks": [("write", "ci-fix.md", "All green.\n\nVERDICT: PASS\n")],
        "review": [("write", "review-findings.md",
                    "Looks good.\n\nVERDICT: APPROVED\n")],
        "qa": [("write", "qa-report.md", "All good.\n\nVERDICT: PASS\n")],
    }
    scripts.update(overrides)
    for agent, behaviors in scripts.items():
        fake_agents.set(agent, behaviors)


@pytest.fixture
def consumer_repo(tmp_path, monkeypatch, fake_agents):
    """Byte-identical copy of the shipped example as a clean git repo,
    laid out like the real repo (README at the root, pipeline under
    examples/self/) so additional_files (../../README.md), state_dir and
    agents_dir all resolve exactly as they would in a consumer's repo."""
    repo = tmp_path / "repo"
    (repo / "examples" / "self").mkdir(parents=True)
    # .pr is the pipeline's gitignored build-artifact dir. It must NOT ride
    # into the "shipped example" copy — a prior real run can leave stale
    # artifacts there, and committing them would flip commit_allowed to False
    # once clear_attempt_artifacts deletes the produced files.
    shutil.copytree(EXAMPLE, repo / "examples" / "self", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".pr"))
    (repo / "README.md").write_text("# README\n")
    monkeypatch.chdir(repo)
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "config", "user.name", "T"], check=True)
    (repo / "plan.md").write_text("# Plan\n\nBuild the thing.\n")
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-qm", "init"], check=True)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    # Never kill a contributor's real process on that port (see module
    # docstring).
    monkeypatch.setattr("agent_engine.actions._listening_pids",
                        lambda *a, **k: [])
    return repo


def _log(repo: Path) -> str:
    return subprocess.run(["git", "log", "--oneline"], cwd=repo,
                          capture_output=True, text=True, check=True).stdout


class TestHistoricalFixtures:
    def test_run004_decorated_verdict_still_passes(self, consumer_repo,
                                                   fake_agents):
        """QA run 004 burned 3 attempts on `**VERDICT: PASS**` — markdown
        decoration around the verdict line. The tolerant parser (LAST
        VERDICT line wins) must route this as a pass, not an unclear retry."""
        _passing_scripts(fake_agents, checks=[
            ("write", "ci-fix.md",
             "## CI analysis\n\nEverything is fine.\n\n**VERDICT: PASS**\n")])
        rc = main([str(consumer_repo / "examples" / "self" / "pipeline.yaml"), "--plan", "plan.md", "--no-viz"])
        assert rc == 0
        assert fake_agents.agents_called() == ["dev", "checks", "review", "qa"]
        assert "feat: construct plan plan.md (agent dev loop)" in _log(
            consumer_repo)

    def test_stale_artifact_is_deleted_between_attempts(self, consumer_repo,
                                                        fake_agents):
        """A stale artifact from attempt N must be deleted before attempt N+1
        runs — otherwise the verdict stage re-reads the previous file and the
        loop retries against ghosts. The pin: attempt 2's note must be the
        missing-artifact one, proving the stale FAIL was gone."""
        _passing_scripts(fake_agents, checks=[
            ("write", "ci-fix.md", "STALE findings\n\nVERDICT: FAIL\n"),
            ("ok",),  # attempt 2 writes nothing
            ("write", "ci-fix.md", "Fixed.\n\nVERDICT: PASS\n"),
        ])
        rc = main([str(consumer_repo / "examples" / "self" / "pipeline.yaml"), "--plan", "plan.md", "--no-viz"])
        assert rc == 0
        attempt3_checks = fake_agents.messages_for("checks")[-1]
        assert ("checks agent did not write `examples/self/.pr/ci-fix.md` "
                "on attempt 2." in attempt3_checks)
        assert "checks output (attempt 2)" not in attempt3_checks

    def test_verdict_written_before_turn_cap_still_passes(self, consumer_repo,
                                                          fake_agents):
        """Verdict-first truncation: a clear verdict stands even when the run
        was cut short (turn cap / stuck detection) before the agent formally
        finished — the artifact on disk is the source of truth."""
        _passing_scripts(fake_agents, qa=[
            ("write_truncated", "qa-report.md",
             "Partial QA findings, cut short.\n\nVERDICT: PASS\n")])
        rc = main([str(consumer_repo / "examples" / "self" / "pipeline.yaml"), "--plan", "plan.md", "--no-viz"])
        assert rc == 0
        assert fake_agents.agents_called().count("qa") == 1
        assert "(agent dev loop)" in _log(consumer_repo)

    def test_unclear_verdict_retries_with_content_in_notes(self, consumer_repo,
                                                           fake_agents):
        """An unparseable verdict forces an attempt-bounded retry, and the
        artifact's content rides into the next attempt's notes — findings
        are never swallowed."""
        _passing_scripts(fake_agents, checks=[
            ("write", "ci-fix.md",
             "The build looks mostly fine but I cannot decide.\n"
             "Line two of findings.\n"),
            ("write", "ci-fix.md", "Decided.\n\nVERDICT: PASS\n"),
        ])
        rc = main([str(consumer_repo / "examples" / "self" / "pipeline.yaml"), "--plan", "plan.md", "--no-viz"])
        assert rc == 0
        attempt2_dev = fake_agents.messages_for("dev")[1]
        assert "unparseable" in attempt2_dev
        assert "I cannot decide" in attempt2_dev

    def test_dirty_worktree_at_start_skips_commit_but_run_succeeds(
            self, consumer_repo, fake_agents):
        """Run 004: the dev agent's commit swept up an unrelated edit. Now the
        single commit point only fires when the worktree was clean at start —
        a dirty-at-start run still succeeds, it just doesn't commit."""
        (consumer_repo / "plan.md").write_text("# Plan\n\nEdited by a human.\n")
        _passing_scripts(fake_agents)
        rc = main([str(consumer_repo / "examples" / "self" / "pipeline.yaml"), "--plan", "plan.md", "--no-viz"])
        assert rc == 0
        assert "(agent dev loop)" not in _log(consumer_repo)

    def test_empty_unit_dir_fails_fast(self, consumer_repo, fake_agents):
        """U3 (2026-07-19): an empty unit dir silently degraded to
        inception-only context the agents couldn't act on. Fail fast."""
        (consumer_repo / "aidlc-docs" / "construction"
         / "unit-99").mkdir(parents=True)
        with pytest.raises(RuntimeError, match="yielded no docs"):
            main([str(consumer_repo / "examples" / "self" / "pipeline.yaml"),
                  "--ai-dlc-unit", "U99", "--no-viz"])
        assert fake_agents.calls == []


class TestExampleExtensionless:
    def test_example_dev_agent_builds_with_bundled_registry(self, monkeypatch):
        """The example's agents name only bundled tools — the dev agent
        builds against the default registry with no consumer extensions.
        (Real SDK factory, fake-key LLM — no network.)"""
        registry = default_registry()
        cfg = load_config(EXAMPLE / "pipeline.yaml")
        agent = load_agent(EXAMPLE / "sdk_agents", "dev", build_llm(cfg.llm))
        assert agent is not None

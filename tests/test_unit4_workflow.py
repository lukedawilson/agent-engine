"""Unit-4 workflow-mode helpers — clean-at-start, the docker-free commit
shim, the project CLI, and the wheel-shipped skill install."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agentic_dev_loop.core import clean_at_start_flag
from agentic_dev_loop.engine.commit_shim import run_commit
from agentic_dev_loop.workflow import SKILL_MD, install_skill, skill_dir

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── clean_at_start_flag ─────────────────────────────────────────────────

def test_clean_at_start_flag_empty_porcelain_is_clean():
    assert clean_at_start_flag("") is True
    assert clean_at_start_flag("   \n  ") is True


def test_clean_at_start_flag_dirty():
    assert clean_at_start_flag("M src/foo.py\n?? bar.txt") is False


# ── commit shim ─────────────────────────────────────────────────────────

def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"],
                   cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"],
                   cwd=path, check=True)
    (path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True,
                   capture_output=True)


def test_commit_shim_refuses_when_not_allowed(capsys):
    assert run_commit("feat: {subject}", "unit-4", False) == 1
    assert "Refusing to commit" in capsys.readouterr().err


def test_commit_shim_requires_message():
    with pytest.raises(ValueError):
        run_commit("", "unit-4", True)


def test_commit_shim_commits_when_allowed(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "work.txt").write_text("constructed")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    assert run_commit("feat: construct {subject}", "unit-4", True) == 0
    log = subprocess.run(["git", "log", "--oneline"], cwd=repo, check=True,
                         capture_output=True, text=True).stdout
    assert "feat: construct unit-4" in log


# ── skill install ───────────────────────────────────────────────────────

def test_install_skill_writes_skill_payload(tmp_path):
    target = tmp_path / "skill"
    install_skill(target)
    assert (target / "SKILL.md").read_text() == SKILL_MD
    assert (target / "workflow.js.template").read_text()
    assert (target / "VERSION").read_text()


def test_install_skill_is_idempotent(tmp_path):
    target = tmp_path / "skill"
    install_skill(target)
    first = (target / "SKILL.md").read_text()
    install_skill(target)
    assert (target / "SKILL.md").read_text() == first


def test_skill_dir_default_target():
    assert skill_dir().name == "agentic-dev-loop"


# ── project CLI ─────────────────────────────────────────────────────────

def test_project_cli_writes_workflow_js(tmp_path, monkeypatch):
    # Build a tiny pipeline + agent prompt in a temp dir, then run the
    # `python -m agentic_dev_loop.core.project` entry point.
    base = tmp_path / "proj"
    agents = base / "agents"
    agents.mkdir(parents=True)
    (agents / "dev.agent.md").write_text("# dev\n")
    (base / "pipeline.yaml").write_text(
        "name: mini\n"
        "llm: {model: m, base_url: http://x, api_key_env: K}\n"
        "agents_dir: agents\n"
        "max_attempts: 5\n"
        "steps:\n"
        "  - name: dev\n"
        "    agent: dev\n"
        "    on_pass: success\n",
    )
    out = subprocess.run(
        [__import__("sys").executable, "-m", "agentic_dev_loop.core.project",
         str(base / "pipeline.yaml")],
        capture_output=True, text=True, cwd=REPO_ROOT)
    assert out.returncode == 0, out.stderr
    js = (base / ".agentic-dev-loop" / "workflow.js").read_text()
    assert "mini" in js
    assert "dev.agent.md" in js


def test_project_cli_fails_loud_on_missing_prompt(tmp_path):
    base = tmp_path / "proj"
    agents = base / "agents"
    agents.mkdir(parents=True)
    (base / "pipeline.yaml").write_text(
        "name: mini\n"
        "llm: {model: m, base_url: http://x, api_key_env: K}\n"
        "agents_dir: agents\n"
        "steps:\n"
        "  - name: dev\n"
        "    agent: dev\n"
        "    on_pass: success\n",
    )
    out = subprocess.run(
        [__import__("sys").executable, "-m", "agentic_dev_loop.core.project",
         str(base / "pipeline.yaml")],
        capture_output=True, text=True, cwd=REPO_ROOT)
    assert out.returncode != 0
    assert "dev.agent.md" in out.stderr

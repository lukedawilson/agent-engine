"""Pipeline-level secrets tests (019): the run refuses a secret-bearing
workspace, injects a declared secret only into the declaring step's exec env,
and scrubs the value from every captured output channel. No Docker — the
``fake_sandbox`` / ``fake_agents`` fixtures stand in for the SDK/Docker
boundaries (the only permitted stubs)."""
from __future__ import annotations

import argparse
import os

import pytest

from agentic_dev_loop.engine.graph import run_pipeline
from agentic_dev_loop.engine.secrets import SecretResolutionError

SECRET_YAML = """\
name: secret-probe
llm:
  model: m
  api_key_env: TEST_LLM_KEY
agents_dir: agents
deps_policy: open
secrets:
  probe-secret:
    from: env
    key: TEST_SECRET_VAR
steps:
  - name: probe
    command: printenv TEST_SECRET_VAR
    secrets: [probe-secret]
    network: true
    on_pass: success
"""

BAN_YAML = """\
name: ban-probe
llm:
  model: m
  api_key_env: TEST_LLM_KEY
agents_dir: agents
deps_policy: open
steps:
  - name: dev
    agent: dev
    on_pass: success
"""


def _args(**over):
    base = {"plan": None, "resume": None, "max_attempts": None,
            "refresh": False, "no_viz": True}
    base.update(over)
    return argparse.Namespace(**base)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pipeline.yaml").write_text(SECRET_YAML)
    agents = repo / "agents"
    agents.mkdir()
    (agents / "dev.agent.md").write_text(
        "---\nname: dev\ntools: [terminal]\n---\nYou are the dev agent.\n")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("TEST_LLM_KEY", "sk-test")
    return repo


def test_secret_injected_only_into_declaring_step(repo, fake_sandbox, capsys):
    # set the host env value the env provider reads
    os.environ["TEST_SECRET_VAR"] = "sup3r-secret-value"
    try:
        ok, attempts = run_pipeline("pipeline.yaml", _args())
    finally:
        os.environ.pop("TEST_SECRET_VAR", None)
    assert (ok, attempts) == (True, 1)
    # the declaring step's exec env carried the secret
    assert fake_sandbox.requests[0].env["TEST_SECRET_VAR"] == "sup3r-secret-value"
    assert fake_sandbox.requests[0].network is True
    # the value was scrubbed from the printed console output (a capture path)
    out = capsys.readouterr().out
    assert "sup3r-secret-value" not in out
    assert "[REDACTED]" in out


def test_env_ban_refuses_run(repo, monkeypatch):
    (repo / "pipeline.yaml").write_text(BAN_YAML)
    (repo / ".env").write_text("TEST_LLM_KEY=sk-in-file\n")
    with pytest.raises(SecretResolutionError, match=".env"):
        run_pipeline("pipeline.yaml", _args())


def test_env_ban_whitelists_convention_fixture(repo, fake_sandbox, fake_agents):
    (repo / "pipeline.yaml").write_text(BAN_YAML)
    (repo / ".env.example").write_text("TEST_LLM_KEY=placeholder\n")
    fake_agents.set("dev", [("respond", "done")])
    ok, _ = run_pipeline("pipeline.yaml", _args())
    assert ok is True


def test_missing_secret_ref_fails_fast_names_step(repo):
    os.environ.pop("TEST_SECRET_VAR", None)
    with pytest.raises(SecretResolutionError) as e:
        run_pipeline("pipeline.yaml", _args())
    assert "probe-secret" in str(e.value)
    assert "['probe']" in str(e.value)
    assert "TEST_SECRET_VAR" in str(e.value)

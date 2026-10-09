from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from agent_engine.config import Route, load_config

# The plan's yosk-equivalent reference pipeline (009, YAML schema section),
# verbatim. This is the canonical pin: the documented schema must load.
FULL_YAML = """\
name: yosk-construction

extensions:
  - agent_engine.extensions.aidlc:AidlcExtension

additional_files:
  - coding-standards-ddd.yaml

llm:
  model: openai/deepseek-v4-pro
  base_url: https://api.deepseek.com
  api_key_env: OPENAI_API_KEY
  extra_body: { chat_template_kwargs: { thinking: false } }

state_dir: .pr
max_attempts: 3
agents_dir: sdk_agents

steps:
  - name: dev
    agent: dev
    produces: implementation-summary.md
    on_pass: test

  - name: test
    agent: test
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
    params: { port: 8080, match: Yosk }
    on_pass: qa

  - name: qa
    agent: qa
    artifact: qa-report.md
    verdicts: { pass: PASS, fail: FAIL }
    max_iterations: 200
    on_pass: commit
    on_fail: { goto: dev, retry: true }

  - name: commit
    action: commit
    params: { message: "feat: construct {subject} (agent dev loop)" }
    on_pass: success
"""


def _base() -> dict:
    return {
        "name": "test-pipeline",
        "llm": {"model": "m", "api_key_env": "K"},
        "agents_dir": "sdk_agents",
        "steps": [{"name": "dev", "agent": "dev", "on_pass": "success"}],
    }


def _load(tmp_path: Path, data):
    p = tmp_path / "pipeline.yaml"
    p.write_text(yaml.safe_dump(data))
    return load_config(p)


def test_full_schema_example_round_trips(tmp_path):
    p = tmp_path / "pipeline.yaml"
    p.write_text(FULL_YAML)
    cfg = load_config(p)

    assert cfg.name == "yosk-construction"
    assert cfg.extensions == ["agent_engine.extensions.aidlc:AidlcExtension"]
    assert cfg.additional_files == ["coding-standards-ddd.yaml"]
    assert cfg.state_dir == ".pr"
    assert cfg.max_attempts == 3
    assert cfg.agents_dir == "sdk_agents"

    assert cfg.llm.model == "openai/deepseek-v4-pro"
    assert cfg.llm.base_url == "https://api.deepseek.com"
    assert cfg.llm.api_key_env == "OPENAI_API_KEY"
    assert cfg.llm.extra_body == {"chat_template_kwargs": {"thinking": False}}
    assert cfg.llm.timeout is None  # opinionated no-timeout default

    dev, test, review, port_sweep, qa, commit = cfg.steps
    assert dev.agent == "dev"
    assert dev.produces == ["implementation-summary.md"]
    assert dev.on_pass == "test"
    assert dev.on_fail is None

    assert test.artifact == "ci-fix.md"
    assert test.verdicts.pass_ == "PASS"
    assert test.verdicts.fail == "FAIL"
    assert test.on_fail == Route(goto="dev", retry=True)

    assert review.verdicts.fail == "NEEDS CHANGES"

    assert port_sweep.action == "kill_listeners"
    assert port_sweep.params == {"port": 8080, "match": "Yosk"}

    assert qa.max_iterations == 200

    assert commit.action == "commit"
    assert commit.params["message"] == "feat: construct {subject} (agent dev loop)"
    assert commit.on_pass == "success"


def test_minimal_config_applies_defaults(tmp_path):
    cfg = _load(tmp_path, _base())
    assert cfg.extensions == []
    assert cfg.additional_files == []
    assert cfg.state_dir == ".pr"
    assert cfg.max_attempts == 3
    step = cfg.steps[0]
    assert step.action is None
    assert step.params == {}
    assert step.produces == []
    assert step.artifact is None
    assert step.verdicts is None
    assert step.max_iterations is None
    assert step.on_fail is None


def test_produces_accepts_a_list(tmp_path):
    data = _base()
    data["steps"][0]["produces"] = ["a.md", "b.md"]
    assert _load(tmp_path, data).steps[0].produces == ["a.md", "b.md"]


def test_unknown_top_level_key_rejected(tmp_path):
    data = _base() | {"bogus": 1}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _load(tmp_path, data)


def test_unknown_step_key_rejected(tmp_path):
    data = _base()
    data["steps"][0]["bogus"] = 1
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _load(tmp_path, data)


def test_unknown_llm_key_rejected(tmp_path):
    data = _base()
    data["llm"]["bogus"] = 1
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _load(tmp_path, data)


def test_unknown_route_key_rejected(tmp_path):
    data = _base()
    data["steps"][0]["on_pass"] = {"goto": "success", "bogus": 1}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _load(tmp_path, data)


def test_unknown_verdicts_key_rejected(tmp_path):
    data = _base()
    data["steps"][0]["artifact"] = "a.md"
    data["steps"][0]["verdicts"] = {"pass": "P", "fail": "F", "bogus": 1}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _load(tmp_path, data)


def test_dangling_on_pass_rejected(tmp_path):
    data = _base()
    data["steps"][0]["on_pass"] = "nope"
    with pytest.raises(ValidationError, match="unknown route target 'nope'"):
        _load(tmp_path, data)


def test_dangling_retry_goto_rejected(tmp_path):
    data = _base()
    data["steps"][0]["on_fail"] = {"goto": "nope", "retry": True}
    with pytest.raises(ValidationError, match="unknown route target 'nope'"):
        _load(tmp_path, data)


def test_terminal_targets_allowed(tmp_path):
    data = _base()
    data["steps"][0]["on_pass"] = "failure"
    assert _load(tmp_path, data).steps[0].on_pass == "failure"


def test_both_agent_and_action_rejected(tmp_path):
    data = _base()
    data["steps"][0]["action"] = "commit"
    with pytest.raises(ValidationError, match="exactly one of 'agent' or 'action'"):
        _load(tmp_path, data)


def test_neither_agent_nor_action_rejected(tmp_path):
    data = _base()
    del data["steps"][0]["agent"]
    with pytest.raises(ValidationError, match="exactly one of 'agent' or 'action'"):
        _load(tmp_path, data)


def test_artifact_without_verdicts_rejected(tmp_path):
    data = _base()
    data["steps"][0]["artifact"] = "a.md"
    with pytest.raises(ValidationError, match="'artifact' and 'verdicts' must appear together"):
        _load(tmp_path, data)


def test_verdicts_without_artifact_rejected(tmp_path):
    data = _base()
    data["steps"][0]["verdicts"] = {"pass": "P", "fail": "F"}
    with pytest.raises(ValidationError, match="'artifact' and 'verdicts' must appear together"):
        _load(tmp_path, data)


def test_produces_and_artifact_mutually_exclusive(tmp_path):
    data = _base()
    data["steps"][0]["produces"] = "a.md"
    data["steps"][0]["artifact"] = "b.md"
    data["steps"][0]["verdicts"] = {"pass": "P", "fail": "F"}
    with pytest.raises(ValidationError, match="mutually exclusive"):
        _load(tmp_path, data)


def test_duplicate_step_names_rejected(tmp_path):
    data = _base()
    data["steps"].append({"name": "dev", "agent": "dev", "on_pass": "success"})
    with pytest.raises(ValidationError, match="duplicate step names"):
        _load(tmp_path, data)


def test_zero_steps_rejected(tmp_path):
    data = _base()
    data["steps"] = []
    with pytest.raises(ValidationError):
        _load(tmp_path, data)


@pytest.mark.parametrize("terminal", ["success", "failure"])
def test_step_named_reserved_terminal_rejected(tmp_path, terminal):
    data = _base()
    data["steps"][0]["name"] = terminal
    data["steps"][0]["on_pass"] = "success"
    with pytest.raises(ValidationError, match="reserved terminal"):
        _load(tmp_path, data)


def test_non_mapping_yaml_rejected(tmp_path):
    p = tmp_path / "pipeline.yaml"
    p.write_text("- just\n- a\n- list\n")
    with pytest.raises(ValueError, match="must be a mapping"):
        load_config(p)

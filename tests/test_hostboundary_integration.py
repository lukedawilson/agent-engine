"""Marked real-Docker integration tests for the host boundary (020): a
consumer action's code runs inside the sandbox and cannot touch the host.
Skip with an explicit reason when no daemon or integration image is present;
never silently skipped in CI."""
from __future__ import annotations

import shutil

import pytest
from openhands.sdk import LLM

from agentic_dev_loop.core.config import IsolationConfig, PipelineConfig
from agentic_dev_loop.engine.isolation import (
    DockerBackend, SandboxError, SubprocessRunner, probe_docker,
    resolve_effective_profile,
)
from agentic_dev_loop.engine.registry import Registry
from agentic_dev_loop.engine.stages import Runtime, make_action_node

pytestmark = pytest.mark.docker

TEST_IMAGE = "python:3.12"


def _docker_available() -> str | None:
    if shutil.which("docker") is None:
        return "docker CLI not on PATH"
    try:
        probe_docker()
    except SandboxError as e:
        return f"docker daemon unavailable: {e}"
    return None


@pytest.fixture
def backend(tmp_path):
    reason = _docker_available()
    if reason is not None:
        pytest.skip(reason)
    inspect = SubprocessRunner().run(
        ["docker", "image", "inspect", TEST_IMAGE, "--format", "{{.Id}}"],
        timeout=30)
    if inspect.exit_code != 0:
        pytest.skip(f"integration image {TEST_IMAGE!r} not present locally")
    ws = tmp_path / "ws"
    ws.mkdir()
    profile = resolve_effective_profile(IsolationConfig(image=TEST_IMAGE))
    b = DockerBackend(image=TEST_IMAGE, workspace=str(ws),
                      iso_state_dir=str(tmp_path / "state"), profile=profile)
    b.ensure_image()
    b.create_execution_container()
    yield b, ws
    b.close()


def _runtime(backend, ws, script, tmp_path):
    reg = Registry()
    reg.add_sandbox_action("probe", script)
    cfg = PipelineConfig.model_validate({
        "name": "probe",
        "llm": {"model": "openai/test-model", "api_key_env": "K"},
        "agents_dir": "agents",
        "steps": [{"name": "probe", "action": "probe", "on_pass": "success"}],
    })
    runtime = Runtime(cfg=cfg, registry=reg,
                      llm=LLM(model="openai/test-model", api_key="sk-test"),
                      agents_dir=tmp_path / "agents", state_dir=tmp_path / "state",
                      workspace=ws, sandbox=backend)
    return runtime, cfg.steps[0]


class TestConsumerActionSentinel:
    def test_action_code_cannot_create_host_file(self, backend, tmp_path):
        b, ws = backend
        sentinel = tmp_path / "host-sentinel.txt"
        script = f'python -c "open({str(sentinel)!r}, \\"w\\").write(\\"pwned\\")"'
        runtime, step = _runtime(b, ws, script, tmp_path)
        node = make_action_node(runtime, step)
        node({"subject": "s", "attempt": 1, "step_verdicts": {}})
        # The action wrote to a path that exists on the host but is not the
        # workspace mount — it landed in the container's own filesystem (or was
        # refused by the read-only rootfs), never on the host.
        assert not sentinel.exists()

    def test_action_can_still_write_inside_workspace(self, backend, tmp_path):
        b, ws = backend
        script = 'python -c "open(\\"in-sandbox.txt\\", \\"w\\").write(\\"ok\\")"'
        runtime, step = _runtime(b, ws, script, tmp_path)
        make_action_node(runtime, step)({"subject": "s", "attempt": 1,
                                         "step_verdicts": {}})
        assert (ws / "in-sandbox.txt").read_text() == "ok"

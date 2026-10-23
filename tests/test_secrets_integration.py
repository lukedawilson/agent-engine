"""Marked real-Docker integration tests for secret injection (019): a resolved
secret travels into the declaring step's exec env, and the host-side audit
trail never records the value. Skips with an explicit reason when no daemon or
integration image is present (CI pre-installs both)."""
from __future__ import annotations

import shutil

import pytest

from agentic_dev_loop.core.config import IsolationConfig
from agentic_dev_loop.engine.isolation import (
    DockerBackend, SandboxExecutionRequest, SandboxError, SubprocessRunner,
    probe_docker, resolve_effective_profile, resolve_sandbox_env,
)

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
    state = tmp_path / "state"
    profile = resolve_effective_profile(IsolationConfig(image=TEST_IMAGE))
    b = DockerBackend(image=TEST_IMAGE, workspace=str(ws),
                      iso_state_dir=str(state), profile=profile)
    b.ensure_image()
    b.create_execution_container()
    yield b, ws, state
    b.close()


class TestSecretInjectionE2E:
    def test_secret_reaches_exec_env_only(self, backend):
        b, ws, state = backend
        env = resolve_sandbox_env(None, secrets={"TEST_SECRET_VAR": "sup3r-secret"})
        req = SandboxExecutionRequest(
            argv=["printenv", "TEST_SECRET_VAR"], cwd=str(ws), env=env,
            pipeline="p", step="probe")
        result = b.run(req)
        assert result.exit_code == 0, result.stderr
        assert "sup3r-secret" in result.stdout

        # the audit trail hashes env keys but never logs values (BR-11 / 019)
        audit = (state / "sandbox-audit.jsonl").read_text()
        assert "sup3r-secret" not in audit
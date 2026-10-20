"""Marked real-Docker integration tests (BR-12.3). Skip with an explicit
reason when no daemon or integration image is present; never silently skipped
in CI (the workflows pre-install Docker and the image)."""
from __future__ import annotations

import shutil

import pytest

from agentic_dev_loop.config import IsolationConfig
from agentic_dev_loop.isolation import (
    DockerBackend, SandboxExecutionRequest, SandboxError,
    SubprocessRunner, probe_docker, read_stamp, resolve_effective_profile,
    write_stamp,
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
    profile = resolve_effective_profile(IsolationConfig(image=TEST_IMAGE))
    b = DockerBackend(image=TEST_IMAGE, workspace=str(ws),
                      iso_state_dir=str(tmp_path / "state"), profile=profile)
    b.ensure_image()
    b.create_execution_container()
    yield b, ws
    b.close()


def _run(backend, argv, **kw):
    ws = backend._workspace
    req = SandboxExecutionRequest(
        argv=argv, cwd=ws,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp"},
        timeout=kw.get("timeout"))
    return backend.run(req)


class TestProbe:
    def test_probe_passes(self):
        reason = _docker_available()
        if reason is not None:
            pytest.skip(reason)
        r = probe_docker()
        assert r.ostype == "linux"
        assert tuple(int(x) for x in r.api_version.split(".")) >= (1, 43)


class TestEcho:
    def test_echo_round_trip(self, backend):
        b, _ws = backend
        result = _run(b, ["echo", "hello-sandbox"])
        assert result.exit_code == 0
        assert "hello-sandbox" in result.stdout


class TestNetworkOff:
    def test_no_external_reachability(self, backend):
        b, _ws = backend
        result = _run(b, ["python", "-c",
                          "import socket; s=socket.socket(); s.settimeout(2); "
                          "s.connect(('1.1.1.1', 80))"])
        assert result.exit_code != 0  # --network none: no route


class TestReadOnlyRootfs:
    def test_rootfs_read_only_mount_writable(self, backend):
        b, ws = backend
        # rootfs is read-only: writing to / fails
        ro = _run(b, ["python", "-c", "open('/readonly-probe','w').write('x')"])
        assert ro.exit_code != 0
        # the workspace mount is writable
        rw = _run(b, ["sh", "-c", "printf x > writable-probe"])
        assert rw.exit_code == 0
        assert (ws / "writable-probe").read_text() == "x"


class TestGitGuardE2E:
    def test_mutation_blocked_before_exec(self, backend):
        b, _ws = backend
        with pytest.raises(SandboxError, match="AE-SBX-008"):
            _run(b, ["git", "commit", "-m", "x"])

    def test_read_runs(self, backend):
        b, _ws = backend
        result = _run(b, ["git", "status"])
        assert not isinstance(result, SandboxError)


class TestNetworkedContainerE2E:
    """014: `network: true` steps run in a second, bridge-network container.
    The distinguishing observable is the interface set — network-none has only
    loopback; the bridge container additionally gets a routable eth0. This is
    deterministic (no external egress required)."""

    @pytest.fixture
    def networked_backend(self, tmp_path):
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
                          iso_state_dir=str(tmp_path / "state"), profile=profile,
                          network=True)
        b.ensure_image()
        b.create_execution_container()
        yield b, ws
        b.close()

    def test_networked_container_has_bridge_interface(self, networked_backend):
        b, ws = networked_backend
        req = SandboxExecutionRequest(
            argv=["python", "-c",
                  "import socket; print(' '.join(sorted(n for _, n in socket.if_nameindex())))"],
            cwd=ws,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp"},
            network=True)
        result = b.run(req)
        assert result.exit_code == 0, result.stderr
        names = result.stdout.split()
        assert "lo" in names
        assert any(name != "lo" for name in names)

    def test_default_container_still_network_none(self, networked_backend):
        b, ws = networked_backend
        req = SandboxExecutionRequest(
            argv=["python", "-c",
                  "import socket; print(' '.join(sorted(n for _, n in socket.if_nameindex())))"],
            cwd=ws,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp"},
            network=False)
        result = b.run(req)
        assert result.exit_code == 0, result.stderr
        assert result.stdout.split() == ["lo"]


class TestProvisionE2E:
    def test_provision_stamp_skip_refresh(self, backend, tmp_path):
        b, ws = backend
        stamp_dir = tmp_path / "stamps"
        b.provision("printf provisioned > stamp-probe", "k1", str(stamp_dir),
                    force=False)
        assert (ws / "stamp-probe").read_text() == "provisioned"
        assert read_stamp(stamp_dir, "k1")
        # stamp hit: a second provision does not re-run (file would change)
        b.provision("printf other > stamp-probe", "k1", str(stamp_dir),
                    force=False)
        assert (ws / "stamp-probe").read_text() == "provisioned"
        # force re-runs
        b.provision("printf refreshed > stamp-probe", "k1", str(stamp_dir),
                    force=True)
        assert (ws / "stamp-probe").read_text() == "refreshed"

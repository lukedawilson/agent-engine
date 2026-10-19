"""Unit tests for the sandbox domain (steps 2-6): value objects, pure
functions, the Docker backend with an injected command runner (the seam — no
monkeypatching), and the host-side audit/stamp helpers against real temp dirs.

No Docker daemon is required: every backend test drives the injected
`CommandRunner`; the real daemon is exercised only by the marked
test_isolation_integration.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_dev_loop.config import IsolationConfig
from agentic_dev_loop.isolation import (
    AUDIT_MAX_BYTES, CmdResult, DEFAULT_DEV_IMAGE_REF,
    DockerBackend, EffectiveProfile, ProbeResult, SandboxError,
    SandboxExecutionRequest, SandboxExecutionResult, append_audit_record,
    clean_stamps, docker_create_payload, docker_provision_payload,
    is_git_mutation, probe_docker, read_stamp, resolve_effective_profile,
    resolve_image_ref, resolve_sandbox_env, select_backend, setup_stamp_key,
    translate_mount_path, write_stamp,
)


class FakeRunner:
    """Scripted CommandRunner — the unit-test seam for the docker CLI."""

    def __init__(self, *script):
        self.calls: list[list[str]] = []
        self.script = list(script)

    def run(self, argv, *, timeout=None, check=False):
        self.calls.append(argv)
        if not self.script:
            return CmdResult(exit_code=0, stdout="", stderr="")
        item = self.script[0]
        if len(self.script) > 1:
            self.script.pop(0)
        return item(argv) if callable(item) else item


def ok(stdout=""):
    return CmdResult(exit_code=0, stdout=stdout, stderr="")


def fail(code, stderr=""):
    return CmdResult(exit_code=code, stdout="", stderr=stderr)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class TestRequest:
    def test_valid_request(self):
        r = SandboxExecutionRequest(argv=["echo", "hi"], cwd="/ws",
                                    env={"PATH": "/bin"}, timeout=1.0)
        assert r.argv == ["echo", "hi"]

    def test_empty_argv_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            SandboxExecutionRequest(argv=[], cwd="/ws", env={})

    def test_relative_cwd_rejected(self):
        with pytest.raises(ValueError, match="absolute"):
            SandboxExecutionRequest(argv=["true"], cwd="ws", env={})

    def test_nonpositive_timeout_rejected(self):
        with pytest.raises(ValueError, match="> 0"):
            SandboxExecutionRequest(argv=["true"], cwd="/ws", env={}, timeout=0)


class TestResult:
    def test_succeeded_and_timeout(self):
        assert SandboxExecutionResult(0, "", "", 1.0, "docker").succeeded
        assert not SandboxExecutionResult(1, "", "", 1.0, "docker").succeeded
        r = SandboxExecutionResult(None, "", "", 1.0, "docker", timed_out=True)
        assert r.is_timeout and not r.succeeded


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


class TestEffectiveProfile:
    def test_defaults(self):
        p = resolve_effective_profile(None)
        assert p.network_off and p.read_only_rootfs and p.writes_only_on_mounts
        assert p.drop_all_capabilities and p.git_mutations_blocked
        assert p.image == DEFAULT_DEV_IMAGE_REF
        assert p.memory == "4g" and p.cpus == 2.0

    def test_overrides(self):
        iso = IsolationConfig(image="img@sha256:abc", memory="8g", cpus=4.0,
                              allow_git_mutations=True)
        p = resolve_effective_profile(iso)
        assert p.image == "img@sha256:abc"
        assert p.memory == "8g" and p.cpus == 4.0
        assert not p.git_mutations_blocked

    def test_git_blocked_by_default(self):
        assert resolve_effective_profile(IsolationConfig()).git_mutations_blocked


class TestResolveSandboxEnv:
    def test_base_only(self):
        env = resolve_sandbox_env(None, host_env={})
        assert env["PATH"] == "/usr/local/bin:/usr/bin:/bin"
        assert env["HOME"] == "/root"
        assert "OPENAI_API_KEY" not in env

    def test_declared_null_inherits(self):
        env = resolve_sandbox_env({"MY_VAR": None}, host_env={"MY_VAR": "hostval"})
        assert env["MY_VAR"] == "hostval"

    def test_declared_value_used(self):
        env = resolve_sandbox_env({"MY_VAR": "declared"}, host_env={"MY_VAR": "hostval"})
        assert env["MY_VAR"] == "declared"

    def test_host_env_not_leaked(self):
        env = resolve_sandbox_env(None, host_env={"SECRET": "s3cr3t", "PATH": "/x"})
        assert "SECRET" not in env


class TestIsGitMutation:
    @pytest.mark.parametrize("argv", [
        ["git", "status"],
        ["git", "log", "--oneline"],
        ["git", "diff"],
        ["git", "show", "HEAD"],
        ["git", "ls-files"],
        ["git", "rev-parse", "HEAD"],
        ["git", "blame", "file.py"],
        ["git", "describe"],
        ["git", "for-each-ref"],
        ["git", "branch"],
        ["git", "tag"],
        ["git", "remote", "-v"],
        ["git", "remote", "show", "origin"],
        ["git", "--help"],
        ["git", "help"],
        ["git", "-C", "/repo", "status"],
        ["git", "-c", "color.ui=false", "log"],
        ["git", "--no-pager", "diff"],
    ])
    def test_read_operations_allowed(self, argv):
        assert not is_git_mutation(argv)

    @pytest.mark.parametrize("argv", [
        ["git", "commit", "-m", "x"],
        ["git", "push"],
        ["git", "reset", "--hard"],
        ["git", "branch", "newbranch"],
        ["git", "branch", "-d", "old"],
        ["git", "tag", "-d", "v1"],
        ["git", "stash"],
        ["git", "merge", "main"],
        ["git", "rebase"],
        ["git", "cherry-pick", "abc"],
        ["git", "revert", "HEAD"],
        ["git", "worktree", "add"],
        ["git", "clean", "-fd"],
        ["git", "gc"],
        ["git", "fetch"],
        ["git", "pull"],
        ["git", "am"],
        ["git", "apply"],
        ["git", "checkout", "main"],
        ["git", "switch", "main"],
        ["git", "rm", "f"],
        ["git", "mv", "a", "b"],
        ["git", "init"],
        ["git", "config", "--local", "x", "y"],
        ["git", "remote", "add", "origin", "url"],
        ["git", "unknown-subcommand"],
    ])
    def test_mutations_blocked(self, argv):
        assert is_git_mutation(argv)

    @pytest.mark.parametrize("argv", [
        ["ls", "-la"],
        ["python", "-m", "pytest"],
        ["git-status", "x"],
        [],
    ])
    def test_non_git_not_classified(self, argv):
        assert not is_git_mutation(argv)

    def test_deny_by_default_unknown_subcommand(self):
        assert is_git_mutation(["git", "frobnicate"])


class TestTranslateMountPath:
    def test_identity_and_idempotence(self, tmp_path):
        p = str(tmp_path / "ws")
        assert translate_mount_path(p) == p
        assert translate_mount_path(translate_mount_path(p)) == translate_mount_path(p)

    def test_expands_user(self):
        out = translate_mount_path("~/ws")
        assert not out.startswith("~")

    def test_relative_absolute_resolution(self):
        assert Path(translate_mount_path("ws")).is_absolute()


class TestSetupStampKey:
    def test_stable(self):
        a = setup_stamp_key("npm i", {"package-lock.json": "h1"})
        b = setup_stamp_key("npm i", {"package-lock.json": "h1"})
        assert a == b

    def test_diverges_on_cmd(self):
        assert setup_stamp_key("a", {}) != setup_stamp_key("b", {})

    def test_diverges_on_lockfile(self):
        assert setup_stamp_key("a", {"x": "1"}) != setup_stamp_key("a", {"x": "2"})

    def test_lockfile_order_insensitive(self):
        a = setup_stamp_key("c", {"b": "2", "a": "1"})
        b = setup_stamp_key("c", {"a": "1", "b": "2"})
        assert a == b


class TestPayloads:
    def _profile(self):
        return EffectiveProfile(True, True, True, True, True, "img", "4g", 2.0)

    def test_create_payload_invariants(self, tmp_path):
        ws = str(tmp_path)
        p = docker_create_payload(run_id="r1", image="img", profile=self._profile(),
                                  workspace=ws)
        assert p[0] == "docker" and "create" in p
        assert "--network" in p and "none" in p
        assert "--read-only" in p
        assert "--cap-drop" in p and "ALL" in p
        mounts = [p[i + 1] for i, a in enumerate(p) if a == "-v"]
        assert mounts == [f"{ws}:{ws}"]  # single mount, exactly {workspace}
        assert p[-2:] == ["sleep", "infinity"]

    def test_provision_payload_invariants(self, tmp_path):
        ws = str(tmp_path)
        p = docker_provision_payload(run_id="r1", image="img", workspace=ws,
                                     setup_cmd="make")
        assert "--network" in p and "bridge" in p
        assert "--read-only" not in p  # rw rootfs
        assert "--cap-drop" in p and "ALL" in p
        assert "sh" in p and "-c" in p and "make" in p
        mounts = [p[i + 1] for i, a in enumerate(p) if a == "-v"]
        assert mounts == [f"{ws}:{ws}"]


class TestSelectBackend:
    def test_totality(self):
        assert select_backend("darwin", ProbeResult("1.43", "linux")) is DockerBackend
        assert select_backend("win32", ProbeResult("1.43", "linux")) is DockerBackend
        assert select_backend("linux", ProbeResult("1.43", "linux")) is DockerBackend


# ---------------------------------------------------------------------------
# Probe + image ref
# ---------------------------------------------------------------------------


class TestProbeDocker:
    def test_success(self, monkeypatch):
        runner = FakeRunner(ok("1.54"), ok("linux"))
        monkeypatch.setattr("agentic_dev_loop.isolation.shutil.which",
                            lambda *a: "/usr/bin/docker")
        r = probe_docker(runner)
        assert r == ProbeResult("1.54", "linux")

    def test_missing_docker(self, monkeypatch):
        monkeypatch.setattr("agentic_dev_loop.isolation.shutil.which",
                            lambda *a: None)
        with pytest.raises(SandboxError, match="AE-SBX-001"):
            probe_docker(FakeRunner())

    def test_daemon_unreachable(self, monkeypatch):
        monkeypatch.setattr("agentic_dev_loop.isolation.shutil.which",
                            lambda *a: "/usr/bin/docker")
        with pytest.raises(SandboxError, match="AE-SBX-002"):
            probe_docker(FakeRunner(fail(1, "Cannot connect")))

    def test_api_too_old(self, monkeypatch):
        monkeypatch.setattr("agentic_dev_loop.isolation.shutil.which",
                            lambda *a: "/usr/bin/docker")
        with pytest.raises(SandboxError, match="AE-SBX-003"):
            probe_docker(FakeRunner(ok("1.24"), ok("linux")))

    def test_windows_containers(self, monkeypatch):
        monkeypatch.setattr("agentic_dev_loop.isolation.shutil.which",
                            lambda *a: "/usr/bin/docker")
        with pytest.raises(SandboxError, match="AE-SBX-004"):
            probe_docker(FakeRunner(ok("1.54"), ok("windows")))


class TestResolveImageRef:
    def test_env_override_wins(self):
        assert resolve_image_ref("pinned", environ={"AGENTIC_DEV_LOOP_DEV_IMAGE": "tag"}) == "tag"

    def test_profile_image_used(self):
        assert resolve_image_ref("img@sha256:x", environ={}) == "img@sha256:x"

    def test_empty_without_override_fails(self):
        with pytest.raises(SandboxError, match="AE-SBX-005"):
            resolve_image_ref("", environ={})


# ---------------------------------------------------------------------------
# DockerBackend with fake runner
# ---------------------------------------------------------------------------


def _backend(tmp_path, runner, *, image="img@sha256:abc", git_blocked=True):
    return DockerBackend(
        image=image, workspace=str(tmp_path / "ws"),
        iso_state_dir=str(tmp_path / "state"),
        profile=EffectiveProfile(True, True, True, True, git_blocked,
                                 image, "4g", 2.0),
        runner=runner)


class TestEnsureImage:
    def test_present_skips_pull(self, tmp_path):
        runner = FakeRunner(ok("sha256:abc"))
        backend = _backend(tmp_path, runner)
        backend.ensure_image()
        assert len(runner.calls) == 1
        assert "inspect" in runner.calls[0]

    def test_pull_retries_on_transient_then_verifies(self, tmp_path):
        runner = FakeRunner(
            fail(1, "id-not-found"),
            fail(1, "Cannot connect to the Docker daemon"),
            fail(1, "connection refused"),
            ok(""),
            ok("img@sha256:abc repo@sha256:other"),
        )
        backend = _backend(tmp_path, runner)
        backend.ensure_image()
        pulls = [c for c in runner.calls if "pull" in c]
        assert len(pulls) == 3  # bounded retry succeeded on the 3rd attempt

    def test_pull_auth_error_is_not_retried(self, tmp_path):
        runner = FakeRunner(fail(1, "id-not-found"), fail(1, "denied: unauthorized"))
        backend = _backend(tmp_path, runner)
        with pytest.raises(SandboxError, match="AE-SBX-006"):
            backend.ensure_image()
        assert len([c for c in runner.calls if "pull" in c]) == 1

    def test_digest_mismatch_fails(self, tmp_path):
        runner = FakeRunner(
            fail(1, "id-not-found"), ok(""), ok("img@sha256:other"),
        )
        backend = _backend(tmp_path, runner)
        with pytest.raises(SandboxError, match="AE-SBX-007"):
            backend.ensure_image()


class TestCreateExecutionContainer:
    def test_eager_create_and_start(self, tmp_path):
        runner = FakeRunner(ok("cid"), ok("cid"))
        backend = _backend(tmp_path, runner)
        backend.create_execution_container()
        assert runner.calls[0][:2] == ["docker", "create"]
        assert "--network" in runner.calls[0] and "none" in runner.calls[0]
        assert runner.calls[1] == ["docker", "start", "rid" + "-exec"] or \
            runner.calls[1][1] == "start"


class TestRun:
    def test_exec_argv_assembly(self, tmp_path):
        runner = FakeRunner(ok(""))  # ensure_image not called here
        backend = _backend(tmp_path, runner)
        backend._container = "c1"
        backend._started = True
        req = SandboxExecutionRequest(argv=["echo", "hi"], cwd=str(tmp_path / "ws"),
                                      env={"PATH": "/bin", "K": "v"}, timeout=10.0)
        backend.run(req)
        exec_argv = runner.calls[-1]
        assert exec_argv[0] == "docker" and exec_argv[1] == "exec"
        assert exec_argv[-4:] == ["/usr/bin/timeout", "10", "echo", "hi"]

    def test_no_timeout_argv_verbatim(self, tmp_path):
        runner = FakeRunner(ok(""))
        backend = _backend(tmp_path, runner)
        backend._container = "c1"
        backend._started = True
        req = SandboxExecutionRequest(argv=["echo", "hi"], cwd=str(tmp_path / "ws"),
                                      env={}, timeout=None)
        backend.run(req)
        assert backend._container in runner.calls[-1]
        assert "/usr/bin/timeout" not in runner.calls[-1]

    def test_exit_124_is_timeout(self, tmp_path):
        runner = FakeRunner(CmdResult(124, "out", ""))
        backend = _backend(tmp_path, runner)
        backend._container = "c1"
        backend._started = True
        req = SandboxExecutionRequest(argv=["sleep", "5"], cwd=str(tmp_path / "ws"),
                                      env={}, timeout=1.0)
        result = backend.run(req)
        assert result.timed_out and result.is_timeout
        assert result.exit_code == 124

    def test_git_mutation_blocked(self, tmp_path):
        runner = FakeRunner()
        backend = _backend(tmp_path, runner, git_blocked=True)
        backend._container = "c1"
        backend._started = True
        req = SandboxExecutionRequest(argv=["git", "commit", "-m", "x"],
                                      cwd=str(tmp_path / "ws"), env={})
        with pytest.raises(SandboxError, match="AE-SBX-008"):
            backend.run(req)
        assert not runner.calls  # never reached docker

    def test_git_mutation_allowed_when_knob_set(self, tmp_path):
        runner = FakeRunner(ok(""))
        backend = _backend(tmp_path, runner, git_blocked=False)
        backend._container = "c1"
        backend._started = True
        req = SandboxExecutionRequest(argv=["git", "commit", "-m", "x"],
                                      cwd=str(tmp_path / "ws"), env={})
        backend.run(req)
        assert runner.calls

    def test_audit_record_written(self, tmp_path):
        runner = FakeRunner(CmdResult(1, "", "boom"))
        backend = _backend(tmp_path, runner)
        backend._container = "c1"
        backend._started = True
        req = SandboxExecutionRequest(argv=["false"], cwd=str(tmp_path / "ws"),
                                      env={"K": "secret"}, pipeline="p", step="s")
        backend.run(req)
        audit = (tmp_path / "state" / "sandbox-audit.jsonl").read_text().strip()
        rec = json.loads(audit)
        assert rec["pipeline"] == "p" and rec["step"] == "s"
        assert rec["exit_code"] == 1
        # env values never logged; env keys are hashed into the digest only
        assert "secret" not in audit
        assert "secret" not in rec["request_digest"]

    def test_daemon_lost_raises_after_audit(self, tmp_path):
        runner = FakeRunner(CmdResult(None, "", "lost"))
        backend = _backend(tmp_path, runner)
        backend._container = "c1"
        backend._started = True
        req = SandboxExecutionRequest(argv=["true"], cwd=str(tmp_path / "ws"), env={})
        with pytest.raises(SandboxError, match="AE-SBX-012"):
            backend.run(req)
        assert (tmp_path / "state" / "sandbox-audit.jsonl").exists()


class TestClose:
    def test_idempotent(self, tmp_path):
        runner = FakeRunner(ok(""), ok(""))
        backend = _backend(tmp_path, runner)
        backend._started = True
        backend._container = "c1"
        backend.close()
        backend.close()
        stops = [c for c in runner.calls if c[0] == "docker" and c[1] == "stop"]
        assert len(stops) == 1

    def test_noop_when_not_started(self, tmp_path):
        runner = FakeRunner()
        backend = _backend(tmp_path, runner)
        backend.close()
        assert runner.calls == []


# ---------------------------------------------------------------------------
# Provision + stamps + audit (real temp dirs)
# ---------------------------------------------------------------------------


class TestProvisionStampsAudit:
    def test_provision_writes_stamp(self, tmp_path):
        runner = FakeRunner(ok(""))
        backend = _backend(tmp_path, runner)
        stamp_dir = tmp_path / "stamps"
        backend.provision("make build", "key1", str(stamp_dir), force=False)
        assert read_stamp(stamp_dir, "key1")
        assert runner.calls

    def test_provision_skips_on_stamp(self, tmp_path):
        runner = FakeRunner(ok(""))
        backend = _backend(tmp_path, runner)
        stamp_dir = tmp_path / "stamps"
        write_stamp(stamp_dir, "key1")
        backend.provision("make build", "key1", str(stamp_dir), force=False)
        assert runner.calls == []

    def test_provision_refresh_forces(self, tmp_path):
        runner = FakeRunner(ok(""))
        backend = _backend(tmp_path, runner)
        stamp_dir = tmp_path / "stamps"
        write_stamp(stamp_dir, "key1")
        backend.provision("make build", "key1", str(stamp_dir), force=True)
        assert runner.calls

    def test_provision_failure_no_stamp(self, tmp_path):
        runner = FakeRunner(CmdResult(2, "make: *** Error", ""))
        backend = _backend(tmp_path, runner)
        stamp_dir = tmp_path / "stamps"
        with pytest.raises(SandboxError, match="AE-SBX-009"):
            backend.provision("make", "key1", str(stamp_dir), force=False)
        assert not read_stamp(stamp_dir, "key1")

    def test_clean_stamps(self, tmp_path):
        state = tmp_path / "state"
        for k in ("a", "b", "c"):
            write_stamp(state / "stamps", k)
        assert clean_stamps(state) == 3
        assert clean_stamps(state) == 0

    def test_audit_rotation(self, tmp_path, monkeypatch):
        state = tmp_path / "state"
        monkeypatch.setattr("agentic_dev_loop.isolation.AUDIT_MAX_BYTES", 10)
        append_audit_record(state, {"n": 1, "pad": "x" * 8})
        append_audit_record(state, {"n": 2, "pad": "y" * 8})
        assert (state / "sandbox-audit.jsonl").exists()
        assert (state / "sandbox-audit.jsonl.1").exists()
        # the rolled file holds the earlier record, the fresh one the later
        rolled = (state / "sandbox-audit.jsonl.1").read_text()
        assert "x" * 8 in rolled


class TestStartupSandbox:
    """Eager startup sequence (Q2): probe → image → create/start → provision
    all declared setups — with zero infra operations left for the run phase."""

    def _cfg(self, tmp_path, with_setup=False):
        from agentic_dev_loop.config import PipelineConfig
        steps = [{"name": "dev", "agent": "dev", "on_pass": "test"},
                 {"name": "test", "command": "make", "on_pass": "success"}]
        if with_setup:
            steps[1]["setup"] = "python -m venv .venv-sandbox"
        return PipelineConfig.model_validate({
            "name": "p", "llm": {"model": "m", "api_key_env": "K"},
            "agents_dir": "agents", "steps": steps,
            "isolation": {"state_dir": str(tmp_path / "iso-state")},
        })

    def test_sequence_and_provision(self, tmp_path, monkeypatch):
        from agentic_dev_loop import isolation
        from agentic_dev_loop.isolation import startup_sandbox

        ws = tmp_path / "ws"
        ws.mkdir()
        cfg = self._cfg(tmp_path, with_setup=True)
        monkeypatch.setattr("agentic_dev_loop.isolation.shutil.which",
                            lambda *a: "/usr/bin/docker")
        monkeypatch.setenv("AGENTIC_DEV_LOOP_DEV_IMAGE", "img:tag")
        runner = FakeRunner(
            ok("1.54"),           # probe version
            ok("linux"),          # probe ostype
            ok(""),               # image inspect (pull)
            ok(""),               # docker create
            ok(""),               # docker start
            ok(""),               # docker run provision
        )
        sandbox = startup_sandbox(cfg, workspace=ws, runner=runner)
        try:
            kinds = [c[1] for c in runner.calls]
            assert kinds == ["version", "info", "image", "create", "start", "run"]
            # the provision payload carries the setup command
            run_argv = runner.calls[-1]
            assert "python -m venv .venv-sandbox" in run_argv
            # stamp written host-side
            stamps = tmp_path / "iso-state" / "stamps"
            assert list(stamps.iterdir())
        finally:
            sandbox.close()

    def test_refresh_forces_provision(self, tmp_path, monkeypatch):
        from agentic_dev_loop.isolation import (setup_stamp_key, startup_sandbox,
                                                write_stamp)

        ws = tmp_path / "ws"
        ws.mkdir()
        cfg = self._cfg(tmp_path, with_setup=True)
        monkeypatch.setattr("agentic_dev_loop.isolation.shutil.which",
                            lambda *a: "/usr/bin/docker")
        monkeypatch.setenv("AGENTIC_DEV_LOOP_DEV_IMAGE", "img:tag")

        # Pre-write the stamp as if a prior run already provisioned.
        stamps = tmp_path / "iso-state" / "stamps"
        write_stamp(stamps, setup_stamp_key("python -m venv .venv-sandbox", {}))

        # Without refresh the stamp is a hit: no provision container runs.
        runner = FakeRunner(ok("1.54"), ok("linux"), ok(""), ok(""), ok(""))
        sandbox = startup_sandbox(cfg, workspace=ws, runner=runner)
        sandbox.close()
        assert not [c for c in runner.calls if c[0] == "docker" and c[1] == "run"]

        # With refresh the stamp is ignored: provision re-runs.
        runner2 = FakeRunner(ok("1.54"), ok("linux"), ok(""), ok(""), ok(""), ok(""))
        sandbox2 = startup_sandbox(cfg, workspace=ws, runner=runner2, refresh=True)
        sandbox2.close()
        assert [c for c in runner2.calls if c[0] == "docker" and c[1] == "run"]

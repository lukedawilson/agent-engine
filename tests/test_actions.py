"""Action tests — ported from yosk's TestKillListenersOnPort /
TestGitWorktreeClean / TestCommitNode, retargeted at the node-shaped
`(state, params) -> dict` API. Real processes and real git repos throughout:
git and sockets are local utilities, not network boundaries."""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agent_engine.actions import (_listening_pids, _parse_cwd_output, commit,
                                  git_worktree_clean, kill_listeners,
                                  kill_listeners_on_port)

lsof_required = pytest.mark.skipif(
    shutil.which("lsof") is None, reason="lsof required")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def spawn_listener(port: int, cwd: Path | None = None) -> subprocess.Popen:
    """Spawn a real process listening on 127.0.0.1:port — stands in for an
    orphaned app server. Its command line contains 'socket' (from the -c code)."""
    code = (
        "import socket,time;"
        "s=socket.socket();"
        "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
        f"s.bind(('127.0.0.1',{port}));"
        "s.listen();"
        "time.sleep(120)"
    )
    return subprocess.Popen([sys.executable, "-c", code], cwd=cwd)


def wait_listening(port: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.05)
    raise RuntimeError(f"listener on port {port} never came up")


def init_git_repo(path: Path) -> None:
    """A real git repo with an initial commit, ready for commit-node tests."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"],
                   cwd=path, check=True)
    (path / "seed.txt").write_text("seed")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=path, check=True,
                   capture_output=True)


def git_log(path: Path) -> str:
    return subprocess.run(["git", "log", "--oneline"], cwd=path, check=True,
                          capture_output=True, text=True).stdout


COMMIT_PARAMS = {"message": "feat: construct {subject} (agent dev loop)"}


class TestKillListenersOnPort:
    """The orphan sweep exists to kill real orphaned servers, so it is tested
    with real processes — mocking it would test nothing."""

    @lsof_required
    def test_kills_listener_on_port(self):
        port = free_port()
        proc = spawn_listener(port)
        try:
            wait_listening(port)
            kill_listeners_on_port(port)
            proc.wait(timeout=5)
            assert proc.poll() is not None
        finally:
            if proc.poll() is None:
                proc.kill()

    @lsof_required
    def test_no_listener_is_a_noop(self):
        kill_listeners_on_port(free_port())  # must not raise

    @lsof_required
    def test_match_filter_spares_non_matching_processes(self):
        port = free_port()
        proc = spawn_listener(port)
        try:
            wait_listening(port)
            kill_listeners_on_port(port, match="no-such-process-name")
            assert proc.poll() is None  # still alive — filter did not match
        finally:
            proc.kill()

    @lsof_required
    def test_match_filter_kills_matching_processes(self):
        port = free_port()
        proc = spawn_listener(port)
        try:
            wait_listening(port)
            kill_listeners_on_port(port, match="socket")  # in the -c code
            proc.wait(timeout=5)
            assert proc.poll() is not None
        finally:
            if proc.poll() is None:
                proc.kill()

    @lsof_required
    def test_escalates_to_sigkill_when_term_ignored(self):
        """A server that ignores SIGTERM must still be swept — otherwise the
        orphan holds the port indefinitely."""
        port = free_port()
        code = (
            "import signal,socket,time;"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN);"
            "s=socket.socket();"
            "s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);"
            f"s.bind(('127.0.0.1',{port}));"
            "s.listen();"
            "time.sleep(120)"
        )
        proc = subprocess.Popen([sys.executable, "-c", code])
        try:
            wait_listening(port)
            kill_listeners_on_port(port)
            proc.wait(timeout=10)
            assert proc.poll() is not None
        finally:
            if proc.poll() is None:
                proc.kill()

    @lsof_required
    def test_node_sweeps_from_params(self):
        """The node-shaped wrapper reads port/match from step params."""
        port = free_port()
        proc = spawn_listener(port)
        try:
            wait_listening(port)
            update = kill_listeners({"subject": "x"}, {"port": port, "match": "socket"})
            proc.wait(timeout=5)
            assert proc.poll() is not None
            assert update == {}
        finally:
            if proc.poll() is None:
                proc.kill()

    @lsof_required
    def test_never_sweeps_own_listener(self):
        """A pipeline's own process may be listening on the swept port (the
        live viz server). It must never be swept — only orphaned listeners
        from other processes (previous runs / agent subprocesses)."""
        port = free_port()
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen()
        try:
            assert str(os.getpid()) not in _listening_pids(port, None)
        finally:
            s.close()

    @lsof_required
    def test_cwd_filter_kills_matching_cwd(self, tmp_path):
        port = free_port()
        proc = spawn_listener(port, cwd=tmp_path)
        try:
            wait_listening(port)
            kill_listeners_on_port(port, cwd=tmp_path)
            proc.wait(timeout=5)
            assert proc.poll() is not None
        finally:
            if proc.poll() is None:
                proc.kill()

    @lsof_required
    def test_cwd_filter_spares_other_directory(self, tmp_path):
        other = tmp_path / "elsewhere"
        other.mkdir()
        port = free_port()
        proc = spawn_listener(port, cwd=tmp_path)
        try:
            wait_listening(port)
            kill_listeners_on_port(port, cwd=other)
            assert proc.poll() is None  # still alive — cwd differs
        finally:
            proc.kill()

    @lsof_required
    def test_cwd_with_nonmatching_match_spares(self, tmp_path):
        port = free_port()
        proc = spawn_listener(port, cwd=tmp_path)
        try:
            wait_listening(port)
            kill_listeners_on_port(port, match="no-such-process-name",
                                   cwd=tmp_path)
            assert proc.poll() is None  # cwd matched but command line didn't
        finally:
            proc.kill()


class TestPidCwd:
    def test_parses_path_after_fcwd(self):
        assert _parse_cwd_output(
            "p42312\nfcwd\nn/Users/luke/dev/work/agent-engine\n") == \
            "/Users/luke/dev/work/agent-engine"

    def test_none_when_no_path_line(self):
        assert _parse_cwd_output("p42312\nfcwd\n") is None
        assert _parse_cwd_output("p42312\n") is None

    def test_none_for_garbage(self):
        assert _parse_cwd_output("garbage\n") is None
        assert _parse_cwd_output("") is None


class TestGitWorktreeClean:
    def test_clean_repo(self, tmp_path):
        repo = tmp_path / "repo"
        init_git_repo(repo)
        assert git_worktree_clean(repo) is True

    def test_dirty_repo(self, tmp_path):
        repo = tmp_path / "repo"
        init_git_repo(repo)
        (repo / "new.txt").write_text("uncommitted")
        assert git_worktree_clean(repo) is False

    def test_not_a_repo_is_not_clean(self, tmp_path):
        """Fail-safe: outside a git repo there is no clean baseline, so the
        commit node stays disabled."""
        assert git_worktree_clean(tmp_path) is False


class TestCommitNode:
    """Run 004 policy: agents never commit mid-run; the pipeline commits the
    constructed work exactly once, and only when the worktree was clean at
    run start (so the auto-commit can never sweep up pre-existing unrelated
    changes the way the dev agent's b4acb62a did)."""

    def test_commits_constructed_work(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        init_git_repo(repo)
        (repo / "feature.cs").write_text("// constructed by the pipeline")
        monkeypatch.chdir(repo)

        update = commit({"subject": "unit U2", "commit_allowed": True}, COMMIT_PARAMS)

        log = git_log(repo)
        assert "feat: construct unit U2 (agent dev loop)" in log
        assert "seed" in log  # exactly one new commit on top
        assert update == {}

    def test_message_template_renders_subject(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        init_git_repo(repo)
        (repo / "f.txt").write_text("x")
        monkeypatch.chdir(repo)

        commit({"subject": "pipeline widgets", "commit_allowed": True},
               {"message": "build {subject}"})

        assert "build pipeline widgets" in git_log(repo)

    def test_missing_message_param_fails_fast(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        init_git_repo(repo)
        (repo / "f.txt").write_text("x")
        monkeypatch.chdir(repo)

        with pytest.raises(ValueError, match="message"):
            commit({"subject": "s", "commit_allowed": True}, {})

    def test_skips_when_worktree_was_dirty_at_run_start(self, tmp_path,
                                                        monkeypatch, capsys):
        repo = tmp_path / "repo"
        init_git_repo(repo)
        (repo / "feature.cs").write_text("// constructed by the pipeline")
        monkeypatch.chdir(repo)

        commit({"subject": "unit U2", "commit_allowed": False}, COMMIT_PARAMS)

        assert "feature.cs" not in subprocess.run(
            ["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout
        assert "Skipping auto-commit" in capsys.readouterr().out

    def test_missing_state_key_defaults_to_skip(self, tmp_path, monkeypatch):
        """Checkpoints written before the policy existed have no
        commit_allowed key — resuming them must not suddenly commit."""
        repo = tmp_path / "repo"
        init_git_repo(repo)
        (repo / "feature.cs").write_text("// constructed by the pipeline")
        monkeypatch.chdir(repo)

        commit({"subject": "unit U2"}, COMMIT_PARAMS)

        assert "feature.cs" not in subprocess.run(
            ["git", "ls-files"], cwd=repo, capture_output=True, text=True).stdout

    def test_nothing_to_commit_is_a_noop(self, tmp_path, monkeypatch, capsys):
        repo = tmp_path / "repo"
        init_git_repo(repo)
        monkeypatch.chdir(repo)
        before = git_log(repo)

        commit({"subject": "unit U2", "commit_allowed": True}, COMMIT_PARAMS)

        assert git_log(repo) == before
        assert "Nothing to commit" in capsys.readouterr().out

    def test_commit_failure_does_not_fail_the_run(self, tmp_path, monkeypatch,
                                                  capsys):
        """The work is already verified — a git error is a loud warning, not
        a pipeline failure."""
        repo = tmp_path / "repo"
        init_git_repo(repo)
        (repo / "feature.cs").write_text("// constructed by the pipeline")
        monkeypatch.chdir(repo)
        # Force `git commit` to fail deterministically: env-scoped config
        # overrides every config file, and an empty ident is fatal.
        monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "user.name")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "")
        monkeypatch.setenv("GIT_CONFIG_KEY_1", "user.email")
        monkeypatch.setenv("GIT_CONFIG_VALUE_1", "")

        update = commit({"subject": "unit U2", "commit_allowed": True}, COMMIT_PARAMS)

        assert update == {}
        assert "auto-commit failed" in capsys.readouterr().err

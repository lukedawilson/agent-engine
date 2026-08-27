"""Built-in pipeline actions. Node-shaped: (state, params) -> state update.

`commit` policy (ported unchanged from yosk): agents never commit mid-run;
the pipeline commits exactly once, and only when the worktree was clean at
run start — a dirty-at-start run is committed by the human, so the
auto-commit can never swallow pre-existing unrelated changes (run 004: the
dev agent's b4acb62a swept up an unrelated .gitignore edit).
"""

import os
import subprocess
import sys
import time
from pathlib import Path


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Best-effort git invocation — callers inspect returncode/stdout rather
    than raising, so a git problem never crashes a verified run."""
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, check=False)


def git_worktree_clean(path: Path) -> bool:
    """True only when `path` is a git repo with no uncommitted changes.
    Outside a repo there is no clean baseline — False (fail-safe, keeps the
    commit node disabled)."""
    result = _git(["status", "--porcelain"], cwd=path)
    return result.returncode == 0 and not result.stdout.strip()


def _listening_pids(port: int, match: str | None) -> list[str]:
    """PIDs of processes listening on `port`, optionally only those whose
    command line contains `match`. The current process is always excluded — a
    pipeline must never sweep its own listener (e.g. the live viz server),
    only orphaned listeners left behind by earlier runs or agent subprocesses."""
    out = subprocess.run(
        ["lsof", "-nP", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        capture_output=True, text=True, check=False).stdout
    self_pid = str(os.getpid())
    pids = []
    for pid in out.split():
        if pid == self_pid:
            continue
        if match is not None:
            cmd = subprocess.run(
                ["ps", "-p", pid, "-o", "command="],
                capture_output=True, text=True, check=False).stdout
            if match not in cmd:
                continue
        pids.append(pid)
    return pids


def kill_listeners_on_port(port: int, match: str | None = None,
                           term_timeout: float = 3.0) -> None:
    """Kill processes listening on `port`, optionally only those whose command
    line contains `match`. A stage that was cut short can orphan its server;
    the next attempt's server would fail to bind and probes would hit the
    stale process serving a previous attempt's build.

    SIGTERM first, then SIGKILL whatever still holds the port after
    `term_timeout` — a server that ignores TERM must not hold the port
    indefinitely. Port freedom is judged by re-running lsof, so zombies
    (dead, unreaped children) never look like survivors."""
    try:
        pids = _listening_pids(port, match)
    except FileNotFoundError:
        print(f"WARNING: lsof not found — cannot sweep orphaned listeners on "
              f"port {port}.", file=sys.stderr, flush=True)
        return
    for pid in pids:
        subprocess.run(["kill", pid], capture_output=True, check=False)
    survivors = pids
    deadline = time.monotonic() + term_timeout
    while survivors and time.monotonic() < deadline:
        survivors = _listening_pids(port, match)
        if survivors:
            time.sleep(0.05)
    for pid in survivors:
        subprocess.run(["kill", "-9", pid], capture_output=True, check=False)


def kill_listeners(_state: dict, params: dict) -> dict:
    """Node wrapper: sweep listeners per `params: {port: N, match: str?}`."""
    kill_listeners_on_port(params["port"], match=params.get("match"))
    return {}


def commit(state: dict, params: dict) -> dict:
    """The pipeline's only commit point. Skipped loudly when the worktree was
    dirty at run start, so the auto-commit can never swallow pre-existing
    unrelated changes; a dirty-at-start run is committed by the human.

    `params["message"]` is required — a template rendered with `{subject}`.
    Runs in the process's cwd (the consumer repo the pipeline was launched
    from)."""
    subject = state["subject"]
    if not state.get("commit_allowed", False):
        print(f"[{subject}] Skipping auto-commit — worktree was dirty at run "
              f"start; commit the constructed work manually.", flush=True)
        return {}
    if "message" not in params:
        raise ValueError("commit action requires params.message "
                         "(a template rendered with {subject})")
    cwd = Path.cwd()
    _git(["add", "-A"], cwd=cwd)
    if not _git(["status", "--porcelain"], cwd=cwd).stdout.strip():
        print(f"[{subject}] Nothing to commit.", flush=True)
        return {}
    message = params["message"].format(subject=subject)
    result = _git(["commit", "-m", message], cwd=cwd)
    if result.returncode != 0:
        # The work is built and verified — a git error is a loud warning,
        # not a pipeline failure.
        print(f"WARNING: [{subject}] auto-commit failed — commit manually.\n"
              f"{result.stderr.strip()}", file=sys.stderr, flush=True)
        return {}
    short = _git(["rev-parse", "--short", "HEAD"], cwd=cwd).stdout.strip()
    print(f"[{subject}] Committed constructed work as {short}.", flush=True)
    return {}

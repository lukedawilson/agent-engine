"""Pure subprocess helpers shared by command and action steps.

Command steps classify their command string, split simple commands into argv
lists, and scrub the child environment; action steps reuse the pid-token gate
and the same env scrubbing. All four functions are stateless (PBT targets).
"""

from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
from collections.abc import Mapping

_SHELL_METACHARS = frozenset("&|;><$`~*?[]")
_FIXED_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TERM")


def needs_shell(command: str) -> bool:
    """True when `command` carries shell metacharacters (``&&``, ``|``,
    ``;``, ``>``, ``<``, ``$``, backticks, ``~``, or glob chars). Simple
    commands are shlex-split and run shell-free; anything else keeps
    ``shell=True`` (BR-4.1 / BR-4.2)."""
    return any(char in _SHELL_METACHARS for char in command)


def split_command(command: str) -> list[str]:
    """Split a simple command into argv via ``shlex.split``. Callers invoke
    this only when ``needs_shell`` is false - ``shlex`` never sees a shell
    command (BR-4.1)."""
    return shlex.split(command)


def host_shell_execution(
        command: str, *, nt: bool = os.name == "nt",
        which=shutil.which) -> tuple[str | list[str], bool]:
    """How the HOST (non-sandbox) path executes a shell-needing command.

    POSIX: the raw string with ``shell=True`` (unchanged unit-2 behaviour).
    Windows: ``shell=True`` is cmd.exe, which mangles ``$VAR`` expansion and
    ``|`` pipelines (the CI-red hybrid failures) - prefer the discovered
    POSIX ``sh`` (git-bash) via argv instead; fall back to ``shell=True``
    only when no ``sh`` exists anywhere on PATH.
    """
    if not nt:
        return command, True
    sh = which("sh")
    if sh:
        return [sh, "-c", command], False
    return command, True


def kill_process_tree(proc, *, nt: bool | None = None,
                      run=subprocess.run) -> None:
    """Terminate `proc` and its descendants after a timeout.

    POSIX: ``start_new_session`` made ``proc.pid`` the process-group id -
    ``killpg`` reaps the whole group (a shell wrapper's children survive a
    plain ``kill``).

    Windows: ``proc.kill()`` terminates only the direct child - a git-bash
    ``sh -c`` wrapper's python child survives and keeps the pipes open, so
    the follow-up ``communicate()`` blocks out the child's full lifetime.
    ``taskkill /T`` walks the process tree while the parent is still alive,
    then ``kill`` sweeps up anything left (CI-red: 9.5s timeout test).
    """
    if nt is None:
        nt = os.name == "nt"
    if nt:
        run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True, check=False)
        proc.kill()
    else:
        os.killpg(proc.pid, signal.SIGKILL)


def is_pid_token(token: str) -> bool:
    """True only for a plain decimal integer - the only tokens from ``lsof``
    output safe to hand to ``kill``/``ps`` (BR-5.2)."""
    return token.isascii() and token.isdigit()


def child_env(allowlist: list[str] | None = None,
              api_key_env: str | None = None,
              parent: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build a scrubbed child environment: the fixed known-safe whitelist
    (``PATH``, ``HOME``, ``LANG``, ``LC_ALL``, ``TERM``), plus the env var
    named by ``api_key_env`` (always included by default), plus any
    additional names in ``allowlist`` (the author-extensible
    ``env_allowlist``). Everything else is excluded
    (BR-4.3, BR-5.4, NFR-2.1)."""
    source = os.environ if parent is None else parent
    names = set(_FIXED_ENV)
    if api_key_env:
        names.add(api_key_env)
    if allowlist:
        names.update(allowlist)
    return {name: source[name] for name in names if name in source}

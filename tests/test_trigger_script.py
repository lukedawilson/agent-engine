"""Trigger-script contract tests.

The trigger script must keep the pipx-managed engine install current:
a stale install rejects newer pipeline configs at load time (e.g.
`deps_policy` in a11 rejected by an a10 install), so an existing install
is upgraded on every run. Tests drive the real script with stub
executables on PATH — no network, no mocks of the script's logic.

The script is bash, so it is executed through `bash` on every platform:
Windows cannot CreateProcess a `.sh` file (shebangs are a POSIX concept)
and its MSYS bash (git-bash, preinstalled on windows-latest runners)
understands only POSIX-style paths (`/c/...`), so PATH entries and
redirect targets inside stub bodies are converted accordingly.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "trigger-agentic-dev-loop.sh"


def _msys(path: Path) -> str:
    """POSIX-style form of a Windows path (`C:\\x` -> `/c/x`).

    MSYS bash splits PATH on `:` and treats backslashes as escapes, so a
    native `C:\\...` entry would fragment into `C` + `\\...`. Pass the
    mount-style form instead. On POSIX the path is returned unchanged.
    """
    if os.name != "nt":
        return str(path)
    drive, rest = os.path.splitdrive(str(path))
    return "/" + drive[0].lower() + rest.replace("\\", "/")


def _bash() -> str:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is required to run the trigger script")
    return bash


def _run_script(*args: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_bash(), _msys(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _make_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/bash\n{body}\n")
    path.chmod(0o755)


def _env_with(bin_dir: Path | None = None) -> dict:
    entries = ["/usr/bin", "/bin"]
    if bin_dir is not None:
        entries.insert(0, _msys(bin_dir))
    return {**os.environ, "PATH": ":".join(entries)}


def test_trigger_upgrades_existing_install(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    pipx_log = tmp_path / "pipx.log"
    _make_stub(
        bin_dir,
        "agentic-dev-loop",
        'echo "cli-ran: $*"',
    )
    _make_stub(
        bin_dir,
        "pipx",
        f'echo "$*" >> "{_msys(pipx_log)}"',
    )

    result = _run_script("--plan", "plan.md", env=_env_with(bin_dir))

    assert result.returncode == 0, result.stderr
    assert pipx_log.read_text().strip() == "upgrade --cooldown 0 --pip-args=--prerelease=allow agentic-dev-loop"
    # The upgrade happens before the loop is launched.
    assert "cli-ran:" in result.stdout


def test_trigger_fails_fast_when_upgrade_fails(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub(bin_dir, "agentic-dev-loop", "echo should-not-run")
    _make_stub(bin_dir, "pipx", "echo upgrade-broken >&2; exit 1")

    result = _run_script(env=_env_with(bin_dir))

    assert result.returncode != 0
    assert "pipx upgrade" in result.stderr
    assert "should-not-run" not in result.stdout


def test_trigger_errors_when_cli_absent():
    result = _run_script(env=_env_with())

    assert result.returncode != 0
    assert "pipx install" in result.stderr

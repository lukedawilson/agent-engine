"""Trigger-script contract tests.

The trigger script must keep the pipx-managed engine install current:
a stale install rejects newer pipeline configs at load time (e.g.
`deps_policy` in a11 rejected by an a10 install), so an existing install
is upgraded on every run. Tests drive the real script with stub
executables on PATH — no network, no mocks of the script's logic.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "trigger-agentic-dev-loop.sh"


def _make_stub(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/bash\n{body}\n")
    path.chmod(0o755)


def _env_with(bin_dir: Path) -> dict:
    return {"PATH": f"{bin_dir}:/usr/bin:/bin"}


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
        f'echo "$*" >> {pipx_log}',
    )

    result = subprocess.run(
        [str(SCRIPT), "--plan", "plan.md"],
        capture_output=True,
        text=True,
        env=_env_with(bin_dir),
    )

    assert result.returncode == 0, result.stderr
    assert pipx_log.read_text().strip() == "upgrade agentic-dev-loop"
    # The upgrade happens before the loop is launched.
    assert "cli-ran:" in result.stdout


def test_trigger_fails_fast_when_upgrade_fails(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _make_stub(bin_dir, "agentic-dev-loop", "echo should-not-run")
    _make_stub(bin_dir, "pipx", "echo upgrade-broken >&2; exit 1")

    result = subprocess.run(
        [str(SCRIPT)],
        capture_output=True,
        text=True,
        env=_env_with(bin_dir),
    )

    assert result.returncode != 0
    assert "pipx upgrade" in result.stderr
    assert "should-not-run" not in result.stdout


def test_trigger_errors_when_cli_absent(tmp_path):
    result = subprocess.run(
        [str(SCRIPT)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin"},
    )

    assert result.returncode != 0
    assert "pipx install" in result.stderr

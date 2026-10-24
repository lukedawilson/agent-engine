"""Reject em dash characters (U+2014) in repository text files.

The em dash ban lives in AGENTS.md. This checker is the single
implementation behind both guards: `tests/test_repo_ascii.py` runs it over
every tracked file, and `.pre-commit-config.yaml` runs it over staged
files.

Usage:
    python tools/check_no_em_dash.py [FILE ...]

With no arguments, every file listed by `git ls-files` is checked. Files
that do not decode as UTF-8 are treated as binary assets and skipped.

Exit status: 0 when no em dash is found, 1 otherwise.
"""

import subprocess
import sys
from pathlib import Path

EM_DASH = "\u2014"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def _offenders(paths: list[str]) -> list[str]:
    offenders: list[str] = []
    for name in paths:
        try:
            text = Path(name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if EM_DASH in line:
                offenders.append(f"{name}:{number}: {line}")
    return offenders


def main(arguments: list[str]) -> int:
    paths = arguments[1:] or _tracked_files()
    offenders = _offenders(paths)
    for offender in offenders:
        print(offender)
    if offenders:
        print(
            f"rejected: {len(offenders)} em dash characters found; replace "
            "with a comma, colon, hyphen, or a restructured sentence (see "
            "the em dash ban in AGENTS.md)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

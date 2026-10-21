"""Console entry point `agentic-dev-loop-workflow` — the workflow-mode
install surface (ID-3): `install-skill` installs the skill payload; the
projection itself is `python -m agentic_dev_loop.core.project`."""

from __future__ import annotations

import argparse
import sys

from . import install_skill, skill_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentic-dev-loop-workflow",
        description="Workflow-mode helpers for agentic-dev-loop.")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser(
        "install-skill",
        help="install the /agentic-dev-loop skill to ~/.claude/skills")
    install.add_argument("--target", default=None,
                         help="override the install directory")
    args = parser.parse_args(argv)

    if args.command == "install-skill":
        try:
            target = install_skill(args.target)
        except OSError as exc:
            print(f"install-skill failed: {exc}\n"
                  f"Fix: ensure {skill_dir().parent} exists and is writable.",
                  file=sys.stderr)
            return 1
        print(f"Installed skill to {target}", flush=True)
        return 0
    return 2  # unreachable — required subcommand


if __name__ == "__main__":
    sys.exit(main())

"""Docker-free commit shim (BR-8, FR-4.6): the engine's single gated commit
point, exposed as a subprocess-invocable helper for workflow mode.

Workflow steps run in Claude Code's own environment, so this shim pulls in
neither openhands-sdk nor docker — it reaches `actions.commit` directly,
which is already docker-free and preserves the trusted hooksPath + templated
message. It refuses loudly when the worktree was not clean at run start.
"""

from __future__ import annotations

import argparse
import sys

from .actions import commit as _engine_commit


def run_commit(message_template: str, subject: str, commit_allowed: bool,
               state_dir: str | None = None) -> int:
    """Run the gated commit. Returns 0 on success (including a clean-but-
    empty worktree, which the engine reports as "Nothing to commit"), 1 when
    the commit is refused (dirty-at-start)."""
    if not commit_allowed:
        print("Refusing to commit — worktree was not clean at run start; "
              "commit the constructed work manually.", file=sys.stderr,
              flush=True)
        return 1
    if not message_template:
        raise ValueError("commit shim requires a message template "
                         "(rendered with {subject})")
    state: dict = {"subject": subject, "commit_allowed": True}
    if state_dir is not None:
        state["state_dir"] = state_dir
    _engine_commit(state, {"message": message_template})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentic-dev-loop-commit",
        description="Docker-free, gated commit for workflow mode.")
    parser.add_argument("message",
                        help="commit message template (rendered with {subject})")
    parser.add_argument("--subject", default="", help="the {subject} value")
    parser.add_argument("--allowed", action="store_true",
                        help="the worktree was clean at run start (required "
                             "before any auto-commit)")
    parser.add_argument("--state-dir", default=None,
                        help="pipeline state dir (excludes checkpoint sqlite "
                             "from the commit)")
    args = parser.parse_args(argv)
    return run_commit(args.message, args.subject, args.allowed, args.state_dir)


if __name__ == "__main__":
    sys.exit(main())

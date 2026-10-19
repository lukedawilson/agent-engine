"""The suite must exercise the working tree, not an installed wheel.

This repo dogfoods its own published wheel in .venv (deliberate). Plain
pytest would otherwise import the published code and silently test stale
behaviour. This test pins the import to src/ — it fails the moment the
conftest sys.path insertion stops working.
"""

from pathlib import Path

import agentic_dev_loop

REPO_SRC = Path(__file__).resolve().parents[1] / "src"


def test_import_resolves_to_working_tree():
    resolved = Path(agentic_dev_loop.__file__).resolve()
    assert str(resolved).startswith(
        str(REPO_SRC) + "/"
    ), (
        f"agentic_dev_loop imported from {resolved}, not the working tree "
        f"({REPO_SRC}) — conftest's src/ sys.path insertion is not effective"
    )

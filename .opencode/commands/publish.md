---
description: Cut and publish an agentic-dev-loop release - bump version, update changelog, commit, tag, push; the v* tag push triggers release.yml (tests → PyPI → GitHub Release). Usage: /publish [--major|--minor|--patch|<version>] [--description "text"]
---

!`.venv/bin/python tools/publish.py $ARGUMENTS --dry-run`

!`.venv/bin/python tools/publish.py $ARGUMENTS`

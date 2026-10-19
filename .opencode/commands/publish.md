---
description: Cut and publish an agentic-dev-loop release — bump version, update changelog, commit, tag, push; the v* tag push triggers release.yml (tests → PyPI → GitHub Release). Usage: /publish [--major|--minor|--patch|<version>] [--description "text"]
---

Run the release script with the user's arguments. First show the dry-run so the
plan is visible before anything changes:

!`.venv/bin/python tools/publish.py $ARGUMENTS --dry-run`

If the dry-run plan is correct, execute it for real:

!`.venv/bin/python tools/publish.py $ARGUMENTS`

The script is the single source of truth for release mechanics — never
hand-edit pyproject.toml or CHANGELOG.md as part of this command. Report the
new version, the tag, the changelog entry, and the commit. If the script
fails, report the error; do not attempt manual workarounds.

Notes:
- Selectors are mutually exclusive: `--major`, `--minor`, `--patch`, or an
  explicit canonical PEP 440 version such as `0.3.0` or `1.0.0rc1`
  (a `v` prefix is tolerated; non-canonical forms like `1.0.0-rc.1` are
  rejected with the canonical spelling).
- `--major` on an rc of x.0.0 finalises it (`1.0.0rc1` → `1.0.0`); rc
  iteration (`1.0.0rc2`) is done with an explicit version.
- With no `--description`, the changelog entry comes from the
  `## [Unreleased]` section when it has content, otherwise from git history
  since the last tag. A given description never touches the Unreleased
  section — its notes belong to the next release.
- Cutting the *current* version is allowed only while it is untagged (the
  first cut of a pre-bumped version).
- The script commits **all** pending changes with the release (that is the
  release-cut commit), so run it with the work being released in place.

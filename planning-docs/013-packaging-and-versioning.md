# 013 — Packaging & Versioning

**Status**: Completed — shipped: pyproject 0.2.0 + hygiene, `--version`, CHANGELOG, release.yml, /publish (T1–T5, T8 done). Renamed across the board to `agentic-dev-loop`: distribution, CLI, repo, shipped example dir/trigger script, and Python import (`agent_engine` → `agentic_dev_loop`). Outstanding: T6 cut v0.2.0 + T7 verify, after the §7 one-time PyPI/GitHub setup.
**Date**: 2026-10-19
**Trigger**: User — "Before we implement unit 3, we should do proper packaging and versioning. The current version (without kernel-level sandboxing) is v0.x.x, and a proper v1 has the kernel-level sandboxing (unit 3)."

## 1. Decisions (confirmed with user)

| # | Question | Decision |
| --- | --- | --- |
| D1 | Version for the current pre-sandbox state | **v0.2.0** (pyproject bumped 0.1.0 → 0.2.0; 0.1.0 predates units 1+2 and was never tagged). User initially picked "tag as-is 0.1.0", then revised to 0.2.0. |
| D2 | Distribution channel | **PyPI + GitHub Releases** — publish via OpenID-connect trusted publishing from a tag-triggered GitHub Actions workflow; GitHub Releases carry the changelog. |
| D3 | v1 release shape | **v1.0.0-rc.1 first** at unit-3 green, promoted to **v1.0.0** after a soak period. |
| D4 | Machinery scope | **Full** — pyproject metadata hygiene + CHANGELOG.md + `--version` CLI flag + tag-triggered CI release workflow. Ships now, not waiting for unit-3 CI. |

## 2. The versioning scheme

**Semantic Versioning, with the unit-3 boundary as the 0.x → 1.0 line.**

| Version | Meaning | When |
| --- | --- | --- |
| `v0.2.0` | Units 1+2 complete (output-passing fix, file-tool removal, SDK hardening); **no kernel-level sandboxing** | Now — current `main` |
| `v1.0.0-rc.1` | Unit 3 (kernel-level sandboxing, always-on) green — Build and Test passing | Cut at unit-3 completion |
| `v1.0.0-rc.N` | Fixes found during soak | As needed |
| `v1.0.0` | RC soak passed | Promotion commit after soak |
| `v1.x.y` | Post-1.0 semver: breaking changes → 2.0.0, features → minor, fixes → patch | Ongoing |

**Rationale for the boundary** (user's framing): kernel-level sandboxing is the defining capability of "real" v1 — the guardrail that makes the engine safe to point at untrusted work. Everything before it is an experimental line (`0.x`) where minor bumps may break behaviour. Under semver, `0.2.0` accurately signals "0.1.0 semantics are gone" (file_editor removed, tool surface locked to `tools:`, subprocess hardening).

**Version lifecycle on `main`**:
- After the `v0.2.0` tag, `pyproject` stays at `0.2.0` while unit-3 development runs. No dev-suffix churn (`1.0.0rc1.dev0` etc.) — the version only moves in release-cut commits.
- Release-cut commit = version bump in `pyproject.toml` + CHANGELOG entry in the **same commit**, tagged immediately after.
- During the RC soak, `main` stays at `1.0.0rc1`; each fix shipped during soak becomes `rc.2`, `rc.3`, … until promotion.

**PEP 440 note**: the canonical string for the RC is `1.0.0rc1`, and that form is used **everywhere mechanical** — `pyproject.toml`, the CHANGELOG heading (`## [1.0.0rc1]`), and the git tag (`v1.0.0rc1`). `tools/publish.py` rejects non-canonical input (`1.0.0-rc.1` → suggests `1.0.0rc1`), and `release.yml`'s release-notes extraction keys on the tag minus `v`, so the tag and the changelog heading must match exactly — the tag cannot be cosmetic while the heading is canonical. The human-facing plan language (`v1.0.0-rc.1`) and the mechanical string (`v1.0.0rc1`) refer to the same release.

**Soak criteria** (proposed, adjustable at the time): `v1.0.0-rc.1` is promoted when it has driven ≥ 2 real pipelines — the shipped self-loop demo plus at least one real repo pipeline — across ≥ 3 working days with **no blocker-level sandbox failures** (isolation escape, fail-fast-not-firing, platform breakage). Fixes during soak → next RC; promotion commit bumps to `1.0.0` on the then-current `main`.

**PyPI immutability**: a version string, once published, can never be republished. Therefore `release.yml` runs the full test suite *before* building/publishing (below), and tags are only pushed after tests are green locally.

## 3. Single source of truth for the version

- `[project] version` in `pyproject.toml` is the **only** place the version is written.
- Runtime reads it via `importlib.metadata.version("agentic-dev-loop")` — verified working with the local editable install (resolves `0.1.0` today).
- **No** `__version__` constant in `src/agentic_dev_loop/__init__.py` — dual sources drift (this repo has been burned by silent staleness before; don't invite it).
- If metadata is unavailable (running from a source checkout that was never installed), fail **loudly**: print a clear error naming the problem ("agentic-dev-loop is not installed — version unavailable; run `pip install -e .`"). No silent fallback to a hard-coded string.

**`--version` flag** (new, TDD per repo rule — red/green/refactor):
- `agentic-dev-loop --version` prints `agentic-dev-loop X.Y.Z` from metadata.
- Landed via `tests/test_cli.py` additions first (red), then the argparse wiring in `src/agentic_dev_loop/cli.py` (`_core_parser` / probe parser so it works even before config resolution), then refactor.
- No mocks: `importlib.metadata` is a local call against the installed distribution.

## 4. Packaging hygiene (pyproject.toml)

Current gaps (verified against `pyproject.toml`):

| Fix | Detail |
| --- | --- |
| `readme = "README.md"` | Confirmed (user) — use the existing `README.md`. Missing today, so the package has no long description on PyPI. |
| `license = "Apache-2.0"` | Confirmed (user). Repo `LICENSE` is Apache-2.0. PEP 639 SPDX string form requires `setuptools >= 77` — bump `[build-system] requires` from `setuptools>=68` accordingly. |
| `authors = [{ name = "Luke Wilson" }]` | Confirmed (user) — name resolved from GitHub profile `lukedawilson`. No public email on the profile; PEP 621 email is optional, so publish name-only unless the user wants an address listed (§10). |
| `[project.urls]` | Confirmed (user) — homepage only for now: `Homepage = "https://github.com/lukedawilson/agentic-dev-loop"`. No Issues URL yet. |
| `classifiers` | Full proposed list in §4.1. |
| requires-python consistency | `pyproject` says `>=3.12`; **README says "≥ 3.11"** — README is wrong. `openhands-sdk 1.17.0` itself declares `Requires-Python: >=3.12`, so `>=3.12` is correct. Fix the README line. |
| Build artifacts | `src/agent_engine.egg-info/`, `dist/`, `build/` already gitignored — nothing to do, but confirmed clean. |

### 4.1 Proposed classifier list

Trove classifiers (ordered by convention; rationale in brackets; verified against the canonical `pypa/trove-classifiers` list on 2026-10-19):

```toml
classifiers = [
    "Development Status :: 4 - Beta",                     # 0.2.0: solid, tested, but the defining v1 capability (kernel sandbox) is missing
    "Environment :: Console",                              # CLI-driven: `agentic-dev-loop` console script
    "Intended Audience :: Developers",
    "Operating System :: MacOS",                           # unit-3 FR-2.4 targets all three
    "Operating System :: Microsoft :: Windows",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",         # no Python 2
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",  # LLM agents execute the steps — the only AI trove classifier that exists (no agent/agentic/LLM/LangChain/MCP classifiers); the LangChain ecosystem publishes under this one
    "Topic :: Software Development",
    "Topic :: Software Development :: Libraries :: Python Modules", # it is an importable library, not an application
    "Topic :: Software Development :: Quality Assurance",  # review/qa verdict agents + test gate are the product's core loop
    "Topic :: Security",                                   # kernel-level sandboxing of untrusted agent code is the defining v1 capability — security is a first-class topic here
    "Typing :: Typed",                                     # ships py.typed
]
```

Checked and rejected: `Topic :: Software Development :: Build Tools` (compile-flavoured), `Topic :: Software Development :: Code Generators` (the engine doesn't generate code), `Topic :: Software Development :: Testing` (too narrow — implies a test tool; Quality Assurance covers the verdict-gate story), `Topic :: Security :: Cryptography` (no crypto anywhere in the product), `Framework :: Robot Framework :: Tool` (framework-specific), `Topic :: Utilities` (vague).

Notes:
- `Development Status` bumps to `5 - Production/Stable` in the `1.0.0` release-cut commit, not before.
- No `License ::` classifier: with the `setuptools >= 77` floor (§4), setuptools treats any `License ::` classifier as superseded by the PEP 639 `license = "Apache-2.0"` field and rejects the build (`InvalidConfigError`). The SPDX expression field alone is the single source of license truth.
- Python 3.12–3.14 match the local venv (3.12.13) and system interpreters actually used (3.14.8).

Out of scope: moving off setuptools (no benefit at this size), `py.typed` handling (already shipped), dependency changes (none needed for packaging).

## 5. CHANGELOG.md

New file, [Keep a Changelog](https://keepachangelog.com/) format, sections:

- `[Unreleased]` — unit-3 work in progress.
- `[0.2.0]` — 2026-10-19: unit-1 + unit-2 summaries. Content pulled from the unit-of-work definitions (captured-response artifacts replace agent file-writes; `file_editor` removed; `tools:` as sole capability allowlist; `task_tracker` instruction removed; command/action subprocess argv hardening; extension tool-registration validation; `env_allowlist`). **Changed** items phrased as behaviour changes, since 0.x minors may break.
- Future: `[1.0.0-rc.1]` (kernel-level sandboxing: always-on Docker backend, fail-fast, host-side commit unchanged), `[1.0.0]` (promotion), etc.

Release workflow extracts the top changelog section for the GitHub Release body (see §6), so changelog and release notes can't diverge.

## 6. Release workflow — `.github/workflows/release.yml`

This is the **repo's first workflow** (no `.github/` exists today). It lands before unit-3's `ci.yml` / `publish-image.yml`; they coexist without overlap — `release.yml` is the only tag-triggered, publishing workflow.

```
on:
  push:
    tags: ["v*"]
permissions:
  contents: write        # GitHub Release creation
  id-token: write        # PyPI trusted publishing
jobs:
  test:                  # guard rail: never publish a broken tag
    runs-on: ubuntu-latest
    - checkout, setup-python 3.12, pip install -e ".[dev]"
    - run: pytest tests/ -q          # pure suite; no Docker needed
  release:
    needs: test
    runs-on: ubuntu-latest
    environment: pypi    # protected environment, manual approval optional
    - build sdist + wheel      (python -m build)
    - publish to PyPI          (pypa/gh-action-pypi-publish, OIDC trusted publishing)
    - create GitHub Release    (softprops/action-gh-release) with the
                               CHANGELOG section for the tag as the body
```

Design notes:

- **Tag → verify → build → publish → release**, strictly ordered. Test failure aborts before anything is published.
- **Trusted publishing, zero secrets in the repo**: PyPI authorises the `release.yml` workflow + repo via OIDC. No API token ever touches GitHub.
- **`environment: pypi`**: a GitHub deployment environment so PyPI publishing can be gated (and later: required reviewers) without touching the build.
- **Fail loud on publish failure** (repo rule — no silent fallbacks): a failed publish job is red, the tag is *not* silently re-published, and the run is retried via `workflow_dispatch` (PyPI forbids re-uploading the same version, so the retry only succeeds if the first attempt never actually uploaded).
- Tags are annotated (`git tag -a v0.2.0 -m "…"`); signing is the user's call (see open items).
- Single `ubuntu-latest` runner is right for a packaging workflow; the platform matrix lives in unit-3's `ci.yml`, not here.

### 6.1 Release-chain security (tag → PyPI is a trust boundary)

For a product whose v1 headline is sandboxing, the release pipeline itself is attack surface. Hardening folded into the design:

- **PEP 740 attestations**: the publish step runs `pypa/gh-action-pypi-publish` with `attestations: true`, so PyPI records signed build provenance for the wheel/sdist. Downstream `pip` verifies artifacts came from this repo's CI, not a compromised upload.
- **Build provenance on the GitHub Release**: the build job enables GitHub artifact attestation (`actions/attest-build-provenance`), so release assets carry the same provenance story on the GitHub side.
- **Tag protection on GitHub**: a `v*` tag protection rule (Settings → Rules) so release tags cannot be deleted or force-pushed. The tag is the publish trigger — a retargetable tag is a retargetable release.
- **PyPI account hardening**: 2FA on the PyPI account (already mandatory for accounts managing projects/trusted publishers).
- **Out of scope**: code signing beyond PEP 740 (no GPG-key infrastructure worth standing up for a first release), dependency pinning (§11).

## 7. One-time manual setup (user, before the first tag push)

1. PyPI account (user) + the `agentic-dev-loop` project name — confirmed free (PyPI JSON API 404s on `agentic-dev-loop`).
2. On PyPI: add a **pending trusted publisher** — owner `lukedawilson`, repository `agentic-dev-loop`, workflow `release.yml`, environment `pypi`.
3. On GitHub: create the `pypi` deployment environment (Settings → Environments), initially with no required reviewers.
4. On GitHub: add the `v*` tag protection rule (§6.1) before pushing the first tag.

After that, every `v*` tag push publishes automatically.

## 8. Ordered task list (side-quest — all before unit-3 Code Generation)

| # | Task | Code? |
| --- | --- | --- |
| T1 | Commit the pending unit-3 design docs currently in the working tree (`aidlc-docs/…` modified/untracked) so the tag lands on a clean history | docs |
| T2 | pyproject hygiene + version bump `0.1.0 → 0.2.0` (all §4 items) + README requires-python fix | config |
| T3 | `--version` flag — TDD via `tests/test_cli.py`, then `cli.py` wiring (§3) | **yes** |
| T4 | `CHANGELOG.md` with `[Unreleased]` + `[0.2.0]` | docs |
| T5 | `.github/workflows/release.yml` (§6) | config |
| T6 | Commit T2–T5, annotate `v0.2.0`, push → CI publishes `agentic-dev-loop 0.2.0` to PyPI + creates the first GitHub Release | — |
| T7 | Verify: `pip install agentic-dev-loop` in a clean venv; `agentic-dev-loop --version`; PyPI page renders README/licence/classifiers; GitHub Release body = changelog. Rebuild wheels from a **clean tree** (`rm -rf build dist *.egg-info` first — setuptools reuses stale `build/lib` and ships old package dirs in the wheel; caught in practice during the import rename) | — |
| T8 | Implement `/publish` command — release-cut automation: `tools/publish.py` (version resolution, pyproject bump, changelog render, commit/tag/push, `--dry-run`) + `tests/test_publish.py` (22 subprocess-git tests) + `.opencode/commands/publish.md` | **yes** ✅ done |

Then unit-3 Code Generation proceeds with no further versioning work until its release-cut commit (bump to `1.0.0rc1` + changelog + tag `v1.0.0rc1` at Build-and-Test green).

## 9. Integration with unit 3

- Unit-3 CI (`ci.yml`, `publish-image.yml`) and `release.yml` coexist; a release-cut tag triggers only `release.yml`. No workflow changes needed in unit 3.
- `construction/shared-infrastructure.md` already speaks of "engine-version floors" for the dev image — unchanged by this plan, but release-cut commits are the natural place to bump the image digest constant when a toolchain change rides with the release (same-commit rule already recorded there).
- The `1.0.0rc1` release-cut commit is part of unit-3's completion ceremony: green suite → version bump + changelog → tag → publish → **soak begins** (Build and Test stage, then soak, then `1.0.0` promotion).

## 10. Open items

- **Author email** (optional): metadata will publish as `Luke Wilson` (name-only). If an email should appear on PyPI, supply it before the first publish — changing it later means editing future releases only (old release files keep the old metadata).
- **Tag signing**: annotated tags are settled; whether to sign (GPG/SSH) with the user's existing key setup — trivial either way.
- **Unit 4 overlap**: if the Claude Code backend unit lands during the v1.0.0-rc soak, decide then whether it rides inside `v1.0.0` (releasing more than "v1 = kernel sandboxing") or waits for `v1.1.0`. Noted, not decided — it doesn't block this side-quest.
- Soak criteria in §2 are proposed defaults; adjust at RC cut time.

## 11. Out of scope

- Anything AI-DLC-tracked (unit-3 design docs, `aidlc-state.md`, audit trail) — this side-quest lives only here in `planning-docs/`.
- Repo renames, setuptools replacement, dependency bumps, dev-container tooling.
- Publishing machinery for unit-3's Docker dev image (`publish-image.yml` — already designed in unit-3 Infrastructure Design).

# Plan: `--dry-run` pipeline validation flag

> **Status: COMPLETED** (2026-10-23) — shipped; --dry-run implemented (engine/cli.py + engine/dryrun.py).

## Goal

Add a `--dry-run` flag to the `agentic-dev-loop` CLI that performs the full
pipeline load-and-validate pass without executing anything, and prints a
summary plan.

## Behaviour

When `--dry-run` is given:

1. Everything short of execution runs: pipeline YAML parse, step config
   validation (kinds, exclusivity, params), extension loading (including the
   ai-dlc and plan document loaders), agents_dir / verdicts / routing-target
   resolution, isolation config validation, image-ref resolution (pure — no
   Docker calls).
2. Print a human-readable summary: pipeline path, subject, resolved document
   loader + docs, per-step: kind and key params, isolation: resolved image
   ref + backend + memory/cpus + state_dir, and a final
   `dry run complete — nothing executed` line.
3. No LLM calls (no agent instantiation), no Docker daemon contact, no
   state/checkpoint/viz writes, no sandbox container.
4. Exit 0 if the pipeline loads and validates; exit 1 with the existing loud
   error for any load failure.
5. Does NOT require OPENAI_API_KEY (no LLM is touched).

## Acceptance criteria (TDD — red/green/refactor)

- Tests in `tests/` using real tmp-dir fixtures. No mocks for file I/O or
  pure functions (repo policy); network boundaries are the only allowed
  mocks and none are needed here.
- Valid pipeline + `--dry-run`: exit 0, summary contains the subject, the
  step names, and the resolved image ref; assert NO state files are created
  and the run works with OPENAI_API_KEY stripped from the subprocess env.
- Broken pipelines fail with exit 1 and the existing error, for each of:
  (a) invalid YAML; (b) a missing agent file referenced by agents_dir;
  (c) a routing target that does not exist; (d) isolation `image: ""`
  (explicit) → AE-SBX-005 fail-fast.
- `--help` documents `--dry-run`; README CLI section updated.
- Full non-docker suite stays green (currently 582 passed). The
  docker-marked tests are unaffected — do not run or modify them.

## Out of scope

- No changes to isolation.py, agents.py, step execution, the release
  workflow, or packaging. No /publish. No Docker calls in the feature
  itself.

## Conventions

- TDD (red first), loud errors, no silent fallbacks. Keep style consistent
  with cli.py (argparse, `_core_parser`).
- The flag must compose with existing flags: `--no-viz`, `--resume`,
  `--refresh` etc. are simply irrelevant during a dry run.

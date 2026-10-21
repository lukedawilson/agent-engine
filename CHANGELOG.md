# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- feat: unit-4 Claude Dynamic Workflows driver — hard module break: the flat
  `agentic_dev_loop` package splits into `core` (pipeline model + parse +
  workflow projection), `engine` (graph/stages/sandbox/CLI), and `viz`
  (live-graph server + workflow ingest). No re-export shims.
- feat: build-time workflow projection — `project_workflow`, prompt-reference
  validation, deterministic `render_workflow_js`, and the docker-free commit
  shim; skill payload (`/agentic-dev-loop`) ships in the wheel.
- feat: extras inversion — base install is `core` + `viz` (pydantic + PyYAML
  only); the heavy OpenHands-SDK engine moves to the `[engine]` extra
  (`[workflow]` is the base). The generated workflow JS is a real wheel-shipped
  template implementing the deterministic loop (routing, attempt counter,
  retry-note injection, clean-at-start, viz launch, gated commit), pinned by
  golden-render tests; `viz` is now stdlib-only (no LangChain renderer).

### Migration (breaking)

- `agentic_dev_loop.config` → `agentic_dev_loop.core.config`
- `agentic_dev_loop.results` → `agentic_dev_loop.core.results`
- `agentic_dev_loop.outputs` → `agentic_dev_loop.engine.outputs`
  (`Verdict`/`VerdictError` → `agentic_dev_loop.core.verdict`)
- `agentic_dev_loop.viz` → `agentic_dev_loop.viz` (now a package; the
  `viz.py` module moved to `viz.server`)
- `agentic_dev_loop.{graph,stages,isolation,cli,llm,actions,agents,registry,loaders,proc,dryrun}` → `agentic_dev_loop.engine.*`
- `agentic_dev_loop.extensions.aidlc` → `agentic_dev_loop.engine.extensions.aidlc`
  (update the `extensions:` string in your pipeline.yaml)


## [1.0.0a5] - 2026-10-20

### Changed

- fix: load extensions once across parse, dry-run, and run
- Add dev-dotnet sandbox image: dotnet 10.0.402 + jq/unzip/lsof for dotnet pipelines

## [1.0.0a4] - 2026-10-20

### Changed

- fix: harden sandbox request VO and kernel-proof network-none test
- feat: construct plan 014-per-stage-networking.md (agent dev loop)

## [1.0.0a3] - 2026-10-20

### Changed

- docs: plan per-stage networking (014)
- fix: cap agent-client-protocol below 1.0.0 — its rc drops acp.helpers
- Fix opencode publish command double-cutting

## [1.0.0rc1] - 2026-10-20

### Changed

- Update tagline

## [1.0.0a2] - 2026-10-20

### Changed

- feat: construct plan 015-container-lifecycle-rm-fix.md (agent dev loop)
- docs: plan 015 — container lifecycle --rm cleanup fix

## [1.0.0a1] - 2026-10-20

### Changed

- feat: construct plan 014-dry-run-flag-plan.md (agent dev loop)
- fix: sandbox HOME=/tmp for host-user containers (root's home is unwritable)
- ci: run docker integration tests on Linux only (Windows runners have no Docker daemon)
- test: skip POSIX-only killpg test on Windows
- fix: close the six Windows-CI failures from the unit-3 dogfood run
- fix: make product and suite Windows-CI green; run sandbox as host user
- fix: re-pin dev image digest after multi-arch rebuild (amd64+arm64)
- ci: build the dev image for linux/amd64 and linux/arm64
- docs: plan --dry-run validation flag (unit-3 dogfood)
- fix: pin published dev-image digest (KD-2)
- feat: construct unit unit-3 (agent dev loop)

## [0.3.0] - 2026-10-19

### Changed

- refactor: match --aidlc-unit slugs verbatim against unit dirs; drop mangling
- Unit 3 docs fixes
- test: pin test imports to the working tree src/ (dogfood-safe)

## [0.2.0] - 2026-10-19

### Added

- `env_allowlist` pipeline config to extend the whitelisted child-process
  environment.

### Changed

- Distribution renamed from `agent-engine` to `agentic-dev-loop`; the CLI
  command renamed from `agent-engine` to `agentic-dev-loop`, the shipped
  example-pipeline directory and trigger script renamed to match, and the
  Python import renamed from `agent_engine` to `agentic_dev_loop`.
- Agent steps now capture the agent's final response as the pipeline feedback
  channel; agents no longer write artifacts through `file_editor` (the tool
  was removed).
- `tools:` is now the sole capability allowlist for agent steps; an unknown
  tool name fails to load.
- The `task_tracker` instruction was removed from the shipped `dev` agent
  definition.
- Command and action steps run subprocesses with hardened argv handling (no
  implicit shell, explicit `shell=False`) and a whitelisted child environment.
- Extension tool registration validates a non-empty identifier and rejects
  collisions with SDK-registered tools.


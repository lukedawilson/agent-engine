# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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


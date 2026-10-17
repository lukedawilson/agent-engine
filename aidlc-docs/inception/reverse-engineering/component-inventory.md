# Component Inventory

## Application Packages

- `agent_engine` (src/) - The pipeline engine library + CLI — config schema, graph, stages, agents, actions, registry, loaders, verdicts, viz.

## Infrastructure Packages

- None.

## Shared Packages

- `agent_engine.extensions.aidlc` - Bundled AI-DLC document loader extension (unit doc resolution + current-unit autodetect).
- `agent-engine/` (consumer example) - Shipped self-hosting pipeline (pipeline.yaml + sdk_agents/{dev,review,qa}.agent.md).

## Test Packages

- `tests/` - 16 pytest files covering every module (actions, agents, aidlc, cli, config, e2e fixtures, graph, llm, loaders, registry, sdk compat, stages, verdicts, viz) + conftest.py + sample_ext.py extension fixture.

## Tooling (repo-level, not part of the package)

- `.opencode/` - OpenCode agent/command/skill configuration (Builder/Planner/Readonly agents, 10 AI-DLC commands, 3 skills).
- `.aidlc/aidlc-rules/` - AWS AI-DLC ruleset v1.0.0.
- `aidlc-docs/` - AI-DLC working docs (state, audit, inception/construction artifacts).
- `tools/`, `apply-patches.sh`, `coding-standards-ddd.yaml` - workflow helpers.

## Total Count

- **Total Packages**: 3 (library core, bundled extension, consumer example)
- **Application**: 1
- **Infrastructure**: 0
- **Shared**: 2
- **Test**: 1

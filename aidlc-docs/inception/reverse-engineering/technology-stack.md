# Technology Stack

## Programming Languages

- Python - >=3.12 - entire codebase (src, tests, consumer).

## Frameworks

- LangGraph - >=1.2 - cyclic state graph, routing, retries.
- langgraph-checkpoint-sqlite - >=3.0 - crash-safe checkpoint/resume.
- Pydantic - >=2.0 - strict config schema.
- OpenHands SDK - ~=1.17.0 - agent runtime (LLM, Agent, Conversation, tool registry).
- openhands-tools - ~=1.17.0 - terminal / file_editor / task_tracker tools.

## Infrastructure

- SQLite - loop-checkpoints.sqlite under state_dir (one per workspace).
- LLM provider (DeepSeek, OpenAI-compatible HTTP API) - configured per pipeline.

## Build Tools

- setuptools - >=68 - packaging; console script `agent-engine`.
- pip - editable install (`pip install -e .`).

## Testing Tools

- pytest - test suite (16 files), run mechanically by the pipeline's `test` command step.

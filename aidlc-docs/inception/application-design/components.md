# Components - Guardrails & Sandboxing

High-level component definitions. Business rules are detailed later in Functional Design.

## New Components

| Component | Purpose | Responsibilities | Interfaces |
| --- | --- | --- | --- |
| **Outputs** (`src/agent_engine/outputs.py`) | Feedback domain: everything about what an agent run produces and how it is interpreted (Unit 1) | Capture the agent's final SDK response; write it to the step's artifact path; parse verdicts from captured text | `CapturedOutput.from_agent_result(result, step, state_dir)` - constructing static method (VO, per DDD descent); `Verdict.from_text(text) -> Result[Verdict]` - pure, typed result object |
| **Isolation** (`src/agent_engine/isolation.py`) | Sandbox execution domain (Unit 3, opt-in) | Probe availability; run commands inside the boundary; adapt the Docker Engine API | `Sandbox` - **single concrete type** (no protocol: single-impl interfaces forbidden). `Sandbox.for_config(config)` (fail-fast when unavailable), `Sandbox.available() -> bool`, `Sandbox.run(request) -> SandboxExecutionResult`. Platform variance (daemon detection, mount translation, CRLF) is **internal behavior**. A shared interface is extracted only when a second backend (e.g. native Linux namespaces) is actually implemented |

## Modified Components

| Component | Purpose | Change |
| --- | --- | --- |
| **Stages Runtime** (`stages.py`) | Execute agent/command/action steps; build context; manage attempts | Unit 1: `run_agent` delegates capture to Outputs (agent no longer writes reports; `file_editor` dropped). Unit 3: terminal-tool and command-step execution routes through `Sandbox` when isolation is enabled |
| **Agents** (`agents.py`) | Load `.agent.md` definitions; register SDK tools | Unit 2: wire frontmatter `tools`/`filter_tools_regex`/`include_default_tools` through the SDK factory; fail fast on unknown tool names (already true) |
| **Registry** (`registry.py`) | Extension surface: actions, tools, document loaders | Unit 2: validate tool names at registration - collision detection against built-ins/other extensions, reserved-name rejection |
| **Pipeline Config** (`config.py`) | Strict YAML schema (`extra=forbid`) | Unit 3: opt-in isolation config fields (no change to existing fields; default = no isolation) |

## Unchanged Components

| Component | Purpose |
| --- | --- |
| **Graph** (`graph.py`) | `LoopState`, `build_graph`, `run_pipeline`, SQLite checkpoints, resume |
| **Actions** (`actions.py`) | Built-in `commit` (single point, clean-worktree gate), `kill_listeners_on_port` |
| **Loaders** (`loaders.py`) | `PlanDocumentLoader`, loader selection, zero-docs fail-fast |
| **LLM** (`llm.py`) | `build_llm`, fail-fast secrets, SDK compat shims |
| **Viz** (`viz.py`) | VizBus, localhost server, console capture |
| **AidlcExtension** (`extensions/aidlc.py`) | AI-DLC unit autodetection + document loading |

## Domain Objects (values & entities)

| Type | Kind | Notes |
| --- | --- | --- |
| `Verdict` | Value object | Kinds: PASS / FAIL / APPROVED / NEEDS CHANGES; `from_text` returns `Result[Verdict]` - UNCLEAR/ambiguous is an expected condition, not an exception |
| `CapturedOutput` | Value object | Raw text, artifact path, parsed verdict result; constructs itself from an agent result (static method) and handles its own artifact persistence |
| `Step` | Entity | Exactly-one-kind step with routing rules, artifact declarations, caps |
| `Attempt` | Entity | Attempt number, accumulated notes, exhaustion check |
| `AgentDefinition` | Entity | Frontmatter-derived; invariant: tool names ⊆ known tools |
| `ToolRegistry` | Entity | Invariant: unique tool names |
| `SandboxExecutionRequest` / `Result` | Value objects | Command, env, mounts, cwd, timeout → exit code, stdout/stderr, timed-out |
| `Sandbox` | Value object (concrete, no protocol) | Docker Engine API adapter; platform detection/mount translation internal |

No persistence abstractions (no Repository/DAO types) - entities handle their own artifact persistence inside `state_dir`, as today.

## Requirements Traceability

| Requirement | Component |
| --- | --- |
| FR-1.2 / FR-1.3 | Outputs, Stages Runtime, Agents (file_editor removal) |
| FR-1.4 | Agents (task_tracker fix), shipped `.agent.md` files |
| FR-1.5 / FR-1.6 | Stages Runtime, Actions (subprocess hardening) |
| FR-1.7 | Registry (tool-name validation) |
| FR-2.1..2.6 | Isolation (`Sandbox`), Stages Runtime, Pipeline Config |

# Component Methods — Guardrails & Sandboxing

Method signatures with high-level purpose and I/O types. Detailed business rules (parsing algorithm, timeout semantics, verdict precedence) are defined in Functional Design.

## Outputs (new)

| Method | Purpose | Input | Output |
| --- | --- | --- | --- |
| `CapturedOutput.from_agent_result(result, step, state_dir)` | Construct from an agent run: capture final response, write the artifact, parse the verdict — one constructing static method (VO owns the operation; no service wrapper) | `result` (SDK agent result), `step` (Step), `state_dir` (Path) | `CapturedOutput` — artifact written to the step's path as a side effect |
| `Verdict.from_text(text)` | Parse a verdict from arbitrary text (pure, source-agnostic) | `text` (str) | `Result[Verdict]` — typed error code (`NO_VERDICT`, `AMBIGUOUS`) on expected failure; never raises for expected conditions |
| `CapturedOutput.write(path)` | Persist the captured text to its artifact path | `path` (Path) | `Result[None]` — typed error on write failure |

## Isolation (new)

| Method | Purpose | Input | Output |
| --- | --- | --- | --- |
| `Sandbox.for_config(config)` | Resolve the sandbox for the current config; **fail fast** when isolation is requested but no usable runtime exists | isolation config section | `Sandbox` — raises (startup misconfiguration policy) |
| `Sandbox.available()` | Probe whether the Docker Engine API is reachable now | None | `bool` |
| `Sandbox.run(request)` | Execute one command inside the boundary (create/exec/remove container, bind mounts, path translation) | `SandboxExecutionRequest` (command, env, mounts, cwd, timeout) | `SandboxExecutionResult` (exit code, stdout, stderr, timed_out) |
| `Sandbox.detect_socket()` (internal) | Platform daemon detection: unix socket / npipe+WSL2 / `DOCKER_HOST` | None | socket address — internal behavior, not an interface |
| `Sandbox.translate_mount(host_path)` (internal) | Windows mount-path translation (`C:\repo`→`/c/repo`), CRLF/permission handling | host path | container path — internal behavior |

## Stages Runtime (modified)

| Method | Purpose | Change |
| --- | --- | --- |
| `run_agent(runtime, step, state)` | Run an agent step | Delegates capture to `CapturedOutput.from_agent_result`; agent tools no longer include file-writing tools |
| `_run_command(runtime, step, state)` | Run a command step | Routes through `Sandbox.run` when isolation enabled; argv-list invocation where possible |
| `build_context(runtime, step, state)` | Assemble docs + expected outputs for an agent | Unchanged contract — reads pipeline-written artifacts |
| `clear_attempt_artifacts(runtime, step, state)` | Per-attempt artifact hygiene | Unchanged |

## Agents (modified)

| Method | Purpose | Change |
| --- | --- | --- |
| `load_agent(name, base_dir)` | Load `.agent.md` → SDK agent | Wires `tools` / `filter_tools_regex` / `include_default_tools` from frontmatter; fail-fast unknown names |
| `register_builtin_tools()` | Register terminal/file_editor/task_tracker with the SDK registry | `file_editor` no longer granted to shipped agents |

## Registry (modified)

| Method | Purpose | Change |
| --- | --- | --- |
| `Registry.add_tool(name, tool)` | Register an extension tool | Validates name: not a built-in, not already registered, not reserved |

## Pipeline Config (modified)

| Method | Purpose | Change |
| --- | --- | --- |
| `PipelineConfig` / `StepConfig` / `LlmConfig` validators | Strict schema enforcement | Adds opt-in isolation section; existing fields untouched |

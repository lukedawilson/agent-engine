# Tech Stack Decisions - unit-2 (SDK-level hardening)

## Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| TS-1 | **No new runtime dependencies** | `shlex`, `shutil`, `os`, `re` are stdlib; tool-name validation and pid validation need nothing beyond them. `pydantic` (existing dep) types the new optional config key. |
| TS-2 | **Subprocess env hygiene**: fixed known-safe whitelist + `llm.api_key_env` (included by default) + author-extensible `env_allowlist` (NFR-1 answer C) | Whitelist + default key + explicit allowlist keep legitimate inherited-var use possible without a full passthrough; everything else excluded. |
| TS-3 | **New pure-function module**: `src/agent_engine/proc.py` (`needs_shell`, `split_command`, `is_pid_token`, `child_env`) | Stateless helpers shared by the command-step (`stages.py`) and action-step (`actions.py`) surfaces - a module, not a service (DDD descent step 0). |
| TS-4 | **Tool-name validation location**: `Registry.add_tool` (registry.py) | Registration is the entity's own invariant; validates against the SDK's `list_registered_tools()` before `register_tool`. |
| TS-5 | **Binary resolution**: `shutil.which("git"/"lsof"/"ps"/"kill")` | Absolute-path resolution at call time; a missing binary keeps the existing fail-safe contract (positive-only attribution, loud warning). |
| TS-6 | **Env-allowlist config key**: new optional `PipelineConfig` field `env_allowlist: list[str] = []` | Optional + additive - existing pipelines load unchanged (NFR-1/NFR-2.5). The LLM key is added automatically regardless of this list. |

## Deferred (out of unit-2)

| Item | Deferred to |
| --- | --- |
| Sandboxing the agent `terminal` tool + command steps in a container | unit-3 (FR-2.x) |
| Reusing `child_env` inside the sandbox boundary | unit-3 (FR-2.1) |
| `Result` reuse by Sandbox execution results | unit-3 |

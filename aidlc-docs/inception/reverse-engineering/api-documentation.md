# API Documentation

## REST APIs

None - agent-engine is a library + CLI with no server API. The only network surface is the localhost-only live viz HTTP server (127.0.0.1, default port 8321, ephemeral, no public endpoints documented).

## Internal APIs

### run_pipeline(cfg_path, args, *, viz_bus=None) → tuple[bool, int]
- **Signature**: `run_pipeline(cfg_path: str | Path, args: argparse.Namespace, *, viz_bus=None) -> tuple[bool, int]`
- **Parameters**: `cfg_path` - pipeline YAML path; `args` - parsed CLI namespace (loader flags, --resume, --max-attempts, --no-viz); `viz_bus` - optional programmatic event bus.
- **Return Types**: `(success: bool, attempts: int)`.
- **Notes**: The public API (graph.py). Loads config, resolves docs via the selected loader (empty → fail fast), builds the graph with SqliteSaver, handles resume/hard-failure re-entry, wires viz, returns outcome.

### load_agent(agents_dir, name, llm) → Agent
- **Signature**: `load_agent(agents_dir: Path | str, name: str, llm: LLM) -> Agent`
- **Parameters**: `agents_dir` - directory holding `<name>.agent.md`; `name` - agent name; `llm` - built LLM.
- **Return Types**: SDK `Agent`.
- **Notes**: File must exist (fail fast); frontmatter name must equal filename stem; frontmatter `tools:` names resolved against the SDK global registry (unknown → ValueError).

### run_agent(agent_name, message, runtime, max_iterations=500) → AgentResult
- **Signature**: `run_agent(agent_name: str, message: str, runtime: Runtime, max_iterations: int = DEFAULT_MAX_ITERATIONS) -> AgentResult`
- **Parameters**: `agent_name` - step's agent; `message` - shared attempt context; `runtime` - Runtime dataclass (cfg, registry, llm, resolved paths); `max_iterations` - turn cap.
- **Return Types**: `AgentResult(ok: bool, truncated: bool)`.
- **Notes**: Failures write `<state_dir>/last-error.md`; `truncated=True` when the run ended without FINISHED (turn cap or stuck detection).

### parse_verdict(text, verdicts) → str | None
- **Signature**: `parse_verdict(text: str, verdicts: dict[str, str]) -> str | None`
- **Parameters**: `text` - artifact content; `verdicts` - mapping e.g. `{pass_: "pass", fail: "fail"}`.
- **Return Types**: the mapped verdict, or None when unclear.
- **Notes**: LAST decoration-tolerant `VERDICT: X` line wins; caveat delimiters tolerated; negation inverts on two-key sets only.

### load_config(path) → PipelineConfig
- **Signature**: `load_config(path: Path) -> PipelineConfig`
- **Parameters**: `path` - YAML file.
- **Return Types**: validated `PipelineConfig`.
- **Notes**: strict at every level (extra="forbid"); every error names the step.

### build_llm(cfg) → LLM
- **Signature**: `build_llm(cfg: LlmConfig) -> LLM`
- **Parameters**: `cfg` - LlmConfig (model, base_url, api_key_env, timeout).
- **Return Types**: SDK `LLM`.
- **Notes**: missing api_key_env env var → RuntimeError naming it (no fallback).

### resolve_unit_docs(docs_dir, unit_id) → dict[str, str]
- **Signature**: `resolve_unit_docs(docs_dir: Path | str, unit_id: str) -> dict[str, str]`
- **Parameters**: `docs_dir` - aidlc-docs path; `unit_id` - any unambiguous spelling.
- **Return Types**: namespaced doc bundle (unit files, `inception/*`, `plans/unit-N-*-code-generation-plan.md`).
- **Notes**: ambiguous unit id → RuntimeError; no dir → FileNotFoundError; empty unit load → RuntimeError.

### get_current_unit(docs_dir) → str
- **Signature**: `get_current_unit(docs_dir: Path | str) -> str`
- **Parameters**: `docs_dir` - aidlc-docs path.
- **Return Types**: `"U<n>"` from the aidlc-state.md Current Stage line.

## Data Models

### PipelineConfig
- **Fields**: name, extensions (list), additional_files (list), llm (LlmConfig), state_dir (default ".pr"), max_attempts (default 3), agents_dir, steps (min 1).
- **Relationships**: contains LlmConfig + list[StepConfig].
- **Validation**: duplicate step names rejected; terminal names reserved; all route targets must exist.

### StepConfig
- **Fields**: name; agent | action | command (exactly one, non-empty); params; produces; artifact; verdicts (VerdictSpec); max_iterations; timeout (gt 0, command-only); on_pass; on_fail (RouteTarget).
- **Relationships**: artifact ↔ verdicts must appear together; produces and artifact mutually exclusive.
- **Validation**: command steps cannot carry artifact/verdicts/produces/params/max_iterations.

### LlmConfig
- **Fields**: model (required), base_url, api_key_env (required), timeout (None = no client-side timeout).
- **Validation**: strict.

### VerdictSpec / Route
- **VerdictSpec**: `{pass: <token>, fail: <token>}` (aliased from YAML keys pass/fail).
- **Route**: `{goto: str, retry: bool}` - retry consumes an attempt.

### LoopState (TypedDict)
- **Fields**: subject, docs, context, attempt, max_attempts, notes (append reducer), failed, failed_step, resume_target, outcome, commit_allowed, step_verdicts, retry_target, thread_id.

### Runtime (dataclass)
- **Fields**: cfg, registry, llm, agents_dir, state_dir, workspace (all resolved absolute paths).

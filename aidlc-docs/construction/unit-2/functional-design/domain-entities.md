# Domain Entities - unit-2 (SDK-level hardening)

Per DDD standards: descent audit applied. No new services; no new value objects; no persistence abstractions; behaviour lives at the lowest responsible level.

## Value Objects

**None introduced.** The unit's new behaviours are stateless pure functions over strings/mappings (tool names, command strings, pid tokens, environment mappings). A value object for any of these would be anaemic - a data holder with no behaviour - which the standards forbid. The pure functions are the design (descent step 0).

## New Module (pure functions, not a service)

### `proc` (NEW - `src/agent_engine/proc.py`, module of stateless helpers)

Shared by the command-step (FR-1.5) and action-step (FR-1.6) surfaces. A module, not a service - no state, no construction, no name after a technical role.

| Function | Signature | Notes |
| --- | --- | --- |
| `needs_shell` | `(command: str) -> bool` | True when the command carries shell metacharacters |
| `split_command` | `(command: str) -> list[str]` | `shlex.split`; called only when `needs_shell` is false |
| `is_pid_token` | `(token: str) -> bool` | Plain decimal integer check for lsof-derived pids |
| `child_env` | `(allowlist: list[str] \| None) -> dict[str, str]` | Fixed known-safe whitelist + `llm.api_key_env` (always) + author-extensible allowlist; all other vars excluded (NFR-1 = C) |

All four are pure - the PBT-02 targets.

## Modified Entities

### `Registry` (entity - modified, `src/agent_engine/registry.py`)

- `add_tool(name, tool)` now validates before delegating to the SDK: non-empty identifier (BR-3.1) and no collision with `list_registered_tools()` (BR-3.2, BR-3.3). The SDK's silent duplicate-overwrite is pre-empted (BR-3.4).

### `_run_command` (module function - modified, `src/agent_engine/stages.py`)

- Classifies the command via `needs_shell`; runs argv-style (`shell=False`) for simple commands, `shell=True` for complex ones; builds the child env via `child_env` (BR-4). Exit-code-is-the-verdict, timeout process-group kill, and `start_new_session=True` unchanged.

### Action helpers (module functions - modified, `src/agent_engine/actions.py`)

- `_git`, `_pid_cwd`, `_listening_pids`, `kill_listeners_on_port`: resolve `git`/`lsof`/`ps`/`kill` via `shutil.which`; validate pid tokens via `is_pid_token` before `kill`/`ps`; explicit `shell=False`; `child_env` scrubbing (BR-5). Positive-only attribution preserved (BR-5.5).

### `dev.agent.md` (agent definition - modified)

- WORKFLOW step 3 "create task tracker entries" removed; `tools: [terminal]` unchanged (BR-2).

## Descent Audit (Domain Validation)

| Behaviour | Placement | Step | Verdict |
| --- | --- | --- | --- |
| Detect shell metacharacters | `proc.needs_shell` | 0 static helper | Correct - pure predicate |
| Split simple command | `proc.split_command` | 0 static helper | Correct - pure function |
| Validate pid token | `proc.is_pid_token` | 0 static helper | Correct - pure predicate |
| Build scrubbed env | `proc.child_env` | 0 static helper | Correct - pure function |
| Validate tool name on register | `Registry.add_tool` | 2 method on existing entity | Correct - the registry owns its name invariant |
| Run a command safely | `_run_command` | 2 existing module orchestration point | Correct - one caller (`make_command_node`) |
| Resolve binary path | `shutil.which` (stdlib) | - | Correct - standard library, no wrapper |

No entity delegated to a helper; no new service; no single-implementation interface; no repository/DAO; no anaemic value object.

## Requirements Traceability

| FR | Covered by | Note |
| --- | --- | --- |
| FR-1.1 (tool surface) | BR-1; `load_agent` (unchanged mechanics, formalized + tested) | **Scope reduced by FD-2/FD-2b**: no `filter_tools_regex`, no `include_default_tools` frontmatter knob - `tools:` is the sole capability allowlist; FinishTool + ThinkTool stay as SDK-default infra. `requirements.md` FR-1.1 + `unit-of-work.md` "new frontmatter fields" wording to be amended accordingly. |
| FR-1.4 (task_tracker) | BR-2; `dev.agent.md` | Instruction dropped, not the tool |
| FR-1.5 (command shell) | BR-4; `proc` + `_run_command` | Hybrid argv/shell + env hygiene |
| FR-1.6 (action subprocess) | BR-5; `actions.py` helpers | pid validation + `shutil.which` + `shell=False` |
| FR-1.7 (tool registration) | BR-3; `Registry.add_tool` | Collision detection + reserved-name rejection at load |
| FR-1.8 / NFR-2 (fail-fast) | BR-6 | Loud errors, no silent degrade |
| NFR-1 (backward compat) | BR-7 | YAML unchanged; existing agent files unchanged |
| NFR-3 (security baseline) | BR-4.3 / BR-5.4 | least privilege + credential hygiene on host surfaces |
| NFR-6 (PBT partial) | PBT-02 in business-logic-model.md | pure-function properties |

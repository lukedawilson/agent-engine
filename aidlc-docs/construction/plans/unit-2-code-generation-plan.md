# Code Generation Plan - unit-2 (SDK-level hardening)

## Unit Context

| Item | Detail |
| --- | --- |
| Project type | Brownfield - modify existing files, never create duplicates |
| Requirements | FR-1.1 (tool-surface semantics, reduced), FR-1.4 (drop task_tracker instruction), FR-1.5 (hybrid shell), FR-1.6 (subprocess hardening), FR-1.7 (tool-registration validation), NFR-2.1 (env hygiene), NFR-2.4/PBT-02 |
| Dependencies | unit-1 landed (`Result`, `CapturedOutput`, `Verdict` live; capture path frozen). unit-3 consumes unit-2's `_run_command` shape + validated `ToolRegistry` |
| Files created | `src/agent_engine/proc.py`, `tests/test_proc.py`, `tests/test_proc_pbt.py` |
| Files modified | `src/agent_engine/registry.py`, `src/agent_engine/stages.py`, `src/agent_engine/actions.py`, `src/agent_engine/config.py`, `src/agent_engine/agents.py` (docstring only), `agent-engine/sdk_agents/dev.agent.md` (+ verify review/qa), tests |
| N/A steps | API layer (in-process library), Repository layer (DDD ban), Frontend, DB migrations, Deployment artifacts, Project-structure setup (brownfield) |

## Design decisions (from FD/NFR)

- **FR-1.1**: no new frontmatter fields, no regex. `tools:` stays the exact capability allowlist; FinishTool + ThinkTool are SDK-default infra. Code change = a test pinning the semantics + a `load_agent` docstring formalization. No `load_agent` logic change.
- **FR-1.4**: `dev.agent.md` drops the "create task tracker entries" WORKFLOW step; `tools: [terminal]` unchanged.
- **FR-1.5/1.6**: new pure-function module `proc` (`needs_shell`, `split_command`, `is_pid_token`, `child_env`). Command steps pass `api_key_env` + `env_allowlist` from config into `_run_command`; action steps call `child_env()` with the fixed whitelist only (they hold no config - git/lsof never need the LLM key).
- **FR-1.7**: `Registry.add_tool` validates a non-empty identifier + no collision with the SDK's `list_registered_tools()` before `register_tool`.
- **NFR-2.1**: `child_env` = fixed whitelist (`PATH`, `HOME`, `LANG`, `LC_ALL`, `TERM`) + the `llm.api_key_env` value (included by default) + `env_allowlist` extras. New optional `PipelineConfig.env_allowlist: list[str] = []`.

## TDD ordering

Repo policy: TDD (red → green → refactor). Pure functions and local utilities use real implementations (no mocks); subprocess is exercised with real simple commands (`echo`, `python -c`) and real `git`. SDK global tool registry is the real one.

## Steps

- [ ] **Step 1 - `proc.needs_shell` (red)** - `tests/test_proc.py`: metacharacter strings (`&&`, `|`, `;`, `>`, `$`, backtick) → True; plain word sequences → False
- [ ] **Step 2 - `proc.needs_shell` (green)** - implement `src/agent_engine/proc.py`; pass Step 1
- [ ] **Step 3 - `proc.split_command` (red/green)** - `shlex` split of a simple command to argv; verify it is only ever called when `needs_shell` is false (assert in the helper)
- [ ] **Step 4 - `proc.is_pid_token` (red/green)** - digit strings → True; `-9`, `1;rm`, ``, ` 123`, `12a` → False
- [ ] **Step 5 - `proc.child_env` (red/green)** - returns whitelist + `api_key_env` value + allowlist extras; excludes everything else (monkeypatch.setenv for controlled parent env)
- [ ] **Step 6 - PBT suite (PBT-02)** - `tests/test_proc_pbt.py` with Hypothesis: metacharacter detection, split/join round-trip, numeric-token gate, env-scrub property
- [ ] **Step 7 - `Registry.add_tool` validation (red/green)** - `tests/test_registry.py`: empty/whitespace name → ValueError; a name already in `list_registered_tools()` (e.g. `terminal`) → ValueError naming the collision; a fresh unique name → registers
- [ ] **Step 8 - `_run_command` hybrid (red/green)** - `tests/test_stages.py`: simple command runs argv-style and captures output; a shell command (`echo a && echo b`) runs via shell; both build the child env via `child_env` (api_key_env + env_allowlist threaded from config)
- [ ] **Step 9 - actions hardening (red/green)** - `tests/test_actions.py`: `_git`/`_pid_cwd`/`_listening_pids`/`kill_listeners_on_port` resolve binaries via `shutil.which`, filter lsof pid tokens through `is_pid_token`, explicit `shell=False`, `child_env()`
- [ ] **Step 10 - config `env_allowlist` (red/green)** - `tests/test_config.py`: `env_allowlist` optional, defaults `[]`, accepts a list of names; unknown/typed-wrong values reject (strict config)
- [ ] **Step 11 - FR-1.1 tool-surface test (red/green)** - `tests/test_agents.py`: an agent with `tools: []` builds with no capability tools (FinishTool/ThinkTool infra only); `tools: [unknown-name]` → fail fast (already true - pin it); docstring in `load_agent` formalizes BR-1
- [ ] **Step 12 - example agent definitions** - `dev.agent.md`: drop the "create task tracker entries" step (FR-1.4); verify `review.agent.md` + `qa.agent.md` `tools: [terminal]` remain valid under BR-1 (no change expected); all three must still build
- [ ] **Step 13 - full suite** - `pytest tests/ -q` green (incl. `test_e2e_fixtures.py`, `test_sdk_compat.py`)
- [ ] **Step 14 - documentation** - generate `aidlc-docs/construction/unit-2/code/` summaries (markdown only)

## Story Traceability

| Requirement | Steps |
| --- | --- |
| FR-1.1 (tool surface) | Step 11 (test + docstring), Step 12 (verify example agents) |
| FR-1.4 (task_tracker) | Step 12 |
| FR-1.5 (command shell) | Steps 1–5, 8 |
| FR-1.6 (action subprocess) | Steps 4–5, 9 |
| FR-1.7 (tool registration) | Step 7 |
| NFR-2.1 (env hygiene) | Steps 5, 8, 9, 10 |
| NFR-2.4 / PBT-02 | Step 6 |

---

## Note: Execution via the engine's dev loop (self-hosting)

- **Decision (2026-10-18)**: unit-2's code generation runs through the engine's own dev loop (`./trigger-agent-engine.sh --ai-dlc-unit U2`), not manual TDD by an assistant. This plan is the dev agent's build spec - the ai-dlc loader injects it (`plans/unit-2-*-code-generation-plan.md`) alongside the FD/NFR/infrastructure artifacts.
- **What the dev agent must do**: follow the 14 steps TDD (red → green → refactor), using `.venv-sandbox/bin/python -m pytest tests/ -q` as the local gate; the pipeline's mechanical `test` step is the authoritative green signal. The "Design decisions" section is binding - do not invent new frontmatter fields or a regex filter (FR-1.1 is reduced), and do not drop FinishTool/ThinkTool (FD-2).

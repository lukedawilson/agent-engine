# System Architecture

## System Overview

agent-engine is a single Python library + CLI. The CLI (`agent-engine PIPELINE`) loads a pipeline YAML, builds a cyclic LangGraph state graph (one node per step plus a retry `bump` node and a `success` terminal), and runs it against the OpenHands SDK, which executes LLM-driven agents with terminal/file-editor tools. A SQLite checkpointer makes runs crash-resumable. Extensions contribute actions, SDK tools, and document loaders through a registry.

## Architecture Diagram

```mermaid
flowchart TD
    subgraph CLI["cli.py — two-phase CLI"]
        P1["Phase 1: find PIPELINE"]
        P2["Phase 2: full parser<br/>(core flags + loader flags)"]
    end
    subgraph Config["config.py — strict schema"]
        PC["PipelineConfig<br/>(extra=forbid)"]
        SC["StepConfig<br/>agent|command|action"]
        LC["LlmConfig"]
    end
    subgraph Registry["registry.py — extension seam"]
        R["Registry<br/>actions / loaders / tools"]
        LE["load_extensions<br/>(module:Class)"]
    end
    subgraph Graph["graph.py + stages.py"]
        G["StateGraph (cyclic)"]
        Nodes["agent / command / action nodes"]
        Bump["bump retry node"]
        Success["success terminal"]
        CP["SqliteSaver<br/>(loop-checkpoints.sqlite)"]
    end
    subgraph SDK["OpenHands SDK"]
        A["Agent<br/>(frontmatter tools allowlist)"]
        C["Conversation<br/>(workspace, max_iterations)"]
        T["Tools: terminal,<br/>file_editor, task_tracker"]
    end
    subgraph Ext["extensions/"]
        Aidlc["aidlc.py<br/>AidlcExtension"]
    end
    subgraph Viz["viz.py"]
        VB["VizBus + HTTP server"]
        NW["NodeWatch / capture"]
    end
    P1 --> P2 --> Config
    Config --> Registry
    Registry --> LE
    LE --> Ext
    Config --> Graph
    Graph --> SDK
    Nodes --> SDK
    Graph --> CP
    Graph --> Viz
```

## Component Descriptions

### cli.py
- **Purpose**: Entry point; two-phase argument handling.
- **Responsibilities**: core flags (`--resume`, `--max-attempts`, `--no-viz`, `--viz-port`), loader-contributed flags per pipeline, exit code 0/1.
- **Dependencies**: config, graph, registry.
- **Type**: Application

### config.py
- **Purpose**: Strict YAML schema.
- **Responsibilities**: step-shape validation (exactly one kind key; command steps cannot carry artifact/verdicts/produces/params/max_iterations; artifact↔verdicts pairing; timeout requires command), duplicate step names, route targets, reserved terminal names.
- **Dependencies**: pydantic, yaml.
- **Type**: Model

### graph.py
- **Purpose**: Config-driven LangGraph builder + `run_pipeline` public API.
- **Responsibilities**: node/edge assembly, retry cycle, checkpointing, resume (including hard-failure re-entry), doc resolution, viz wiring, commit_allowed computation before checkpointer dirties the worktree.
- **Dependencies**: langgraph, stages, config, llm, loaders, registry, viz, actions.
- **Type**: Application

### stages.py
- **Purpose**: Stage nodes, routers, `run_agent` port.
- **Responsibilities**: agent/command/action node closures, verdict reading, unclear-verdict retry, attempt hygiene (`clear_attempt_artifacts`), command timeout with process-group SIGKILL, notes accumulation, deterministic routing.
- **Dependencies**: openhands-sdk, langgraph, agents, config, registry, verdicts.
- **Type**: Application

### agents.py
- **Purpose**: Agent file loading + SDK factory mechanics.
- **Responsibilities**: `load_agent` — file must exist (fail fast), frontmatter name must match filename, tools resolved against the SDK's global registry (unknown → ValueError). Imports register `terminal`, `file_editor`, `task_tracker`.
- **Dependencies**: openhands-sdk, openhands-tools.
- **Type**: Application

### registry.py
- **Purpose**: Extension seam between core and consumers.
- **Responsibilities**: action registration (duplicate → error), document loader registration with CLI-option collision detection, SDK tool registration via `register_tool`, `default_registry` (commit action + plan loader), `load_extensions` fail-fast.
- **Dependencies**: argparse, importlib, openhands-sdk.
- **Type**: Application

### actions.py
- **Purpose**: Built-in pipeline actions (node-shaped).
- **Responsibilities**: `commit` (single commit point, gated on clean-at-start worktree), `git_worktree_clean`, orphaned viz-listener sweep (`kill_listeners_on_port` with positive-only cwd attribution).
- **Dependencies**: git CLI, lsof, ps.
- **Type**: Application

### llm.py
- **Purpose**: LLM construction from config.
- **Responsibilities**: fail-fast on missing api_key_env (no silent fallbacks), two import-time SDK compat shims (DeepSeek reasoning-content registration + reasoning passback repair), no-timeout default.
- **Dependencies**: openhands-sdk.
- **Type**: Application

### loaders.py
- **Purpose**: Built-in `plan` document loader + selection flow.
- **Responsibilities**: `select_loader` coexistence model (flag selects; two loaders' flags → error; sole defaultable autodetect; none → no docs).
- **Dependencies**: registry.
- **Type**: Application

### verdicts.py
- **Purpose**: Verdict-line parsing.
- **Responsibilities**: last decoration-tolerant `VERDICT: X` line wins; caveat delimiters; negation handling on two-key sets; bare-prose rejection.
- **Dependencies**: none (pure).
- **Type**: Model

### viz.py (1,148 LOC)
- **Purpose**: Live graph visualization.
- **Responsibilities**: HTTP server on localhost (default port 8321), live event bus, node watching, console capture, Mermaid topology, heartbeat.
- **Dependencies**: http.server, threading.
- **Type**: Application

### extensions/aidlc.py
- **Purpose**: Bundled AI-DLC document loader extension.
- **Responsibilities**: `--ai-dlc-unit` flag + bare-run autodetect from aidlc-state.md; unit doc resolution with inception docs and code-generation plans.
- **Dependencies**: registry.
- **Type**: Client

## Data Flow

```mermaid
sequenceDiagram
    participant CLI
    participant Graph
    participant Stage as stage node
    participant SDK as OpenHands Agent
    participant FS as state_dir artifacts
    participant Git as git worktree

    CLI->>Graph: run_pipeline(cfg, args)
    Graph->>Graph: build_graph + SqliteSaver
    loop per attempt
        Graph->>Stage: context + attempt N
        Stage->>SDK: run_agent(name, message)
        SDK->>FS: writes artifact / produces
        Stage->>FS: parse VERDICT line
        alt verdict pass
            Stage->>Graph: route on_pass
        else verdict fail + retry
            Stage->>Graph: bump (attempt+1, notes accumulated)
        else unclear
            Stage->>Graph: implicit bump retry (bounded)
        end
    end
    Graph->>Git: commit action (if clean-at-start)
    Graph->>CLI: (success, attempts)
```

## Integration Points

- **External APIs**: OpenHands SDK (agent execution), LLM provider HTTP API (DeepSeek, configured via base_url/model/api_key_env).
- **Databases**: SQLite checkpointer (`<state_dir>/loop-checkpoints.sqlite`) — one per workspace.
- **Third-party Services**: none beyond the LLM provider.

## Infrastructure Components

- **CDK Stacks**: none.
- **Deployment Model**: pip-installable library (`agent-engine` console script); runs in-process on the operator's machine; no server deployment.
- **Networking**: localhost-only viz HTTP server (127.0.0.1, default port 8321, auto-opens browser); outbound HTTPS to the LLM provider.

## Security-Relevant Architecture Notes (for the guardrails/sandboxing intent)

- **Tool injection path**: `pipeline.yaml extensions:` → `load_extensions` → `registry.add_tool` → SDK global tool registry → agent frontmatter `tools:` allowlist → `load_agent` → `agent_definition_to_factory`. Tool names in frontmatter are resolved against the SDK's GLOBAL registry (any extension can register anything; no namespacing).
- **Shell execution surfaces**: (1) agent `terminal` tool — full host-user shell authority; (2) command steps — `subprocess.Popen(..., shell=True, start_new_session=True)` in the workspace; (3) `actions.py` git/lsof/ps subprocess calls. The prompt-level tool allowlist restricts what agents are OFFERED, not what granted tools can do.
- **Filesystem authority**: agents run with `workspace=` set, but `terminal` can reach the entire host filesystem; artifacts live in `state_dir`.
- **The SDK's `llm_security_analyzer`** is advisory prompt text, not enforcement.

# Dependencies

## Internal Dependencies

```mermaid
flowchart TD
    cli["cli.py"] --> config["config.py"]
    cli --> graph["graph.py"]
    graph --> config
    graph --> stages["stages.py"]
    graph --> registry["registry.py"]
    graph --> llm["llm.py"]
    graph --> loaders["loaders.py"]
    graph --> viz["viz.py"]
    graph --> actions["actions.py"]
    stages --> agents["agents.py"]
    stages --> verdicts["verdicts.py"]
    registry --> actions
    registry --> loaders
    extensions["extensions/aidlc.py"] --> registry
```

### graph.py depends on stages.py
- **Type**: Runtime
- **Reason**: node/edge assembly + run_pipeline orchestrates stage nodes, routers, bump/success terminals.

### stages.py depends on agents.py, verdicts.py, registry.py, config.py
- **Type**: Runtime
- **Reason**: agent loading, verdict parsing, action lookup, step config typing.

### registry.py depends on actions.py + loaders.py (default_registry)
- **Type**: Runtime
- **Reason**: core pre-registers the commit action and plan loader.

### extensions/aidlc.py depends on registry.py (protocol only)
- **Type**: Runtime
- **Reason**: registers the ai-dlc document loader.

## External Dependencies

### openhands-sdk
- **Version**: ~=1.17.0
- **Purpose**: LLM construction, Agent/Conversation execution, agent-definition factory, tool registration.
- **License**: MIT (OpenHands project).

### openhands-tools
- **Version**: ~=1.17.0
- **Purpose**: terminal (full shell), file_editor, task_tracker tools.
- **License**: MIT.

### langgraph
- **Version**: >=1.2
- **Purpose**: StateGraph execution with conditional edges.
- **License**: MIT.

### langgraph-checkpoint-sqlite
- **Version**: >=3.0
- **Purpose**: SqliteSaver checkpointing.
- **License**: MIT.

### pydantic
- **Version**: >=2.0
- **Purpose**: Config schema validation.
- **License**: MIT.

### PyYAML
- **Version**: >=6.0
- **Purpose**: YAML parsing.
- **License**: MIT.

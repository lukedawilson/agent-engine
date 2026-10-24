# Deployment Architecture - unit-1 (output-passing fix)

## Deployment Model

Unit-1 changes **no deployment characteristics**. The library ships as a pip-installable Python package (`agent-engine` console entry point); consumers run `agent-engine pipeline.yaml` in their own environment. No servers, no services, no images.

## Runtime Placement

| Runtime element | Placement | Changed by unit-1? |
| --- | --- | --- |
| Pipeline process (LangGraph + OpenHands SDK) | User's machine, user's OS account | No |
| `state_dir` artifacts | Local disk, user workspace | Paths unchanged |
| Viz server | localhost-only, existing | No |
| Commit action | Host-side native git | No |

## Environment Assumptions

- Python ≥ 3.12 (pyproject)
- Existing deps: `openhands-sdk ~=1.17.0`, `openhands-tools ~=1.17.0`, `langgraph>=1.2`, `pydantic>=2`, `PyYAML`
- New: none (TS-3); dev-dep addition `hypothesis` (TS-2)

## Cross-platform

Unit-1 introduces no platform-specific behavior - the file-write and string-parse paths are pure stdlib. Platform variance (daemon detection, mounts, CRLF) belongs to unit-3.

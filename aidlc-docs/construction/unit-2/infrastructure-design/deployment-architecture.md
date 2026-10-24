# Deployment Architecture - unit-2 (SDK-level hardening)

## Deployment Model

Unit-2 changes **no deployment characteristics**. The library ships as a pip-installable Python package (`agent-engine` console entry point); consumers run `agent-engine pipeline.yaml` in their own environment. No servers, no services, no images.

## Runtime Placement

| Runtime element | Placement | Changed by unit-2? |
| --- | --- | --- |
| Pipeline process (LangGraph + OpenHands SDK) | User's machine, user's OS account | No |
| Command/action subprocesses | Child of the pipeline process, host-side | Hardened (argv/shell hybrid, `child_env`, `shutil.which`) - placement unchanged |
| `state_dir` artifacts | Local disk, user workspace | Paths unchanged |
| Viz server | localhost-only, existing | No |
| Commit action | Host-side native git | Hardened (`shutil.which`, `shell=False`) - still host-side |

## Environment Assumptions

- Python ≥ 3.12 (pyproject)
- Existing deps: `openhands-sdk ~=1.17.0`, `openhands-tools ~=1.17.0`, `langgraph>=1.2`, `pydantic>=2`, `PyYAML`
- New runtime deps: none (TS-1 - stdlib `shlex`/`shutil`/`os`/`re`)
- New config: one optional `env_allowlist: list[str]` field (additive, backward compatible)

## Cross-platform

Unit-2 introduces no new platform-specific behaviour: `shlex`/`shutil.which`/`subprocess` are portable. The `lsof`/`ps`/`kill` binaries (in `actions.py`) are POSIX-only, but that is pre-existing behaviour, not introduced here. Platform variance for the sandbox (daemon detection, mounts, CRLF) belongs to unit-3.

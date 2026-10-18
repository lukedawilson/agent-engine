# Infrastructure Design Plan — unit-2 (SDK-level hardening)

## Assessment Context

Unit-2 hardens host-side subprocess invocation (command/action steps) and tool registration. It introduces **no new infrastructure surface**: no deployment target change, no compute, no storage schema, no messaging, no networking, no new monitoring. The subprocess hardening is in-process stdlib code (`shlex`/`shutil`/`os`), not a runtime boundary.

## Infrastructure Steps

- [x] Analyze functional + NFR design artifacts for infrastructure needs
- [x] Evaluate all infrastructure categories (below)
- [x] Generate `aidlc-docs/construction/unit-2/infrastructure-design/infrastructure-design.md`
- [x] Generate `aidlc-docs/construction/unit-2/infrastructure-design/deployment-architecture.md`
- [x] Confirm no shared-infrastructure artifact needed

## Category Evaluation

| Category | Disposition | Justification |
| --- | --- | --- |
| Deployment Environment | N/A | Desktop CLI library, pip-installable (`agent-engine = agent_engine.cli:main`); no deployment target, no cloud provider. Unchanged by unit-2. |
| Compute Infrastructure | N/A | Command/action subprocesses are children of the existing pipeline process on the host; no new compute service. |
| Storage Infrastructure | N/A | `env_allowlist` is a YAML config field, not storage; `state_dir` unchanged. No schema, no database. |
| Messaging Infrastructure | N/A | In-process step routing (LangGraph); no queues, no async boundaries. |
| Networking Infrastructure | N/A | Unit-2 adds no network surface. (Unit-3 introduces the container daemon socket — its infrastructure belongs to unit-3's design.) |
| Monitoring Infrastructure | N/A | Existing viz/console capture unchanged; no new observability surface. |
| Shared Infrastructure | N/A | Nothing shared across units at the infrastructure level in unit-2. |

## Open Questions

None. Every category is N/A with justification — unit-2 has zero infrastructure footprint. Proceeding directly to artifact generation.

## Verification

- [x] No category skipped without justification
- [x] Unit-3 infrastructure (Docker daemon socket, mounts, image toolchain) explicitly deferred to unit-3's Infrastructure Design

# Infrastructure Design - unit-1 (output-passing fix)

## Summary

Infrastructure design found **no infrastructure components** in unit-1. The unit modifies in-process data flow within a desktop CLI library. All infrastructure categories are N/A with justification (see plan).

## Component-to-Infrastructure Mapping

| Logical component (FD) | Infrastructure choice | Rationale |
| --- | --- | --- |
| `CapturedOutput` VO | None - in-process value object | Pure computation + local file write |
| `Verdict` VO | None - in-process value object | Pure parsing |
| `StagesRuntime.run_agent` modification | None - existing orchestrator | Delegation only |
| `Result[T, E]` type | None - stdlib-level code | No external service |

## Explicitly Deferred to unit-3

| Item | Why |
| --- | --- |
| Container daemon detection (unix socket vs npipe) | Unit-3 kernel isolation; unit-1 touches no execution boundary |
| Mount-path translation, image selection | Unit-3 |
| Isolation fail-fast on unavailable runtime | Unit-3 (FR-2.3) |

## Storage Note

Artifact writes target the existing `state_dir/<artifact>` paths. No new directories, no new lifecycle (stale-artifact hygiene unchanged - BR-5).

## Security Note

No new network, process, or file-permission surfaces (NFR-1.2/1.3). The security baseline's infrastructure-shaped rules remain N/A for a desktop library.

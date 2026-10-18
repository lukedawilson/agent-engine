# NFR Requirements — unit-1 (output-passing fix)

## Assessment Summary

NFR assessment identified three real NFRs; everything else is N/A per user scoping (desktop CLI tool, single pipeline process, no uptime concept).

## Non-Functional Requirements

| ID | NFR | Detail |
| --- | --- | --- |
| NFR-1.1 | **Fail-safe handling** | All expected conditions return typed `Result` errors (`NO_VERDICT`, `AMBIGUOUS`, `EMPTY_RESPONSE`, `IO_ERROR`) — never exceptions. Security-baseline SECURITY-15 (exception handling/fail-safe) satisfied by design. |
| NFR-1.2 | **Least privilege** | Capture writes only to the step's artifact path under `state_dir`; no other filesystem writes introduced. SECURITY-06 (least privilege) satisfied. |
| NFR-1.3 | **Data protection** | Captured artifacts are local plaintext model output — same exposure as today's agent-written files. No encryption, no access control, no secret scrubbing (user-confirmed). Cloud-shaped security rules marked N/A for a desktop library. |
| NFR-1.4 | **Reliability (scoped)** | Retry semantics unchanged (BR-3): empty response / unclear verdict → attempt-bounded retry, never silent. Resiliency-baseline retry/recovery guidance in scope; server load/HA/DR N/A. |
| NFR-1.5 | **Testability / PBT** | `hypothesis` added as dev dependency; PBT-01 properties tested (pure functions + serialization round-trips). PBT-02/03/07/08/09 blocking satisfied. |

## Category Dispositions

| Category | Disposition | Justification |
| --- | --- | --- |
| Scalability | N/A | Desktop tool, single pipeline process |
| Performance | N/A | One string pass + one file write per agent step |
| Availability | N/A | No uptime concept; crash-safe resume via checkpointing unchanged |
| Maintainability | N/A | Covered by binding DDD + PBT extension rules |
| Usability | N/A | CLI UX unchanged; YAML schema unchanged (FD-5) |

## Security Baseline Rule Dispositions (blocking set)

| Rule | Disposition |
| --- | --- |
| SECURITY-01 (encryption) | N/A — local plaintext artifacts, no transport |
| SECURITY-02/03 (access/app logging) | N/A — library emits no logs; viz/pipeline logging unchanged |
| SECURITY-04 (HTTP headers) | N/A — no HTTP server in unit-1 scope |
| SECURITY-05 (input validation) | Applicable — `from_agent_result` validates SDK result shape; typed errors on malformed input |
| SECURITY-06 (least privilege) | Applicable — NFR-1.2 |
| SECURITY-07..14 | N/A — cloud/network/config posture rules; desktop library |
| SECURITY-15 (fail-safe) | Applicable — NFR-1.1 |

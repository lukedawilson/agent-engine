# Tech Stack Decisions - unit-1 (output-passing fix)

## Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| TS-1 | **Result type**: generic `Result[T, E]` value type in a new module (user-approved NFR-1 answer A) | Reusable across all three units; DDD-compliant (typed errors, no exceptions for expected conditions); ~40 lines, no dependency |
| TS-2 | **PBT**: add `hypothesis` as dev dependency (user-approved NFR-2 answer A) | Blocking PBT rules for pure functions satisfied; ships with the capture/parse change |
| TS-3 | **No new runtime dependencies** | Unit-1 uses stdlib + existing deps (pydantic for config only, if needed for result typing - else plain dataclasses) |
| TS-4 | **Location of capture logic**: new `src/agent_engine/outputs.py` (VOs `CapturedOutput`, `Verdict`) | Matches Application Design component map; `verdicts.py` absorbed into `Verdict.from_text` |
| TS-5 | **SDK integration**: extract final response from the SDK agent result object | Existing `openhands-sdk ~=1.17.0` result API; no new SDK surface |

## Deferred (out of unit-1)

| Item | Deferred to |
| --- | --- |
| `Result` reuse by Sandbox execution results | unit-3 |
| Parsing-logic hardening beyond BR-2 (user flagged: parsing has had bugs - FD discussion) | Already handled in unit-1 FD per FD-2; deeper hardening if needed = future intent |

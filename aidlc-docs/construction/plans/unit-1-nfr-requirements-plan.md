# NFR Requirements Plan — unit-1 (output-passing fix)

## NFR Assessment Context

Desktop CLI library; unit-1 changes the internal feedback channel of one pipeline step. No new external surfaces.

## NFR Steps

- [x] Analyze functional design artifacts (business-logic-model, business-rules, domain-entities)
- [x] Resolve NFR questions (below)
- [x] Generate `aidlc-docs/construction/unit-1/nfr-requirements/nfr-requirements.md`
- [x] Generate `aidlc-docs/construction/unit-1/nfr-requirements/tech-stack-decisions.md`
- [x] Apply security-baseline: mark cloud-shaped rules N/A with justification; enforce applicable rules
- [x] Apply resiliency-baseline scoped: retry/recovery relevant; server load/HA/DR N/A (user scoping)

## Category evaluation

| Category | Status | Justification |
| --- | --- | --- |
| Scalability | N/A | Desktop tool, single pipeline process (user scoping: no server treatment) |
| Performance | N/A | Capture adds one string pass + one file write per agent step |
| Availability | N/A | No uptime concept; crash-safe resume already exists (checkpointing unchanged) |
| Security | ⏳ Question NFR-3 | Fail-safe handling designed (typed errors); data-protection scope to confirm |
| Tech stack | ⏳ Questions NFR-1/2 | Result type; PBT test dependency |
| Reliability | N/A (scoped) | Retry semantics already designed in FD (BR-3); container recovery is unit-3 |
| Maintainability | N/A | Covered by DDD/PBT extension rules already binding |
| Usability | N/A | CLI UX unchanged; YAML schema unchanged (FD-5) |

## Open Questions

### Question NFR-1: Result type implementation

FD-2 requires typed `Result[Verdict]` (NO_VERDICT/AMBIGUOUS) and BR-3 typed errors (EMPTY_RESPONSE/IO_ERROR). How should `Result` be implemented in the codebase?

A) Small generic `Result[T, E]` value type (new module, ~40 lines) with typed error-code enums — reusable across all three units (recommended; DDD-compliant, no exceptions for expected conditions)

B) Pydantic discriminated union per domain object — more ceremony, less reusable

C) Specific exception subclasses — violates the DDD rule (exceptions for expected conditions)

X) Other

[Answer]: A — generic Result[T, E] value type in a new module (~40 lines), reusable across all three units

---

### Question NFR-2: PBT test dependency

NFR-6/PBT extension (blocking for pure functions) requires property-based tests on `Verdict.from_text` and `CapturedOutput` round-trips. Add `hypothesis` now?

A) Yes — add `hypothesis` as a dev dependency in unit-1; PBT tests ship with the capture/parse change (recommended — properties already identified in FD PBT-01)

B) No — plain example-based tests for unit-1; add Hypothesis later in a dedicated pass

X) Other

[Answer]: A — add hypothesis as a dev dependency in unit-1; PBT tests ship with the capture/parse change

---

### Question NFR-3: Security scope confirmation

The security baseline is blocking. For unit-1 the applicable rules are fail-safe handling (typed errors — already designed) and least privilege. Data-protection scope to confirm: captured responses are the model's own output written to local `state_dir` — no encryption, no access control, no secret scrubbing, correct?

A) Confirm — artifacts are local plaintext model output, same exposure as today's agent-written files; no new data-protection requirements (recommended)

B) Add secret scrubbing / restrictive file permissions on captured artifacts

X) Other

[Answer]: A — confirm: artifacts are local plaintext model output, same exposure as today's agent-written files; no new data-protection requirements

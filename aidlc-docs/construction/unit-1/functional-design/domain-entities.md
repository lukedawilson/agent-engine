# Domain Entities — unit-1 (output-passing fix)

Per DDD standards: descent audit applied. No new services; no persistence abstractions; no repositories/DAOs; behaviour lives at the lowest responsible level.

## Value Objects

### CapturedOutput (VO — NEW, `src/agent_engine/outputs.py`)

| Member | Type | Notes |
| --- | --- | --- |
| `raw_text` | `str` | The agent's final response text |
| `artifact_path` | `Path` | Step's existing produces:/artifact: path under state_dir |
| `verdict` | `Result[Verdict]` | Parsed from `raw_text`; verdict-bearing steps only |

Static constructors / methods:

- `CapturedOutput.from_agent_result(result, step, state_dir) -> Result[CapturedOutput]` — extracts final response from the SDK result; empty/error → typed error (BR-3, FD-4).
- `write() -> Result[None]` — writes per BR-4/Br-5 hygiene and truncation rules; IO error → typed error.

### Verdict (VO — NEW, absorbs `verdicts.py`)

| Member | Type | Notes |
| --- | --- | --- |
| `kind` | enum | `PASS` / `FAIL` / `APPROVED` / `NEEDS_CHANGES` |

Static constructors:

- `Verdict.from_text(text) -> Result[Verdict]` — BR-2 rules; typed errors `NO_VERDICT` / `AMBIGUOUS`. Pure function — primary PBT target.

### Result (existing pattern, reused)

Typed error codes (`NO_VERDICT`, `AMBIGUOUS`, `EMPTY_RESPONSE`, `IO_ERROR`); never an exception for an expected condition.

## Modified Entities

### Step (entity — modified)

- `route(verdict: Result[Verdict])` — unchanged routing shape; now consumes typed results. NO_VERDICT/AMBIGUOUS map to the existing retry edge.

### StagesRuntime (sole application service — modified, no new services)

- `run_agent(step, state)`: after the SDK run, calls `CapturedOutput.from_agent_result`, `write()`, and (verdict-bearing steps) `Verdict.from_text`. Delegation only — all logic lives in the VOs.

## Descent Audit (Domain Validation)

| Behaviour | Placement | Verdict |
| --- | --- | --- |
| Parse verdict from text | `Verdict.from_text` (VO static) | Correct — pure function on VO |
| Extract final response | `CapturedOutput.from_agent_result` (VO static) | Correct — construction of a VO |
| Write artifact | `CapturedOutput.write` (VO method) | Correct — the VO knows its own serialisation |
| Orchestrate capture+write+parse | `StagesRuntime.run_agent` | Correct — pre-existing sole application service, one caller |
| Retry/route on typed errors | `Step.route` (entity) | Correct — entity owns its transitions |

No entity delegated to a helper; no new service; no single-impl interface; no testability-driven seam.

## Requirements Traceability

| FR | Covered by |
| --- | --- |
| FR-1.2 (pipeline captures final response) | CapturedOutput, StagesRuntime.run_agent |
| FR-1.3 (drop file_editor) | dev/review `tools:` lists (agent definitions) |
| NFR-2 (fail-fast) | typed errors → attempt failure paths |
| NFR-6 (PBT partial) | PBT-01 properties in business-logic-model.md |

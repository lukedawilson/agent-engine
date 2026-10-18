# Code Generation Plan — unit-1 (output-passing fix)

## Unit Context

| Item | Detail |
| --- | --- |
| Project type | Brownfield — modify existing files, never create duplicates |
| Stories / requirements | FR-1.2 (pipeline captures final SDK response), FR-1.3 (drop `file_editor` from dev/review agents), NFR-1.1 (typed Results), NFR-1.2 (least privilege — artifact paths only), NFR-1.5/PBT (Hypothesis tests) |
| Dependencies | None — unit-1 is first in sequence; unit-2/3 consume `Result` and the capture path |
| Interface contract | New module `src/agent_engine/outputs.py` exports `Result`, `CapturedOutput`, `Verdict`; `stages.py` consumes them; `verdicts.py` absorbed and deleted |
| Existing files modified | `src/agent_engine/stages.py`, `agent-engine/sdk_agents/dev.agent.md`, `agent-engine/sdk_agents/review.agent.md`, `pyproject.toml` (dev dep) |
| Files created | `src/agent_engine/results.py`, `src/agent_engine/outputs.py`, tests |
| Files deleted | `src/agent_engine/verdicts.py` (absorbed) |
| N/A steps | API layer (in-process library, no HTTP surface), Repository layer (DDD ban on repositories), Frontend, DB migrations, Deployment artifacts, Project-structure setup (brownfield) |

## TDD ordering

Repo policy: TDD (red → green → refactor). Tests are written before the code they validate. Mock policy: SDK classes (`Conversation`, `Agent`) may be mocked only for capture-algorithm tests; file I/O and pure functions use real implementations and temp dirs.

## Steps

- [x] **Step 1 — Result type (red)** — write failing tests `tests/test_results.py` for `Result[T, E]`: ok/err construction, typed error codes, unwrap semantics
- [x] **Step 2 — Result type (green)** — create `src/agent_engine/results.py` (~40 lines, TS-1); make Step 1 tests pass
- [x] **Step 3 — Verdict VO (red)** — write failing tests `tests/test_verdict.py`: port existing `parse_verdict` behavior assertions + new typed `NO_VERDICT`/`AMBIGUOUS` cases (BR-2.1–2.6); historical fixtures' cases included (BR-7)
- [x] **Step 4 — Verdict VO (green)** — create `Verdict` in `src/agent_engine/outputs.py` with `from_text(text) -> Result[Verdict]` (last decoration-tolerant line wins, caveat delimiters, negation, 2-key ambiguity); make Step 3 tests pass
- [x] **Step 5 — CapturedOutput VO (red)** — write failing tests `tests/test_outputs.py`: `from_agent_result` (extraction from fake events; EMPTY_RESPONSE on missing final message), `write()` round-trip to temp dir (FD-3 truncation behavior)
- [x] **Step 6 — CapturedOutput VO (green)** — implement in `src/agent_engine/outputs.py` using the verified SDK path (filter `MessageEvent` where `source == 'agent'`, take last, `content_to_str` join — capture BEFORE `conv.close()`); make Step 5 tests pass
- [x] **Step 7 — PBT suite** — create `tests/test_outputs_pbt.py` with Hypothesis covering the PBT-01 properties: last-line-wins, decoration invariance, NO_VERDICT on verdict-free text, write/read round-trip (NFR-1.5)
- [x] **Step 8 — pyproject** — add `hypothesis` to dev dependencies (TS-2); verify PBT suite runs
- [x] **Step 9 — Wire into stages.py** — modify `run_agent` to capture the final response and write the artifact before `conv.close()`; switch `_read_stage_artifact` verdict parsing to `Verdict.from_text`; remove the `verdicts.py` import
- [x] **Step 10 — Delete verdicts.py** — remove `src/agent_engine/verdicts.py`; verify no remaining imports
- [x] **Step 11 — Agent tool lists (FR-1.3)** — edit `agent-engine/sdk_agents/dev.agent.md` and `review.agent.md`: remove `file_editor` from `tools:` (both keep `terminal`); update their prompts where they reference writing report/verdict files (replace with "state findings in your final response")
- [x] **Step 12 — Full suite** — run entire test suite (`pytest tests/ -q`); `test_e2e_fixtures.py` and `test_sdk_compat.py` must stay green (BR-7)
- [x] **Step 13 — Documentation** — generate `aidlc-docs/construction/unit-1/code/` summaries (markdown only): what changed, capture flow, verdict semantics

## Story Traceability

| Requirement | Steps |
| --- | --- |
| FR-1.2 capture | Steps 3–10 |
| FR-1.3 drop file_editor | Step 11 |
| NFR-1.1 typed results | Steps 1–4 |
| NFR-1.2 least privilege | Steps 5–6 (artifact paths only) |
| NFR-1.5 PBT | Steps 7–8 |
| NFR-6 PBT properties | Step 7 |
| BR-7 historical fixtures | Steps 3, 12 |


---

## Note: Self-hosting feasibility (recorded at user request, 2026-10-17)

- **Unit-1 cannot self-host.** The pipeline process imports its modules once at startup and freezes them; unit-1 edits (`stages.py`, `verdicts.py` deletion, agent prompts) land mid-run invisible to the running process, while `load_agent` re-reads `.agent.md` files per step — the verdict channel skews (new prompts say "final response", frozen `_read_stage_artifact` reads files) and unclear-verdict retries exhaust attempts.
- **Units 2 and 3 CAN dogfood** the engine: start the run after unit-1 lands; verdict/capture mechanism is frozen-and-consistent; edits happen via subprocesses (terminal + pytest fresh imports see new code); review/qa supervise by reading files. Limits: frozen pipeline cannot self-validate new behavior (unit-3 sandboxing validated by pytest only); a bad `.agent.md` edit by the dev agent triggers fail-fast → attempt-bounded retry.
- **Decision**: unit-1 implemented manually (this TDD plan). Unit-2/3 execution approach may use the engine itself — decided at their planning stages.

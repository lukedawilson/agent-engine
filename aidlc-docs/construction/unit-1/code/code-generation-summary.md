# Code Generation Summary - unit-1 (output-passing fix)

## Created

| File | Contents |
| --- | --- |
| `src/agent_engine/results.py` | Generic `Result[T, E]` value type (typed errors, no exceptions for expected conditions) |
| `src/agent_engine/outputs.py` | `CaptureError`/`VerdictError` enums; `Verdict.from_text -> Result[Verdict]` (absorbs verdicts.py); `CapturedOutput.from_agent_result` + `write()` |
| `tests/test_results.py` | 9 tests for Result |
| `tests/test_verdict.py` | 39 tests: 35 legacy parse_verdict assertions ported + conflict/ambiguity + shape |
| `tests/test_outputs.py` | 10 tests: capture algorithm + write round-trip + typed errors |
| `tests/test_outputs_pbt.py` | 4 Hypothesis properties (PBT-01) |

## Modified

| File | Change |
| --- | --- |
| `src/agent_engine/stages.py` | `run_agent` captures final SDK response (before `conv.close()`); `AgentResult` gains `response`/`capture_error`; `_read_stage_artifact` deleted; verdict parsing via `Verdict.from_text`; `_unclear_note` rewritten for capture channel (EMPTY_RESPONSE/NO_VERDICT/AMBIGUOUS); router handles produces-only retry |
| `agent-engine/sdk_agents/dev.agent.md` | `tools: [terminal]`; step 5 → final-response channel |
| `agent-engine/sdk_agents/review.agent.md` | `tools: [terminal]`; OUTPUT → final response |
| `agent-engine/sdk_agents/qa.agent.md` | report → final response (already `[terminal]` only) |
| `pyproject.toml` | `[project.optional-dependencies] dev = [hypothesis, pytest]` |
| `tests/conftest.py` | FakeAgents: `step` kwarg, capture semantics, new `respond` behavior |
| `tests/test_stages.py`, `tests/test_graph.py`, `tests/test_e2e_fixtures.py` | Assertion updates to capture-channel note texts |

## Deleted

| File | Reason |
| --- | --- |
| `src/agent_engine/verdicts.py` | Absorbed into `outputs.py` (`Verdict.from_text`) |
| `tests/test_verdicts.py` | Replaced by `tests/test_verdict.py` |

## Verification

- Full suite: **373 passed** (`tests/ -q`, 28.6s) - including `test_e2e_fixtures.py` (BR-7 historical fixtures) and `test_sdk_compat.py`.
- TDD: red → green → refactor per plan steps 1–12.
- DDD compliance: no new services; VOs own parse/write; `StagesRuntime` delegates only.

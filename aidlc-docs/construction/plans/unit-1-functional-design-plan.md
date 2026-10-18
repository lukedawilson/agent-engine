# Functional Design Plan — unit-1 (output-passing fix)

## Unit Context (from unit-of-work.md)

Pipeline captures the agent's **final SDK response** and writes the artifact itself; `file_editor` removed from dev/review; verdict parsing moves onto captured text via typed `Result`. Parsing logic gets dedicated FD treatment — existing parser has had bugs; no assumptions carried.

## FD Steps

- [x] Analyze unit-1 context and story-map assignments (FR-1.2, FR-1.3)
- [x] Resolve FD questions (below)
- [x] Generate `aidlc-docs/construction/unit-1/functional-design/business-logic-model.md`
- [x] Generate `aidlc-docs/construction/unit-1/functional-design/business-rules.md`
- [x] Generate `aidlc-docs/construction/unit-1/functional-design/domain-entities.md`
- [x] Validate against DDD rules (descent audit: no new services; VOs with static constructors)
- [x] Identify PBT properties (PBT-01) for capture/parse pure functions

## Open Questions

### Question FD-1: Capture scope — which agent-output channels does capture replace?

Today agents write files themselves: dev writes `implementation-summary.md`; review/qa write verdict files. Unit 1 replaces the **summary + verdict** channels with pipeline capture. Agents still legitimately produce working files via terminal (code edits, test runs) — those stay.

A) Capture replaces exactly the `produces:`/`artifact:` channels (summary + verdicts); all other terminal-produced files untouched (recommended)

B) Capture replaces ALL agent file output — pipeline snapshots the entire workspace diff after the agent finishes

X) Other

[Answer]: A — capture replaces exactly the produces:/artifact: channels; other terminal-produced files untouched

---

### Question FD-2: Verdict parsing semantics on captured text

The existing `parse_verdict` reads artifact files: last decoration-tolerant `VERDICT: X` line wins, negation on 2-key sets, caveat delimiters. For captured responses, keep the same semantics?

A) Keep last-VERDICT-line-wins + decoration tolerance + caveat handling, but return typed `Result[Verdict]` (NO_VERDICT / AMBIGUOUS) instead of exceptions (recommended — preserves behavior, fixes the exception-for-expected-condition violation)

B) Redesign semantics entirely (e.g. strict JSON block only)

X) Other

[Answer]: A — keep last-VERDICT-line-wins + decoration tolerance + caveat handling; return typed Result[Verdict] (NO_VERDICT/AMBIGUOUS), no exceptions

---

### Question FD-3: Truncation policy for captured artifact + context

Captured responses can be long; the shipped fixtures include a "verdict-first truncation" behavior. What's the policy?

A) Verdict-first truncation retained for the verdict channel; the summary artifact keeps the full response but `build_context` truncates to a budget (recommended)

B) Hard cap on both (e.g. N chars, verdict preserved)

X) Other

[Answer]: A — verdict-first truncation for the verdict channel; summary artifact keeps full response; build_context truncates to a budget

---

### Question FD-4: Missing / empty final response

If the agent's final response is empty or the agent errored out (no final message), what happens?

A) Treat as attempt failure — increment attempt, retry per existing policy (recommended — consistent with unclear-verdict retry)

B) Fail the step immediately without retry

X) Other

[Answer]: A — empty/errored final response = attempt failure; increment attempt, retry per existing policy

---

### Question FD-5: Pipeline YAML — implicit or explicit capture?

Stage 1 is always-on. Does the existing YAML stay unchanged (capture is implicit — pipeline always writes the artifact from the final response) or does it require a new `capture: true` key?

A) Implicit — YAML schema unchanged; existing pipelines get the new behavior automatically (recommended — "guardrailed by design", no opt-out)

B) Explicit `capture: true` on agent steps

X) Other

[Answer]: A — implicit; YAML schema unchanged; existing pipelines get capture automatically

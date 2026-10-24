# 010 - viz_demo.py: full-snapshot `step_verdicts` events

**Status:** COMPLETED (2026-10-10)
**Date:** 2026-10-10
**Related:** 009 (viz startup port sweep), TDD fix in viz.py PAGE JS (attempt-change verdict reset)

> **Ready to apply:** `git apply planning-docs/010-viz-demo-fix.patch`
> (verified with `git apply --check`). The same change is inlined below.

## Symptom

After the attempt-reset fix landed in `src/agent_engine/viz.py`, running
`run-demo.sh` (the success scenario) still shows `test: no verdict` in the
badge panel once the `review`/`qa` verdicts land.

## Root cause

`viz_demo.py` fabricates `state` events whose `step_verdicts` payloads are
**deltas**, but the viz contract (and the live engine) is **full snapshots**:

- Live engine (`src/agent_engine/stages.py:234` and `:275`):
  `merged = {**state["step_verdicts"], step.name: verdict}` - every verdict
  state event carries the complete accumulated dict.
- Bump (`stages.py:353`): `{"step_verdicts": {}}` - semantically "clear", not
  "no delta".
- Viz (`viz.py` PAGE JS state case): `currentVerdicts = ev.step_verdicts`
  (replace semantics) - correct for the engine, and required for the bump
  reset to work (a merge of `{}` would be a no-op and break the reset).

The demo emits, e.g., `{"step_verdicts": {"review": "pass"}}`, which replaces
the snapshot and drops `test` → badge renders `test: no verdict`. The qa-fail
event (`{"review": "pass", "qa": "fail"}`) has the same problem. No live run
ever emits such deltas, so the live engine + new viz code are correct; the
demo fixture was out of contract.

## Fix (viz_demo.py, `run_scenario` success branch)

Replace the four delta dicts with full snapshots matching `stages.py` merge
semantics:

```python
    emit_node(bus, "dev", {"attempt": 1}, flood=flood)
    emit_node(bus, "test", {"step_verdicts": {"test": "pass"}},
              kind="command")
    emit_node(bus, "review", {"step_verdicts": {"test": "pass",
                                                "review": "pass"}})
    if scenario == "failure":
        emit_node(bus, "qa", ok=False)
        bus.publish({"type": "run_finished", "success": False, "attempts": 1})
        return

    emit_node(bus, "qa", {"step_verdicts": {"test": "pass",
                                            "review": "pass",
                                            "qa": "fail"}})
    emit_node(bus, "bump", {"attempt": 2, "step_verdicts": {}})
    emit_node(bus, "dev")
    emit_node(bus, "test", {"step_verdicts": {"test": "pass"}},
              kind="command")
    emit_node(bus, "review", {"step_verdicts": {"test": "pass",
                                                "review": "pass"}})
    emit_node(bus, "qa", {"step_verdicts": {"test": "pass",
                                            "review": "pass",
                                            "qa": "pass"}})
```

Changes vs current:

| event | current (delta) | fixed (full snapshot) |
|---|---|---|
| review a1 | `{"review": "pass"}` | `{"test": "pass", "review": "pass"}` |
| qa a1 (fail) | `{"review": "pass", "qa": "fail"}` | `{"test": "pass", "review": "pass", "qa": "fail"}` |
| review a2 | `{"review": "pass"}` | `{"test": "pass", "review": "pass"}` |
| qa a2 (pass) | `{"review": "pass", "qa": "pass"}` | `{"test": "pass", "review": "pass", "qa": "pass"}` |

`test` events already match (full snapshot at that point is exactly
`{"test": "pass"}`); the bump `{"attempt": 2, "step_verdicts": {}}` is already
correct.

### Optional fidelity notes (not required for the bug)

- `dev` a1 state carries `{"attempt": 1}` - a live dev node returns
  `{"failed": False}` with no `attempt` field (only the bump carries
  `attempt`). Harmless (verdictAttempt is already 1 from `run_started`) but
  slightly unfaithful to a live stream.
- `emit_node` publishes `state` before `node_finished` - matches live order
  (state comes from the node's return, emitted at node completion).

## Verification (already performed)

Throwaway script (opencode temp dir, since viz_demo.py can't be edited in
planner mode) did two things:

1. **Documented the bug**: drained the current `run_scenario(bus, "success")`
   stream - `state: {"step_verdicts": {"review": "pass"}}` etc., i.e. deltas.
2. **Replayed the fixed full-snapshot stream through the real PAGE JS** (node
   + the DOM-shim harness from `tests/test_viz.py`): all 8 badge snapshots OK
   - in particular at the qa-fail moment badges are
   `["test: pass", "review: pass", "qa: fail"]` and after the bump `[]`
   (attempt reset), then attempt 2 accumulates `test: pass` → `review: pass`
   → `qa: pass`.

## Suggested follow-up test

Add a `TestDemo` assertion (tests/test_viz.py already imports viz_demo and
drains the bus) that each non-bump `state` event's `step_verdicts` equals the
full expected snapshot for that point in the run - e.g. the qa-fail event must
contain `test`, `review`, and `qa` keys. This pins the demo to the engine's
full-snapshot contract and would have caught this bug.

## Outcome (COMPLETED)

- The viz_demo.py fix is applied (full-snapshot dicts at every verdict
  event; bump unchanged).
- The follow-up test landed as `test_demo_step_verdicts_are_full_snapshots`
  in the `TestDemo` class (tests/test_viz.py): it drains the demo bus and
  asserts the exact ordered `step_verdicts` sequence, including the bump's
  `{}` reset.
- Full suite: 329 passed (328 pre-change + the new demo test).
- User confirmed the demo no longer shows `test: no verdict` after the
  review/qa verdict events.

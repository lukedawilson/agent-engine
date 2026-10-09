# Viz Log Clarity — Implementation Plan

> **Status: PLANNED**

> **For agentic workers:** Use bite-sized task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three log/attempt display shortcomings surfaced during the first real `--viz` loop run:

1. **Attempt shows `attempt –/–` for the whole first attempt.** The page only learns `attempt` from `state` events, and the initial state's `attempt: 1` is never emitted (initial inputs are not node writes). `bump` is the first node to write `attempt`, at the *end* of attempt 1. Fix: `run_started` carries the attempt; the page renders `attempt 1/10` immediately and **never** renders an em-dash.
2. **Log shows steps that are not in the graph** (`bump`). The diagram deliberately omits `bump` (plan 002), but its `node_started`/`node_finished` events still become log lines. Fix: the page only logs events for nodes present in the `/topology` `nodes` set it already fetches.
3. **`✔ test passed` is misleading** — it means "test *node* finished without exception", not "verdict PASS" (the first test run actually failed and retried via bump). Fix: completion lines read `✔ X completed`, with the verdict appended when known — `✔ test completed (verdict: FAIL)` / `(verdict: PASS)` — and no verdict clause for steps without verdicts (dev, port_sweep, commit, success).
4. **A verdict-failed step turns green** — today node completion (`ok: true`) always paints the node green, even when the step's verdict was FAIL, and the red only lasts until the next render. Fix: a step whose latest verdict is `fail` stays **red on the graph** until that step is re-run (the next `node_started` flips it to amber/running; a later verdict/pass verdict recolors it).

**Architecture:** Two tiny protocol-adjacent changes and one JS-only change, all inside `viz.py`'s `PAGE` plus the `run_started` payloads in `graph.py` and `viz_demo.py`:

- `run_started` gains `attempt: start_state["attempt"]` (correct for resume — the checkpoint's attempt — and 1 for fresh runs). `translate`, the event whitelist, `/topology`, and the server are untouched.
- `PAGE` JS `handle()`:
  - `run_started` sets `attempt` from the event; `updateAttempt()` never renders `–` — unknown attempt renders `attempt ?/N`.
  - `node_started` / `node_finished`: skip logging when the node is not in `nodeIds` (state events are still processed — badges/attempt must keep updating).
  - `node_finished` with `ok: true` logs `✔ X completed`; with `ok: false` logs `✘ X errored`. Verdicts are attached **order-independently**: the completion line is buffered (`pendingCompletion`); it is flushed (a) immediately when a `state` event's `step_verdicts` provides a verdict for the pending node, or (b) when the next event arrives (next `node_started`, `run_started`, or `run_finished`). This avoids depending on whether the updates part precedes the tasks-end part in LangGraph v2 streams — the verdict is looked up in `currentVerdicts` at flush time.
  - Graph colors become a single precedence function `statusOf(node)` used by `renderGraph()`: **running > verdict-fail > verdict-pass > ok-status > pending**. Two sticky sets (`verdictFail` / `verdictPass`) are updated only when a `state` event's `step_verdicts` **contains a key** (fail → move into `verdictFail`; pass → into `verdictPass`). `bump`'s reset (`step_verdicts: {}`) has no keys, so it leaves the sets alone — red sticks through the bump and stays until the node's next `node_started` (running wins by precedence) or a new verdict. Order-independent for the same reason as Task 3's buffering, and distinct from `currentVerdicts`, which still drives the badges (reset per attempt, unchanged).

**Tech Stack:** unchanged — Python ≥3.12, pytest, LangGraph 1.2.9 (repo venv), stdlib-only server, Mermaid.js v11 via CDN. No new dependencies.

## Global Constraints

- TDD red→green→refactor for every task
- Mock policy unchanged (repo rule): no new seams; `PAGE` changes are covered by the existing string-assertion pattern (`test_page_constant_*`); the `run_started` payload change is covered in `test_viz.py` and `test_cli.py`
- Protocol amendment (documented in 001's style): `run_started` gains `attempt`. `state` whitelist, `node_started`/`node_finished`/`run_finished` shapes unchanged
- Full suite green at the end of every task: `.venv/bin/python -m pytest tests/ -q`

## Locked decisions (from user)

| Decision | Choice |
|---|---|
| Attempt display | Starts at `attempt 1/10` from `run_started`; **never** an em-dash — `attempt ?/N` is the only fallback |
| Log scope | Only nodes in the drawn graph are logged (`bump` invisible); `state: failed`, `run started/finished`, and error lines remain |
| Completion wording | `✔ X completed`, `✘ X errored`; ` (verdict: PASS)` / ` (verdict: FAIL)` appended when a verdict is known for X; no verdict clause otherwise |
| Verdict attachment | Page-side buffering (flush-on-next-event), order-independent of the LangGraph tasks/updates emission order |
| Failed-step color | Red persists until the step is re-run (`node_started` → amber; new verdict recolors); sticky verdict sets survive bump's reset |
| Diagram | Unchanged (plan 002) — `bump` stays off the diagram, off the log |

---

### Task 1: `run_started` carries `attempt`

**Files:**
- Modify: `src/agent_engine/graph.py` (`run_pipeline` publish site), `viz_demo.py` (same), `src/agent_engine/viz.py` (`PAGE` JS only)
- Test: `tests/test_viz.py`, `tests/test_cli.py`

**Interface:**
- `bus.publish({"type": "run_started", ..., "attempt": start_state["attempt"]})` in `graph.py`; `viz_demo.py` publishes `attempt: 1` (success and failure scenarios).
- `PAGE` `handle()`: `case "run_started": if (ev.attempt !== undefined) { attempt = ev.attempt; }` and `updateAttempt()` fallback becomes `attempt ?/N` (no `–` anywhere in the template).

- [ ]**Step 1: Failing tests** — assert the captured `run_started` event includes `attempt: 1` (lifecycle test in `test_cli.py`; demo event assertions in `test_viz.py`); assert `"attempt ?/"` in `PAGE` and `"\u2013/\u2013"` **not** in `PAGE`.
- [ ]**Step 2: Implement; green + refactor.**

### Task 2: Log only drawn nodes

**Files:**
- Modify: `src/agent_engine/viz.py` (`PAGE` JS only)
- Test: `tests/test_viz.py`

**Interface:**
- `node_started` and `node_finished` cases guard with `if (!nodeIds.has(ev.node)) { break; }` — but still update `nodeStatus`/`renderGraph` only for drawn nodes; `state` events are processed unconditionally (badges/attempt).

- [ ]**Step 1: Failing tests** — assert the guard exists in `PAGE` (e.g. `"nodeIds.has(ev.node)"` in the JS); `test_viz.py` string assertions.
- [ ]**Step 2: Implement; green + refactor.**

### Task 3: Completion lines with verdicts

**Files:**
- Modify: `src/agent_engine/viz.py` (`PAGE` JS only)
- Test: `tests/test_viz.py`

**Interface:**
- `pendingCompletion` buffer; `flushPending()` renders `✔ X completed` / `✘ X errored`, appending ` (verdict: PASS|FAIL)` when `currentVerdicts[X]` is known at flush time; flush triggers: verdict-bearing `state` event, next `node_started`, `run_finished`.
- `state` events keep driving `updateBadges()` (badges unchanged).

- [ ]**Step 1: Failing tests** — assert `"completed"` and `"verdict"` appear in `PAGE`; assert `" passed"` (the old completion suffix) does not.
- [ ]**Step 2: Implement; green + refactor.**

### Task 4: Failed verdicts stay red until re-run

**Files:**
- Modify: `src/agent_engine/viz.py` (`PAGE` JS only)
- Test: `tests/test_viz.py`

**Interface:**
- `verdictFail` / `verdictPass` Sets; `state` handler adds/removes per `step_verdicts` key **only when the key is present** (bump's empty reset is a no-op).
- `statusOf(node)` precedence `running > verdictFail > verdictPass > ok-status > pending`; `renderGraph()`'s `classLines` uses `statusOf(n)` instead of `nodeStatus[n] || "pending"`.
- `node_started`/`node_finished` keep writing `nodeStatus` as today; the verdict sets win at render time, so a green "node ok" paint cannot mask a fail verdict in either event order.

- [ ]**Step 1: Failing tests** — assert the precedence helper and sticky sets exist in `PAGE` (string assertions: e.g. `"statusOf"`, `"verdictFail"`, `"verdictPass"` in `PAGE`).
- [ ]**Step 2: Implement; green + refactor.**

### Task 5: Manual smoke

**Files:** none

- [ ]**Step 1:** `./run-demo.sh --no-browser` — fresh page shows `attempt 1/3` immediately; success scenario: `dev completed` (no verdict), `test completed (verdict: FAIL)` → **test node turns red and stays red** through bump (bump invisible in log) and the second `dev completed` → test re-run flips it to running (amber) → `test completed (verdict: PASS)` turns it green → `review completed (verdict: PASS)` → … → `success completed`; badges still flip with bump; failure scenario: `test errored` + failure banner.

## Verification

1. `.venv/bin/python -m pytest tests/ -q` green.
2. Manual smoke (Task 5) — **user eyeballs.**
3. Real `agent-engine examples/self/pipeline.yaml --plan <doc> --viz` run — **user triggers** (makes LLM calls): attempt 1/N from the start, no `bump` lines, verdicts on every completion line that has one, failed steps red until re-run.

## Amendments

- 2026-08-27: `run_started` event protocol extended with `attempt` (plan 001's protocol table predates it). `state` whitelist and all other event shapes unchanged.

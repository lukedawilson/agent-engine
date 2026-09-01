# Viz initial-state race: first stage never flashes — Implementation Plan

> **Status: PLANNED** — written on user instruction: plan and stop. Implementation starts on an explicit go.

> **For agentic workers:** Use bite-sized task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the initialization error in the viz page: while the loop is running, the first stage (`dev`) never flashes amber/pulses and never appears in the event log — even though the pipeline and server-side event stream are correct. Once the first stage finishes, the viz behaves normally.

**Root cause (verified):** A client-side initialization race in the `PAGE` JS. `nodeIds` (the set of drawn nodes) is populated only when the `/topology` fetch resolves, but the SSE connection replays its backlog — `run_started`, `node_started(dev)`, heartbeats — immediately on subscribe. `handle()` guards node events with `if (!nodeIds.has(ev.node)) { break; }`, so the first stage's `node_started`/`node_finished` are silently dropped when they arrive before the topology fetch resolves: `nodeStatus["dev"]` is never set, hence no flash, no `▶ dev running` log line, no elapsed line. Later stages work because the topology has loaded by then.

Empirical repro: headless Chrome against the real server with a pre-populated backlog showed the log contained only `run started: …` — the `node_started(dev)` was dropped. Additional finding: in some headless runs the `/topology` fetch had still not resolved by dump time, so a fix that merely defers `new EventSource("/events")` until after the fetch resolves has a worse failure mode (a stalled `/topology` would kill the event log too). Therefore the fix buffers events instead: the event stream stays open immediately, events are held until topology is ready, then flushed in order.

**Architecture:**

- Client-side only. All changes are in the `PAGE` constant in `src/agent_engine/viz.py`.
- Add `topologyReady` flag + `pendingEvents` array. `es.onmessage` parses the event; while `!topologyReady` it appends to `pendingEvents` and returns; otherwise it calls `handle(ev)` as today.
- The `/topology` `.then` sets subject/mermaidSource/nodeIds, initializes mermaid, sets `topologyReady = true`, flushes `pendingEvents` through `handle()` in order, then calls `renderGraph()` once.
- The `.catch` logs the failure, sets `topologyReady = true`, and flushes — the event log keeps working even if the topology fetch fails.
- A 5 s fallback `setTimeout`: if still `!topologyReady`, force-ready, log a notice, and flush — the log stays alive even if `/topology` stalls (observed in headless Chrome).
- The `nodeIds.has(ev.node)` guards stay untouched: they encode drawn-nodes-only logging (e.g. `bump` is not drawn) and existing tests assert them.

**Tech Stack:** unchanged — Python ≥3.12, pytest, LangGraph 1.2.9 (repo venv), stdlib-only server, Mermaid.js v11 via CDN. No new dependencies. No protocol changes: no new event types, no event shape changes, server untouched.

## Global Constraints

- TDD red→green→refactor for every task
- Mock policy unchanged (repo rule): no new seams; `PAGE` changes covered by the existing string-assertion pattern (`test_page_constant_*`); no JS test runner — assertions are Python strings on `PAGE`
- Full suite green at the end of every task: `.venv/bin/python -m pytest tests/ -q`
- No protocol amendment needed (client-only fix)

## Locked decisions (from user + investigation)

| Decision | Choice |
|---|---|
| Scope | Exactly the initialization race. No other viz changes. |
| Implementation timing | Plan and stop. No code until an explicit go. |
| Fix location | `PAGE` JS in `src/agent_engine/viz.py` only; server and `translate()` untouched |
| Mechanism | Client-side event buffering (`topologyReady` + `pendingEvents`), flushed in order on topology load — not deferring `EventSource` creation |
| `/topology` failure | Log line + flush anyway (event log survives without the graph) |
| Stalled `/topology` fallback | 5 s `setTimeout` force-ready + flush with a notice line |
| `nodeIds.has` guards | Kept as-is (drawn-nodes-only logging is intentional and tested) |
| Out of scope (noted, not fixed) | EventSource auto-reconnect re-subscribes and replays the whole backlog → duplicate log lines + stale "running" states. Separate future plan if desired. |

---

### Task 1: Buffer SSE events until topology is ready

**Files:**
- Modify: `src/agent_engine/viz.py` (`PAGE` JS)
- Test: `tests/test_viz.py`

**Interface (JS):**
- `var topologyReady = false; var pendingEvents = [];`
- `es.onmessage` wrapper: parse event; if `!topologyReady` → `pendingEvents.push(ev); return;` else `handle(ev)`.
- `/topology` `.then`: after `nodeIds`/`mermaidSource` are set and mermaid initialized → `topologyReady = true;` → `pendingEvents.forEach(handle); pendingEvents = [];` → `renderGraph();`
- `.catch`: `logLine("failed to load topology")`, `topologyReady = true`, flush.
- `setTimeout(..., 5000)`: if `!topologyReady` → `topologyReady = true`, `logLine("topology load timed out — event log only")`, flush.

- [ ]**Step 1: Failing tests** — page-constant string assertions in `tests/test_viz.py::TestServer`, following the existing `test_page_constant_*` convention: assert `"topologyReady"` and `"pendingEvents"` in `PAGE`; assert the flush appears in the topology `.then` (e.g. `"pendingEvents.forEach(handle)"`) and in `.catch`; assert the 5 s fallback exists (e.g. `"topology load timed out"`).
- [ ]**Step 2: Implement; green + refactor.**

### Task 2: Regression verification (behavioral)

**Files:** none (possibly extend tests if a gap appears)

- [ ]**Step 1:** Full suite: `.venv/bin/python -m pytest tests/ -q` — existing page-constant tests (`test_page_constant_has_nodes_filter_hook`, `test_page_constant_logs_only_drawn_nodes`, …) and server tests stay green, proving the `nodeIds.has` guards and event protocol are unchanged.
- [ ]**Step 2:** Headless Chrome repro (same technique as the diagnosis): real server with a pre-populated backlog (`run_started` + `node_started(dev)`), `--dump-dom`. The dump must now contain the `▶ dev running` log line. (Mermaid CDN is blocked in headless, so graph rendering is not assertable this way — the log line is the signal.)
- [ ]**Step 3:** Manual smoke: `./run-demo.sh` in a real browser — `dev` flashes amber and pulses while "running", and a mid-run page reload shows the currently-running stage flashing immediately (backlog replayed then rendered).

## Verification

1. `.venv/bin/python -m pytest tests/ -q` green.
2. Headless Chrome dump shows `▶ dev running` (Task 2 Step 2).
3. Manual eyeball: `./run-demo.sh` — first stage flashes while running, all later stages flash, log shows every stage. **User eyeballs.**

## Amendments

- (none yet)

## Follow-up candidate (not in scope)

- EventSource auto-reconnect replays the backlog on every reconnect → duplicate log lines and stale "running" states after a network blip. If it becomes annoying, plan a client-side dedup (e.g. per-event id/seq + last-seen tracking) or a server-side cursor.

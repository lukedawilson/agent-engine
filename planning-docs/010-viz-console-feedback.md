# 010 — Viz console panel: feedback backlog

> **Status: COMPLETED**

## Context

Feedback on the **in-flight, uncommitted plan-008 implementation** in the
working tree (observed 2026-10-09, on top of `1641dea`):

- `src/agent_engine/graph.py` — `ConsoleCapture` attach/detach (~lines 186-218)
- `src/agent_engine/viz.py` — dual-backlog `VizBus` (`console_maxlen`, `_seq`),
  `_Tee`/`ConsoleCapture`, new per-stage accordion UI (`#stages` sections) +
  `ansiToHtml` — ~434 insertions
- `tests/test_cli.py`, `tests/test_graph.py`, `tests/test_viz.py` — the
  implementation's new tests

These changes are **not yet committed** and belong to whoever is implementing
plan 008 — this note must not be swept into unrelated commits.

## Feedback (verbatim)

1. Core terminal panel functionality working
2. Current step no longer flashes on the graph (solid colour only)
3. New terminal panel doesn't tail properly
4. For stages that haven't run, when you expand them, there's just a black
   strip — should have some text

## Status (2026-10-09)

All four items are resolved in the working tree and verified:

- **2 — flash:** fixed — `pulse` keyframes restored (`viz.py:391-392`);
  verified in the demo (running node pulses again).
- **3 — tailing:** verified working — see below; the demo now floods via
  `--flood` (bare `./run-demo.sh` defaults to 600 lines).
- **4 — black strip:** fixed — `addPlaceholder()` (`viz.py:573-578`) renders
  muted "No output" in every stage console; removed on first append (`:700`),
  re-added by `clearConsoles` (`:680`). Verified in the demo.

## Grounded pointers

### 1. Core functionality — working ✓

No action.

### 2. Graph flash regression — **fixed, verified**

The diff **deleted** the pulse animation at implementation time; it is now
restored (`viz.py:391-392`):

```css
.running > * { animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
```

What *survives* in `viz.py`:
- mermaid `classDef running fill:#1976d2,stroke:#1976d2,color:#fff` (line 549)
- `nodeStatus[ev.node] = "running"` on node_started (line 851)

The restored `.running` rule targets the graph's SVG node group only — not
the new `.status-running` stage-header class, which reuses a similar name and
must not pulse.

### 3. Terminal panel doesn't tail — **verified working**

The code evolved past the original candidates while this note was parked:

- `tailSection` (`viz.py:691-695`) now unconditionally snaps to bottom; the
  old 24px guard is gone from it.
- `appendConsole` (`:697-721`) reads `nearBottom(pre)` (the 24px guard,
  `:687-689`) *before* mutating, evicts the first `.cline` past
  `MAX_CONSOLE = 500` (maintaining the "…N lines omitted" counter row), then
  re-anchors with `pre.scrollTop = pre.scrollHeight` when stuck.
- Expand tails via `requestAnimationFrame` (header click `:596`,
  `expandStage` `:659`) — the layout-timing candidate is addressed.
- Replay merge: `VizBus.subscribe()` takes the backlog snapshot and registers
  the subscriber under the same lock, so `publish()` either lands entirely
  before the snapshot (replayed) or entirely after (delivered live) — no
  gap/dup. `/events` SSE serves post-replay events in order.

Verification performed (2026-10-09):

- **Live SSE**: `viz_demo.py --flood 600` → 600/600 flood lines received in
  strict publish order, `run_started` first, `run_finished` last.
- **Late-subscribe replay**: 600 pre-published console events → new subscriber
  received `run_started` + the last 500 console lines (101..600) +
  `node_finished`, merged in `_seq` order.
- **Real browser** (headless Chrome driving the actual PAGE JS): 700-line
  live flood → stage panel **pinned to bottom** (scroll delta 0), 500
  `.cline`s, "…N lines omitted" counter, last line = newest; after scrolling
  up, 10 more lines did **not** yank the panel (scrollTop unchanged).

To eyeball it yourself: `./run-demo.sh` (defaults to `--flood 600`).

### 4. Black strip for stages that haven't run — **fixed, verified**

`addPlaceholder(pre)` (`viz.py:573-578`) now appends a muted "No output"
div (`.stage-placeholder`, CSS `:432`) to every stage console at
`ensureSection` (`:613`) and `clearConsoles` (`:680`); the first
`appendConsole` removes it (`:700`). Unrun stages expand to a dark panel with
the muted placeholder instead of an empty black strip. Verified in the demo
and in the headless-Chrome check (review stage showed "No output").

## Parking notes

- All four items are resolved and verified — this note is now a record of the
  feedback loop, not a backlog.
- The uncommitted working-tree state (plan-008 implementation + stage
  deletion + demo flood) was committed separately from anything unrelated.

# 010 — Viz console panel: feedback backlog

> Status: **backlog note** — deferred for a more urgent issue. Not a plan yet;
> promote to a plan (or fold into plan 008's implementation) when we return.

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

## Grounded pointers

### 1. Core functionality — working ✓

No action.

### 2. Graph flash regression (solid colour, no pulse)

The diff **deleted** the pulse animation and nothing replaced it:

```css
-  .running > * { animation: pulse 1.2s ease-in-out infinite; }
-  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
```

What *survives* in `viz.py`:
- mermaid `classDef running fill:#1976d2,stroke:#1976d2,color:#fff` (line 549)
- `nodeStatus[ev.node] = "running"` on node_started (line 851)

So the current node gets a solid blue fill with no animation — exactly the
reported symptom. **Fix direction:** restore a pulse keyframe targeted at the
graph's running node only (`.running` on the mermaid SVG node group), *not* the
new `.status-running` stage-header class — the old selector `.running > *` was
scoped to the graph; the new stage UI reuses a similar class name.

### 3. Terminal panel doesn't tail

Locations (all in `PAGE` JS, `viz.py`): `tailSection(section)`,
`appendConsole(section, html)`, `expandStage(node)`, and the header-click
handler in `ensureSection`.

Candidate causes to investigate when we pick this up:

- **Eviction breaks bottom-anchoring:** `appendConsole` removes the first
  `.cline` past `MAX_CONSOLE = 500` but never compensates `scrollTop` for the
  removed line's height — a panel stuck to the bottom drifts up by one line per
  eviction, so past 500 lines it stops tailing.
- **`tailSection` guard**: only scrolls when
  `pre.scrollHeight - pre.scrollTop - pre.clientHeight < 24`; if the user (or
  eviction) is just outside that window, new lines never re-anchor.
- **Expand timing:** `expandStage`/header-click call `tailSection` right after
  `display:none → block`; `scrollHeight` may not be laid out yet at that
  moment (content was appended while collapsed).
- **Replay merge:** `VizBus.subscribe()` now merges lifecycle + console
  backlogs by `_seq`; verify the `/stream` endpoint still serves post-replay
  events in order (console events arriving before the subscriber's replay
  completes could be missed/duplicated).

### 4. Black strip for stages that haven't run

`ensureSection(node)` creates an empty
`<pre class="stage-console">` (CSS: `background: #1e1e1e; padding: 8px 10px`)
for **every** node at topology load. For stages with zero console events,
expanding shows an empty dark box — the "black strip".

**Fix direction:** placeholder text while the console has no `.cline`
children — e.g. a muted `.omitted`-style div: "This stage hasn't run yet" /
"No output" — removed on the first `appendConsole`.

## Parking notes

- This note intentionally covers symptoms + pointers only; root-cause
  confirmation and TDD tasks come when we return to it.
- Remember the uncommitted plan-008 working-tree state (5 files listed above)
  when committing anything else in the meantime.

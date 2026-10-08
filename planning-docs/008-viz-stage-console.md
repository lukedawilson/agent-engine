# Per-Stage Console Output in the Sidebar — Implementation Plan

> **Status: PLANNED**

> **For agentic workers:** Use bite-sized task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display the agent engine's console output (terminal colours preserved) in the viz sidebar, nested under the stage that produced it — matching the user intent:

> "display the console output from the agent engine (including the terminal colours) as part of the sidebar. Output should be nested under the stage (e.g. '> dev running'). Section should be collapsible. Automatically collapse completed stages, expand the current one. Live tail."

Today the engine's `print()` lines (stage banners like `[unit] Running dev agent...`, verdict lines, tracebacks) and the OpenHands SDK's `rich`-formatted output (visualizer panels on stdout, log records via `RichHandler` on stderr) go straight to the real terminal, invisible to the page. This plan captures that stream (with its ANSI colour codes intact), ships it to the page as a new event, and renders each node's console inside its own collapsible stage section.

**Architecture:** Five pieces, all in-repo:

1. **`ConsoleCapture`** (new class in `viz.py`, the protocol owner): a pair of write-through proxy streams (`_Tee`) that swap in for `sys.stdout` / `sys.stderr`, split output into lines, attribute each line to `watch.current()` (the node currently running, or `None`), and publish a new `console` event per line. ANSI escape sequences pass through **verbatim** — colour parsing is frontend-only. Verified mechanically: rich 15.0.0's `Console.file` property resolves `sys.stderr` **lazily at render time** (`console.py:759`) and `Console.is_terminal` reads `self.file.isatty()` at render time (`console.py:931`), so swapping `sys.stderr` after SDK import redirects the SDK's `RichHandler(Console(stderr=True))` output through our proxy — and a proxy whose `isatty()` delegates to the real stream captures colours **iff the real console is a tty** (an honest mirror; no colour forcing, so piped output stays clean).
2. **Wiring in `run_pipeline`** (`graph.py`): `capture.attach()` right after `watch` is created, `capture.detach()` as the last statement of the existing `finally` (after `run_finished` is published). Capture is bus-driven, so programmatic `viz_bus` callers (tests) capture too. Bus creation is untouched.
3. **`VizBus` replay split** (`viz.py`): console volume must not evict lifecycle events from the replayed backlog (a tab opened or refreshed mid-run re-subscribes, and "replay the most recent N of everything" — today's `deque(maxlen)` behaviour — is exactly the failure mode once console lines dominate). The bus keeps two backlogs: retained events (everything except `console`/`heartbeat`, bounded by the existing `maxlen`) and console events (bounded by a new `console_maxlen=500`). Heartbeats are delivered live but never replayed — stale `elapsed` is useless and the next live heartbeat arrives ≤2s. `publish()` stamps each event with an internal monotonic `_seq` under the bus lock (payload untouched); `subscribe()` replays the two backlogs merged in `_seq` order. Live delivery is unchanged: every subscriber receives every event.
4. **Protocol amendment**: new `console` event — `{"type": "console", "node": <str|null>, "stream": "stdout"|"stderr", "text": "<raw line, ANSI intact>"}`.
5. **`PAGE` frontend**: the flat `#log` list is replaced by `#stages` (one collapsible `<section class="stage">` per drawn node, in `/topology` order — header row + console `<pre>`) plus a small `#run-log` for lifecycle lines and node-less console lines. Auto-expand the running stage, auto-collapse on finish, live-tail the expanded stage's console. A hand-rolled `ansiToHtml()` renders ANSI SGR codes to inline styles (no new CDN dependency — mermaid remains the only one).

**Tech Stack:** unchanged — Python ≥3.12, pytest, LangGraph 1.2.12, openhands-sdk 1.17.0 + rich 15.0.0 (repo venv), stdlib-only server, Mermaid.js v11 via CDN. No new dependencies.

## Global Constraints

- TDD red→green→refactor for every task
- Mock policy unchanged (repo rule): `run_agent` remains the only permitted stub seam. `ConsoleCapture` is unit-tested directly with `io.StringIO` targets and a stub watch; no new seams
- `PAGE` JS is covered by the existing string-assertion pattern (`test_page_constant_*`); existing page-constant assertions are updated where the new markup conflicts, but their tokens are preserved: `completed`, `errored`, `verdict`, no `" passed"`, `nodeIds.has(ev.node)`
- Protocol amendment (documented in 001's style): new `console` event. All existing event shapes unchanged
- Full suite green at the end of every task: `.venv/bin/python -m pytest tests/ -q`
- No new runtime or CDN dependencies; mermaid stays the only CDN script

## Locked decisions (from user / research)

| Decision | Choice |
|---|---|
| Console placement | Nested under the stage: one collapsible section per drawn node; header reads `▸ dev` (pending, grey) / `▾ dev running` (blue, expanded — matches the user's example `'> dev running'`) / `▸ dev completed` (green, ` (verdict: PASS\|FAIL)` appended when the state event arrives) / `▸ dev errored` (red) |
| Collapse behaviour | `node_started(X)` expands X and collapses all others (scroll header into view); `node_finished(X)` collapses X; `run_finished` collapses all; manual toggle (▸/▾ glyph) works between boundaries |
| Live tail | On console append, scroll to bottom only if the section is expanded **and** the user is near the bottom (`scrollHeight - scrollTop - clientHeight < 24`); otherwise leave the user's scroll position alone |
| Colour capture | Stream-level only (`sys.stdout`/`sys.stderr` proxies). Colours captured iff the real console is a tty — no forcing (would pollute piped output). The SDK's visible output IS captured: agent step/command panels come from `DefaultConversationVisualizer` printing to a lazily-resolved `Console()` on `sys.stdout` (`visualizer/default.py`), and log records via `RichHandler(Console(stderr=True))` — both resolve their stream at render time. Documented bypasses: subprocess writes to fd 1; and under `CI`/`LOG_JSON` the SDK installs a plain `logging.StreamHandler` bound to the real `sys.stderr` at import time (`logger.py`) — no colours there anyway |
| ANSI rendering | Frontend-only, hand-rolled `ansiToHtml()`: 16/256/truecolor SGR, bold/italic/underline, reset; OSC/erase-line/cursor codes ignored; input escaped before styling |
| Event shape | `console` with `node` (nullable), `stream`, `text` (ANSI intact). Node-less or unknown-node lines go to `#run-log` |
| Caps | `MAX_LINE = 8000` chars per captured line (truncated with `…` — SDK state dumps are huge); `MAX_CONSOLE = 500` lines per stage (top `…N lines omitted` counter row); bus replay: lifecycle backlog bounded by the existing `maxlen` (default 500 — generous once heartbeats stop competing), console replay bounded by `console_maxlen = 500` most recent lines. Per-subscriber live queues stay unbounded (pre-existing design; console volume amplifies the slow-client memory growth — fine for a loopback page) |
| Attribution | `watch.current()` — exact for this repo's linear pipelines (`tasks`-start parts are emitted before inline single-task execution, so `watch.start` always lands before the node body prints). Concurrent branches (not used by shipped examples) could mis-attribute; accepted stream-level heuristic |
| Uncaptured output | `run_pipeline`'s final `FAILED after …` print happens after detach — accepted (duplicates `run_finished` info). The `Live graph viz: …` URL print happens before the bus/capture exist — still visible on the real terminal only |
| Security | Console events flow only to loopback SSE subscribers — same trust boundary as the existing page; still HTML-escaped before insertion |

---

### Task 1: `ConsoleCapture` in `viz.py`

**Files:**
- Modify: `src/agent_engine/viz.py` (new `ConsoleCapture` class + `_Tee` helper, `MAX_LINE = 8000` module constant)
- Test: `tests/test_viz.py` (new `TestConsoleCapture`)

**Interface:**

```python
class ConsoleCapture:
    """Tees sys.stdout/sys.stderr into the viz bus, line by line, attributed
    to the node NodeWatch currently reports (None when idle)."""
    def __init__(self, bus, watch) -> None
    def attach(self) -> None   # swap sys.stdout/sys.stderr for _Tee proxies; RuntimeError if already attached
    def detach(self) -> None   # flush partial lines, restore originals; idempotent
```

- `_Tee(capture, stream, target)` per stream: `write(s)` accepts `str` (bytes decoded utf-8/replace) and returns `len(s)` (TextIO contract), appends to a buffer, splits on `\n`, strips trailing `\r` per line, publishes each complete line; write-through to `target` with **no auto-flush**. `flush()` → `target.flush()` only (a partial buffer is published only on newline or detach). `isatty()` and `__getattr__` delegate to `target` (encoding/fileno/etc. for rich + `logging.StreamHandler`). Per-proxy `threading.Lock`.
- Published event: `{"type": "console", "node": self._watch.current(), "stream": <"stdout"|"stderr">, "text": line}` with line truncated to `MAX_LINE` + `…` when over.

- [ ]**Step 1: Failing tests** — `TestConsoleCapture` in `tests/test_viz.py`, built directly on `VizBus()` + `io.StringIO` targets + a stub watch (fixed or None `current()`): complete-line splitting; ANSI preserved verbatim (`"\x1b[32mhi\x1b[0m"` round-trips); write-through to the target; two `write()` calls join into one published line; `\r\n` stripped; node attribution (stub → node, None → null); `attach()`/`detach()` swap and restore `sys.stdout`/`sys.stderr` under `monkeypatch` (assert identity restored); double `attach()` raises `RuntimeError`; 8001-char line truncated to 8000 + `…`; `isatty()` delegates to the target.
- [ ]**Step 2: Implement; green + refactor.**

### Task 2: `VizBus` replay split

**Files:**
- Modify: `src/agent_engine/viz.py` (`VizBus`)
- Test: `tests/test_viz.py` (extend `TestVizBus`)

**Interface:**
- `VizBus(maxlen=500, console_maxlen=500)` — `maxlen` bounds the retained backlog (every event except `console`/`heartbeat`; events without a `type` key count as retained, so existing bus tests are unaffected); `console_maxlen` bounds the console backlog. Heartbeats are delivered live but never replayed.
- `publish()` stamps each event with an internal monotonic `_seq` under the bus lock (payload untouched); `subscribe()` replays retained + console backlogs merged in `_seq` order, then registers for live delivery.

- [ ]**Step 1: Failing tests** — console spam beyond `console_maxlen` evicts only older console events: publish `run_started`, 600 console events, `node_started`; a new subscriber receives `run_started`, `node_started`, and exactly the last 500 console events, in publish order. A heartbeat published pre-subscribe is not replayed but IS delivered live post-subscribe. Existing `TestVizBus` tests stay green unchanged.
- [ ]**Step 2: Implement; green + refactor.**

### Task 3: Wire capture into `run_pipeline`

**Files:**
- Modify: `src/agent_engine/graph.py` (`run_pipeline` viz branch: create + attach after `watch`, detach in `finally`)
- Test: `tests/test_graph.py`, `tests/test_cli.py`

**Interface:**
- In the `if bus is not None:` block, after `watch = viz.NodeWatch()`: `capture = viz.ConsoleCapture(bus, watch); capture.attach()`.
- In the `finally:` — as the last statement, after the `run_finished` publish: `capture.detach()`.

- [ ]**Step 1: Failing tests** — `test_graph.py` stream-path test (existing `viz_bus=VizBus()` + `drain_events()` harness): assert a `console` event exists whose `text` contains the fake stage's `Running dev agent...` print and whose `node == "dev"` (the print runs inside the node, after `watch.start("dev")`). `test_cli.py` lifecycle test: assert `sys.stdout is` and `sys.stderr is` the pre-call streams after `main()` returns; assert the captured `run_started`/`run_finished` are still present (no regression).
- [ ]**Step 2: Implement; green + refactor.**

### Task 4: `PAGE` — stage sections, collapse, live tail

**Files:**
- Modify: `src/agent_engine/viz.py` (`PAGE` markup + JS)
- Test: `tests/test_viz.py` (new + updated `test_page_constant_*`)

**Interface:**
- Replace the flat `#log` list with `#stages` (flex:1, own scroll — one `<section class="stage">` per node in `/topology` `nodes` order, created at topology load) and `#run-log` (existing `logLine()` lifecycle lines + console events with `node` null or not in `nodeIds`; ANSI-rendered; `max-height: 25%`, own scroll).
- Stage section = header `<button class="stage-header">` (toggle glyph `▸`/`▾` + node name + status word) + `<pre class="stage-console">` (dark terminal background, `white-space: pre-wrap; word-break: break-all`). `collapsed` class hides the console.
- JS: `ensureSection(node)`; `setStageStatus(node, word)` using existing `statusOf()` for header colour; header text per the Locked decisions table; verdict suffix reuses plan 004's `pendingCompletion` buffering but writes the header text instead of a log line (flush on verdict-bearing `state` event, next `node_started`, `run_started`, or `run_finished`).
- `node_started(X)`: expand X, collapse others, `scrollIntoView({block: "nearest"})`. `node_finished(X)`: collapse X. `run_finished`: collapse all. `run_started`: clear all consoles + run-log (page shows one run per load).
- Console append: cap at `MAX_CONSOLE = 500` lines with a top `…N lines omitted` counter row; live-tail iff expanded and near bottom (`< 24`px threshold).

- [ ]**Step 1: Failing tests** — assert in `PAGE`: `"stage-header"`, `"stage-console"`, `"collapsed"`, `"scrollHeight"`, `"scrollTop"`, `"MAX_CONSOLE"`, `"console"`; keep/update existing tokens (`completed`, `errored`, `verdict` present; `" passed"` absent; `nodeIds.has(ev.node)` guard applied to console routing).
- [ ]**Step 2: Implement; green + refactor.**

### Task 5: `PAGE` — `ansiToHtml()`

**Files:**
- Modify: `src/agent_engine/viz.py` (`PAGE` JS)
- Test: `tests/test_viz.py`

**Interface:**
- `ansiToHtml(text)`: escape `& < >` first, then scan for ESC sequences: SGR `m` (params split on `;`: 0 reset; 1/22 bold; 3/23 italic; 4/24 underline; 30–37 / 90–97 fg; 40–47 / 100–107 bg; 39/49 default; `38;5;n`/`48;5;n` 256-colour via xterm cube `16 + 36r + 6g + b` / grey `8 + 10n`; `38;2;r;g;b`/`48;2;r;g;b` inline rgb); ignore OSC (`\x1b]…BEL`) and erase-line/cursor sequences; emit `<span style="…">` segments.
- Palette — 30–37: `#0c0c0c #c50f1f #13a10e #c19c00 #0037da #881798 #3a96dd #cccccc`; 90–97: `#767676 #e74856 #16c60c #f9f1a5 #3b78ff #b4009e #61d6d6 #f2f2f2`.
- Console lines (stage consoles and run-log) render through `ansiToHtml`; lifecycle `logLine()` lines stay plain.

- [ ]**Step 1: Failing tests** — assert in `PAGE`: `"ansiToHtml"`, `"\\x1b"`, `"38;5"`, `"38;2"`.
- [ ]**Step 2: Implement; green + refactor.**

### Task 6: Demo console events

**Files:**
- Modify: `viz_demo.py`
- Test: `tests/test_viz.py` (extend `TestDemo`)

**Interface:**
- `emit_node` additionally publishes 2–3 `console` events per node: one plain stdout line (`[subject] Running <name> agent...`), one ANSI-coloured stderr line (`"\x1b[33m[SDK] step 1 — thinking\x1b[0m"`), attributed to the node; plus one node-less console line after `run_started` (exercises `#run-log`).

- [ ]**Step 1: Failing tests** — extend the demo event assertions to include the console events (node attribution + ANSI bytes intact).
- [ ]**Step 2: Implement; green + refactor.**

### Task 7: README + manual smoke

**Files:**
- Modify: `README.md` (extend the viz sentence: per-stage console output with ANSI colours preserved, collapsed when complete, live-tailed while running)

- [ ]**Step 1:** Update README.
- [ ]**Step 2:** `./run-demo.sh --no-browser` — **user eyeballs**: stages appear with their consoles; success scenario dev console fills and auto-scrolls while running, collapses on completion with ` (verdict: …)` on checks; ANSI-coloured demo lines render in colour; failure scenario shows `errored` sections.
- [ ]**Step 3:** Real run `agent-engine examples/self/pipeline.yaml --plan <doc> --viz` — **user triggers** (makes LLM calls): real SDK rich output (coloured) appears under the running stage, live-tailed.

## Verification

1. `.venv/bin/python -m pytest tests/ -q` green.
2. Manual smoke (Task 7 Step 2) — user eyeballs.
3. Real `--viz` run (Task 7 Step 3) — user triggers.

## Amendments

- 2026-10-08: New `console` event protocol (`{type, node, stream, text}`) — plan 001's protocol table predates it. All existing event shapes unchanged. Capture is stream-level (`sys.stdout`/`sys.stderr` proxies), not fd-level; the SDK's own output (the visualizer's `Console()` on `sys.stdout`, Python `logging` → rich → `sys.stderr`) is captured, subprocess writes to fd 1 are not.
- 2026-10-08: `VizBus` replay split — console and lifecycle events get separate backlogs (console bounded by `console_maxlen=500`; lifecycle retained under the existing `maxlen`; heartbeats live-only, never replayed), merged in publish order via an internal `_seq`. Prevents console volume from evicting `run_started`/`node_started`/`state` for tabs opened or refreshed mid-run — plain "most recent N of everything" replay is the pre-existing behaviour and is exactly the failure mode once console lines dominate. Live delivery and all event shapes unchanged.

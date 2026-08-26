# Live Graph Visualization — Implementation Plan

> **Status: PLANNED**

> **For agentic workers:** Use bite-sized task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `--viz` flag to the `agent-engine` CLI that spins up a localhost web page showing the pipeline graph (config-driven — e.g. the shipped self-loop example's `dev→checks→review→port_sweep→qa→commit`, plus the `bump`/`success` terminals) with **live** node highlighting — `pending / running / passed / failed` — plus subject, attempt n/max, one verdict badge per verdict step (any step declaring `artifact`+`verdicts`), and an event log. Zero new dependencies, zero behavior change when the flag is absent.

**Architecture:** New module `src/agent_engine/viz.py` (stream-part translation, event bus, stdlib SSE/HTTP server, embedded HTML page using Mermaid.js from CDN) wired into `graph.run_pipeline` (invoke→stream when a bus is present; server/browser/keep-alive lifecycle when `args.viz` is set) and `cli._core_parser` (`--viz`/`--viz-port` flags). Tests in new `tests/test_viz.py` plus wiring tests in `tests/test_graph.py` and `tests/test_cli.py`. Stage nodes untouched — all live data comes from LangGraph's `tasks`/`updates` stream modes.

**Tech Stack:** Python ≥3.12, pytest, LangGraph 1.2.9 + langgraph-checkpoint-sqlite 3.1.0 (repo venv, unchanged), stdlib `http.server` only, Mermaid.js v11 via CDN.

## Global Constraints

- TDD red→green→refactor for every task
- Mock policy (repo rule): `stages.run_agent` is the only stubbed code path (`FakeAgents`); `translate`/`VizBus` are tested against a real tiny `StateGraph` + `MemorySaver`; HTTP is tested over a real socket on port 0. The three thin CLI-lifecycle seams (`viz.serve_viz`, `viz.wait_for_interrupt`, `webbrowser.open`) are the viz equivalent of the `run_agent` boundary — monkeypatched only in `main()` lifecycle tests.
- Fail fast, never silently degrade: port-bind failure is a loud error naming `--viz-port`, not a fallback port
- `viz_bus=None` default everywhere → byte-identical behavior without `--viz`; the existing suites (`tests/test_graph.py`, `tests/test_cli.py` — which pin `graph.invoke` semantics, including the resume/crash regression tests) must keep passing untouched
- Full suite green at the end of every task: `.venv/bin/python -m pytest tests/ -q`

## Locked decisions (from user)

| Decision | Choice |
|---|---|
| Route | Custom local service (rejected: LangGraph Studio — needs LangSmith account + hosted UI + changed run model; `langgraph-viz` PyPI pkg — 0-star 3-commit weekend project, unmaintained, pre-1.0 API, heavy deps; static-only — no live updates) |
| Activation | Opt-in `--viz` flag, default off |
| Scope | MVP: node status + attempt + verdict badges + event log. NO state-diff inspector, timeline scrubbing, or LLM token streaming |
| Browser | Auto-open via `webbrowser.open()` + print URL |

## Verified LangGraph facts (spiked 2026-07-22 against langgraph 1.2.9; repo venv has 1.2.9)

- `graph.stream(state, config, stream_mode=["tasks", "updates"], version="v2")` yields `StreamPart` dicts `{"type", "ns", "data"}`.
- **`tasks` part semantics (verified):** a part whose data has a `triggers` key = task **start** (`{id, name, triggers}`); a part whose data has an `error` key = task **finish** (same `id`; `error=None` success, string = failure). Start/finish pairs arrive in node-execution order.
- `tasks` mode **requires a checkpointer** — `run_pipeline` already compiles with `SqliteSaver`, so this is free.
- `updates` parts carry `LoopState` deltas per node — `attempt`, `step_verdicts`, `outcome`, `failed` ride the stream with **zero node instrumentation**. (`docs`/`context`/`notes` ride too — they are huge and must be dropped; see whitelist below.)
- Topology: `build_graph(runtime).get_graph().draw_mermaid()` produces the full graph incl. conditional edges as dotted lines (verified pattern; `tests/test_graph.py::TestTopology` already asserts on `.get_graph().nodes`). In `run_pipeline` the compiled graph is already in hand — no second compile needed.
- Final state after streaming: `graph.get_state(config).values`.
- Resume (`initial=None`) through `stream` is documented to behave like `invoke` — **verify with an explicit test in Task 4** (existing suite has resume regression tests at `tests/test_graph.py::TestResume`).
- `updates` mode is deprecated in 1.2.9 but verified working; tolerate/filter the deprecation warning in tests if pytest surfaces it.

## Event protocol (bus payloads)

```json
{"type": "run_started",  "subject": "plan plan.md", "max_attempts": 3, "thread_id": "abc123"}
{"type": "node_started", "node": "checks"}
{"type": "node_finished","node": "checks", "ok": true}
{"type": "state", "attempt": 2, "step_verdicts": {"checks": "fail"}, "outcome": null, "failed": false}
{"type": "run_finished","success": false, "attempts": 3}
```

Whitelist for `state` events: `attempt, step_verdicts, outcome, failed`. (`docs`/`context`/`notes`/`commit_allowed`/`retry_target` are huge or internal — never shipped to the browser; MVP scope. Verdict badges are generic: the page renders one badge per config step with `verdicts:` set, sourced from `step_verdicts`.)

`run_started.subject`/`max_attempts`: from the fresh-run `initial` state, or on `--resume` from `graph.get_state(config).values` (a read, not a mutation).

---

### Task 1: `translate()` — StreamPart → viz events

**Files:**
- Create: `src/agent_engine/viz.py` (`translate(part) -> list[dict]`)
- Test: `tests/test_viz.py`

**Interfaces:**
- Consumes: v2 StreamParts from `graph.stream(..., stream_mode=["tasks", "updates"], version="v2")`
- Produces: event dicts per the protocol above (no `run_*` events here — those come from `run_pipeline`)

- [ ]**Step 1: Failing unit tests** — start part (`triggers`) → `node_started`; finish part (`error` None) → `node_finished ok:true`; finish part (`error` str) → `ok:false`; updates part → single `state` event with ONLY whitelisted keys (feed it `{"docs": ..., "context": ..., "notes": ..., "commit_allowed": ...}` and assert they're dropped); unknown/other parts → `[]`.
- [ ]**Step 2: Implement `translate`** — minimal pure function.
- [ ]**Step 3: Failing e2e test** — real tiny `StateGraph` (2 nodes) + `MemorySaver`, stream `["tasks","updates"]` v2, assert translated sequence is `node_started a → state → node_finished a(ok) → node_started b → …` in order.
- [ ]**Step 4: Green + refactor.**

### Task 2: `VizBus` — thread-safe pub/sub with backlog

**Files:**
- Modify: `src/agent_engine/viz.py`
- Test: `tests/test_viz.py`

**Interfaces:**
- `VizBus(maxlen=500)`: `publish(event)`, `subscribe() -> queue.Queue` (replays bounded backlog into the new subscriber first — late-opening browser tabs catch up), `unsubscribe(q)`
- Thread-safe: nodes publish from the pipeline thread; SSE handler threads consume.

- [ ]**Step 1: Failing tests** — fan-out to 2 subscribers; late subscriber receives backlog in order; unsubscribe stops delivery; backlog evicts oldest beyond `maxlen`; concurrent publish from N threads loses no events.
- [ ]**Step 2: Implement + green + refactor.**

### Task 3: HTTP/SSE server + embedded HTML page

**Files:**
- Modify: `src/agent_engine/viz.py` (`serve_viz(bus, topology_mermaid, subject, port) -> (httpd, thread)`, `PAGE` HTML constant)
- Test: `tests/test_viz.py`

**Interfaces:**
- `GET /` → HTML page. `GET /topology` → `{"mermaid": "...", "subject": "..."}`. `GET /events` → SSE (`data: {json}\n\n`, replay backlog on connect, `:hb` comment every 15s).
- `127.0.0.1` only. `ThreadingHTTPServer` on a daemon thread (each SSE connection holds one thread — fine for a local dev tool).
- Bind failure → raise with message naming `--viz-port` (no silent port fallback).

**Page (MVP):** Mermaid.js v11 CDN; fetch `/topology`, `mermaid.render`; `new EventSource("/events")`; per event update a `node -> status` map and re-render with `classDef` (`running` amber pulse, `passed` green, `failed` red, default pending) + `class <node> <status>` lines; sidebar: subject (updated by `run_started`), `attempt n/max`, one verdict badge per config step with `verdicts:` set, scrolling event log. `run_finished` banners success/failure. CDN unreachable → page still shows the event log as text (script `onerror` fallback), not a blank page.

- [ ]**Step 1: Failing tests** (real server on port 0): `/` 200 + contains mermaid container + topic placeholder; `/topology` JSON round-trip; SSE: connect, `bus.publish`, assert a `data:` frame with the event arrives over the real socket; backlog: publish before connecting, assert replay.
- [ ]**Step 2: Implement server + page; green.**
- [ ]**Step 3: Failing test** — binding a second server to the same port raises the loud `--viz-port` error.
- [ ]**Step 4: Implement + green + refactor.**

### Task 4: Wire into `run_pipeline` + CLI

**Files:**
- Modify: `src/agent_engine/graph.py` (`run_pipeline`), `src/agent_engine/cli.py` (`_core_parser`)
- Test: `tests/test_graph.py` (stream-path tests), `tests/test_cli.py` (flag + lifecycle tests), `tests/test_viz.py` if needed

**Interfaces:**
- `run_pipeline(cfg_path, args, *, viz_bus=None) -> tuple[bool, int]`
  - `viz_bus is None` and no `args.viz` → today's `graph.invoke(initial, config)` path, untouched.
  - bus present (passed in or created because `args.viz`) → publish `run_started` (subject/max_attempts from `initial`, or `graph.get_state(config).values` on resume; plus `thread_id`); `graph.stream(initial, config, stream_mode=["tasks","updates"], version="v2")`; `bus.publish` each `translate(part)` event; drain fully; `final = graph.get_state(config).values`; publish `run_finished` in a `finally` (success read from `final["outcome"]`, attempts from `final["attempt"]`; on exception → `success: false`). Returns `(success, attempts)` exactly as the invoke path does.
  - `args.viz` only (CLI path, bus created inside): additionally `topology = graph.get_graph().draw_mermaid()`; `serve_viz(bus, topology, subject, args.viz_port)`; `webbrowser.open(f"http://127.0.0.1:{port}")` + print URL. After the run returns, keep the process alive via `viz.wait_for_interrupt()` (thin `threading.Event().wait()` wrapper catching `KeyboardInterrupt`) so the final graph stays inspectable; without `--viz`, exit exactly as today. Programmatic callers passing `viz_bus=` get no server and no keep-alive — bus-only.
- `_core_parser()`: `--viz` (store_true), `--viz-port` (int, default 8321) — core flags, so they exist for every pipeline (they're loader-independent).

- [ ]**Step 1: Failing tests** — `run_pipeline` with a real bus + `fake_agents` publishes the translated sequence and returns the same `(success, attempts)` as the invoke path's; `viz_bus=None` path still invokes (existing suite is the pin); **resume via `stream(None, config)`** continues from the checkpoint (mirrors `TestResume::test_resume_from_crash` through the stream path — guards the documented-but-unverified assumption).
- [ ]**Step 2: Implement the stream path in `run_pipeline`; green.**
- [ ]**Step 3: Failing tests** — `build_parser(...).parse_args(["--viz", "--viz-port", "9"])`; `--viz` appears in `--help` output (extend the existing `TestHelp` assertions); full `main(["pipeline.yaml", "--plan", "plan.md", "--viz"])` with `fake_agents`: monkeypatch `viz.serve_viz` (capture the topology arg), `webbrowser.open`, and `viz.wait_for_interrupt` (→ raise `KeyboardInterrupt`); assert `main` returns the pipeline's exit code, topology mermaid contains the pipeline's step names, and the bus saw `run_started`/`run_finished`.
- [ ]**Step 4: Implement `_core_parser` flags + lifecycle wiring; green + refactor.**

### Task 5: Docs

- [ ] `README.md`: one line in the Quick start / CLI section (`--viz` serves a live graph view on localhost, auto-opens the browser).
- [ ] CLI `--help` text for the two flags (part of `_core_parser`).

## Verification

1. `.venv/bin/python -m pytest tests/ -q` green.
2. Manual smoke: tiny-graph script with `--viz` — page renders, nodes light up in order, verdict badges populate.
3. Real `agent-engine examples/self/pipeline.yaml --plan <doc> --viz` run — **user triggers** (makes LLM calls).

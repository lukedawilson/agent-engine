# Viz Vertical Flowchart — Implementation Plan

> **Status: COMPLETED**

> **For agentic workers:** Use bite-sized task execution to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the topology the viz page renders — today `compiled.get_graph().draw_mermaid()`, which yields stadium "pill" nodes, `__start__`/`__end__` terminals, and a horizontal fan of dotted conditional edges — with a config-driven **single vertical flowchart**: every configured step in one top-to-bottom chain (solid `-->` happy path), dotted labeled **loop-back arrows** for retries, plain rectangle nodes. The right-hand sidebar (subject / attempt / verdict badges / event log) is unchanged.

Target rendering for the shipped self-loop example:

```
graph TD;
	dev --> checks;
	checks --> review;
	review --> port_sweep;
	port_sweep --> qa;
	qa --> commit;
	commit --> success;
	checks -. FAIL .-> dev;
	review -. NEEDS CHANGES .-> dev;
	qa -. FAIL .-> dev;
```

(`FAIL` / `NEEDS CHANGES` are **edge labels**, not nodes — mermaid's `A -. label .-> B` dotted-edge syntax; the arrowhead points at `dev`. A fail verdict loops back to dev via the `bump` node — which increments the attempt and resets verdicts and is deliberately not drawn — until attempts are exhausted, at which point bump routes to the `failure` terminal and the run ends.)

**Architecture:** New pure function `viz.topology_mermaid(cfg) -> (mermaid_source, node_ids)` builds a LangChain `Edge` list from `cfg.steps` and renders it through LangChain's own mermaid renderer (`langchain_core.runnables.graph_mermaid.draw_mermaid`, invoked one level below the `Graph.draw_mermaid()` adapter we use today). `/topology` gains a `nodes` field so the page can filter its `class` lines to nodes that actually exist in the diagram (`bump` runs but is deliberately not drawn). `graph.py`'s `--viz` path and `viz_demo.py` swap over; the programmatic `viz_bus=` path and the invoke path are untouched.

**Tech Stack:** unchanged from plan 001 — Python ≥3.12, pytest, LangGraph 1.2.9 (repo venv), stdlib-only server, Mermaid.js v11 via CDN. No new dependencies (langchain_core is already LangGraph's own dependency).

## Global Constraints

- TDD red→green→refactor for every task
- Mock policy unchanged (repo rule): `topology_mermaid` is a pure function — no new seams; only the three existing CLI-lifecycle seams stay monkeypatched in `main()` lifecycle tests
- `viz_bus=None` default → byte-identical behavior without `--viz`; existing suites keep passing
- Full suite green at the end of every task: `.venv/bin/python -m pytest tests/ -q`

## Locked decisions (from user)

| Decision | Choice |
|---|---|
| Layout | Single vertical flowchart; all configured steps; loop-back arrows visible; no pills, no terminal stadiums, no conditional-edge fan |
| Renderer | **Reuse LangChain's renderer** with our own `Edge` list (rejected: parameterising `Graph.draw_mermaid()` — its five kwargs are all cosmetic; rejected: hand-rolled mermaid strings — user chose reuse) |
| Sidebar | Right column stays exactly as-is |
| Loop-back labels | The step's `verdicts.fail` text (`FAIL`, `NEEDS CHANGES`); fall back to `"retry"` for a retrying step without verdicts |
| `bump` node | Omitted from the diagram (engine machinery, not a configured step); its events still stream and appear in the event log |

## Verified LangChain facts (spiked 2026-08-27 against the repo venv's langchain_core, langgraph 1.2.9)

- `Graph.draw_mermaid(*, with_styles, curve_style, node_colors, wrap_label_n_words, frontmatter_config)` is a thin adapter; it hardcodes `graph TD;`, node shape `"{0}({1})"` (stadium) and `([...]):::first/last` terminals. Nothing structural is parameterisable.
- The inner `langchain_core.runnables.graph_mermaid.draw_mermaid(nodes, edges, *, first_node, last_node, with_styles, ...)` takes the topology **as data**:
  - `Edge(source: str, target: str, data: Stringifiable | None = None, conditional: bool = False)`; `conditional=True` renders ` -.-> ` (dotted), `False` renders ` --> `; `data` becomes the edge label (`&nbsp;`-padded, wrapped only above 9 words — our verdict labels are short).
  - `with_styles=False` → no frontmatter block, **no node declarations** (nodes referenced by edges auto-render as plain rectangles), and no default classDefs — the page supplies its own.
  - `first_node=None, last_node=None` → no terminal treatment.
  - Node ids pass through `_to_safe_id`; harmless for our config-validated slug step names (they must match event `node` names for highlighting regardless).
  - Import paths: `from langchain_core.runnables.graph import Edge`, `from langchain_core.runnables.graph_mermaid import draw_mermaid`. **Semi-private API** — not in langgraph's public surface; pinned by tests (same coupling class as the StreamPart facts in plan 001).

---

### Task 1: `topology_mermaid()` — cfg → (mermaid, node ids)

**Files:**
- Modify: `src/agent_engine/viz.py`
- Test: `tests/test_viz.py`

**Interface:**
- `topology_mermaid(cfg: PipelineConfig) -> tuple[str, list[str]]`
- Main chain: for each step with a non-None `route_target(step.on_pass)`: `Edge(step.name, target, conditional=False)`.
- Retry loop-back: `step.on_fail` a `Route` with `retry=True` → `Edge(step.name, step.on_fail.goto, data=label, conditional=True)`, label = `step.verdicts.fail` when the step declares verdicts else `"retry"`.
- Non-retry `on_fail`: `Edge(step.name, route_target(step.on_fail), conditional=True)` (dotted, unlabeled).
- Node id list: step names in config order, plus any referenced terminals (`success`/`failure`), de-duplicated.
- Render: `draw_mermaid(nodes={}, edges=edges, first_node=None, last_node=None, with_styles=False)`.

- [x]**Step 1: Failing tests** — shipped `examples/self/pipeline.yaml`: chain edges in step order ending at `success`; exactly three labeled loop-backs (`FAIL`, `NEEDS CHANGES`, `FAIL`) to `dev`; no `__start__`/`__end__`, no `bump`, no `(`-stadium declarations; node list matches. Synthetic cfg: `Route`-shaped `on_pass`; non-retry `on_fail: failure` → unlabeled dotted edge + `failure` terminal in the node list.
- [x]**Step 2: Implement; green + refactor.**

### Task 2: `/topology` gains `nodes`; page filters class lines

**Files:**
- Modify: `src/agent_engine/viz.py` (`serve_viz(..., nodes=())`, handler, `PAGE`)
- Test: `tests/test_viz.py`

**Interface:**
- `serve_viz(bus, topology_mermaid, subject, port, nodes: Iterable[str] = ())` — `/topology` returns `{"mermaid", "subject", "nodes"}`.
- `PAGE`: keep the `/topology` response's `nodes` in a `Set`; `renderGraph()` emits `class` lines only for ids in that set (drops `bump`; guards against mermaid rejecting class statements for non-existent nodes).

- [x]**Step 1: Failing tests** — `/topology` round-trip includes `nodes`; `PAGE` contains the filter hook (string assertion, matching `test_page_constant_has_fallback_hook`'s pattern).
- [x]**Step 2: Implement; green + refactor.**

### Task 3: Wire `graph.py` + simplify `viz_demo.py`

**Files:**
- Modify: `src/agent_engine/graph.py` (`run_pipeline` `--viz` branch), `viz_demo.py`
- Test: `tests/test_cli.py`

**Interface:**
- `run_pipeline`: replace `graph.get_graph().draw_mermaid()` with `topology, nodes = viz.topology_mermaid(cfg)`; pass `nodes` to `serve_viz`. Subject/resume logic, bus creation, keep-alive: untouched. Programmatic `viz_bus=` path: untouched.
- `viz_demo.py`: `real_topology()` collapses to `viz.topology_mermaid(load_config(EXAMPLE))` — delete the `Runtime`/`build_llm`/dummy-`OPENAI_API_KEY` scaffolding; pass `nodes` through.
- `test_cli.py`: `fake_serve_viz` gains the `nodes` param; existing assertions (`"dev"`/`"success"` in topology) keep passing.

- [x]**Step 1: Failing tests** — update `fake_serve_viz` signature (captures `nodes`); assert captured `nodes` covers the pipeline's steps and excludes `bump`.
- [x]**Step 2: Implement; green + refactor.**
- [x]**Step 3: Demo smoke** — `./run-demo.sh --no-browser`: `/topology` serves the vertical-chain source; SSE sequence unchanged.

## Verification

1. `.venv/bin/python -m pytest tests/ -q` green.
2. Manual smoke: `./run-demo.sh` — single vertical chain of rectangles; `checks -.FAIL.-> dev` arc on attempt 1; badges reset on bump (log only); attempt 2 lights the chain to `success`; banner. **User eyeballs.**
3. Real `agent-engine examples/self/pipeline.yaml --plan <doc> --viz` run — **user triggers** (makes LLM calls).

## Amendments

- 2026-08-27: CLI activation is now default-on (`--no-viz` suppresses) — see plan 001's amendment. The `viz_bus=None` byte-identity constraint still holds for programmatic callers.

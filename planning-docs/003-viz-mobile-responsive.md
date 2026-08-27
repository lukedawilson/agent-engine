# Viz Mobile Responsiveness — Implementation Plan

> **Status: PLANNED**

> **For agentic workers:** Use bite-sized task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the viz page **mobile-friendly (not mobile-first)**. Desktop keeps its current side-by-side layout — flowchart left, step list (subject / attempt / verdict badges / event log) right. On small and extra-small viewports (≤ 768px) the two stack vertically: flowchart on top, step list below, with natural page scrolling. No other visual or behavioral changes.

Current state of the frontend (single embedded `PAGE` constant, `src/agent_engine/viz.py`): `body { display: flex; height: 100vh; }` (row, full-height app shell), `#graph-panel { flex: 1 1 auto; overflow: auto; }`, `#sidebar { flex: 0 0 320px; border-left: 1px solid #e0e0e0; }` with an internally scrolling `#log`; **zero media queries**. Already mobile-safe: `<meta name="viewport">` is present and `#mermaid-container svg { max-width: 100%; height: auto; }` scales the diagram down.

**Architecture:** Desktop-first CSS is untouched. One `@media (max-width: 768px)` block appended to the `<style>` section of `PAGE` flips `body` to a column and adjusts the sidebar. **Zero HTML changes** (DOM order `#graph-panel` → `#sidebar` already yields the right stack order), **zero JS changes**, zero new dependencies.

The breakpoint of 768px stacks on both Bootstrap's `xs` (< 576px) and `sm` (576–767px) ranges — the user's "s/xs viewports" requirement.

**Tech Stack:** unchanged from plan 001 — Python ≥3.12, pytest, LangGraph 1.2.9 (repo venv), stdlib-only server, Mermaid.js v11 via CDN. No new dependencies.

## Global Constraints

- TDD red→green→refactor for every task
- Mock policy unchanged (repo rule): this is a frontend-only change — new coverage is plain string assertions on `PAGE`, matching the existing `test_page_constant_*` pattern; no new seams
- `viz_bus=` semantics, event protocol, `/topology` payload, and server behavior are untouched (nothing outside the `PAGE` string changes)
- Full suite green at the end of every task: `.venv/bin/python -m pytest tests/ -q`

## Locked decisions (from user)

| Decision | Choice |
|---|---|
| Posture | Mobile-friendly, **not** mobile-first — desktop layout is the base, a media query overrides it below the breakpoint |
| Breakpoint | `max-width: 768px` (covers xs + sm ranges) |
| Stack order | Flowchart on top, step list below (DOM order already provides it; no HTML changes) |
| Mobile scroll model | Natural page scroll — `body { height: auto }` below the breakpoint (rejects: fixed-height app shell with two internal scrollers, which is fiddly on mobile chrome) |
| Sidebar border | Moves from the left edge to the top edge when stacked |
| Scope | Right-column content (subject / attempt / badges / log) stays exactly as-is at every size |

---

### Task 1: Failing tests — media query present in `PAGE`

**Files:**
- Test: `tests/test_viz.py`

**Interface:**
- New test(s) alongside the existing `PAGE` string assertions (`test_page_constant_has_fallback_hook`'s pattern), asserting:
  - `"@media" in PAGE`
  - `"max-width: 768px" in PAGE`
  - `"flex-direction: column" in PAGE`

- [ ]**Step 1: Write the failing tests; watch them fail.**
- [ ]**Step 2: No production changes yet — red state confirmed.**

### Task 2: Implement the media query in `PAGE`

**Files:**
- Modify: `src/agent_engine/viz.py` (`PAGE` only)

**Interface:**
- Append before `</style>`:

```css
@media (max-width: 768px) {
  body { flex-direction: column; height: auto; }
  #sidebar { flex: 0 0 auto; border-left: 0; border-top: 1px solid #e0e0e0; }
}
```

- Desktop styles above the media query remain byte-identical.

- [ ]**Step 1: Apply the CSS block; suite green.**
- [ ]**Step 2: Refactor if needed (expected: none).**

### Task 3: Manual smoke

**Files:** none

- [ ]**Step 1:** `./run-demo.sh --no-browser` — open the page at ≤ 768px viewport width (browser device emulation or a narrow window): flowchart on top, step list below, page scrolls naturally, sidebar shows a top border instead of a left border; at > 768px the layout is the unchanged side-by-side shell.

## Verification

1. `.venv/bin/python -m pytest tests/ -q` green.
2. Manual smoke (Task 3) — **user eyeballs** at a phone width and at desktop width.
3. Real `agent-engine examples/self/pipeline.yaml --plan <doc> --viz` run — **user triggers** (makes LLM calls).

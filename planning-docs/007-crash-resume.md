# Crash-resumable runs: stage exceptions park the run for `--resume` — Implementation Plan

> **Status: PLANNED** — written on user instruction: plan and stop. Implementation starts on an explicit go.

> **For agentic workers:** Use bite-sized task execution to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `--resume` work for *all* stage crashes, not just process deaths. Today an ordinary exception inside a stage (LLM provider error, network blip, action bug) is converted to a terminal `failed: True` state and the graph runs to END — so a later `--resume` finds a finished graph and instantly replays "run finished: failure". After this plan, a stage exception **parks** the run: the error is reported exactly as today, the graph never reaches a terminal state, and `--resume <thread-id>` re-enters at the crashed stage with the attempt count intact.

**Root cause (verified), two layers:**

1. `run_agent` (`src/agent_engine/stages.py:91-98`) catches **all** `Exception`s — writes `last-error.md`, prints the traceback — then returns `AgentResult(ok=False)`; the agent node turns that into `{"failed": True}` (`stages.py:199-201`). Action nodes do the same (`stages.py:236-238`). The router's first branch sends `failed=True` straight to END (`stages.py:259-260`).
2. END writes a final checkpoint; the run is *complete* (failure terminal). `graph.stream(None, config)` on a resumed thread has no pending work, so the `finally` in `run_pipeline` (`graph.py:202-217`) publishes `run_finished: failure` from the checkpointed state and the process exits — no stage re-executes, no new checkpoints are written.

Only `BaseException`s (KeyboardInterrupt, SIGKILL) escape the `except Exception` net and leave the graph mid-superstep — the one crash mode `--resume` actually recovers from, and the only one tested (`("crash",)` → `KeyboardInterrupt`, `tests/conftest.py:48-49`; `TestResume.test_resume_from_crash`). The graph.py docstring already advertises "crash-resumable … re-enters at the first stage that didn't complete" — today that's true only for `BaseException` deaths.

Real incident (the motivation): audio-transcriber AI-DLC unit U005, 2026-09-14. DeepSeek returned a transient 400 (`reasoning_content … must be passed back`) inside the `checks` agent — minutes after the identical config had run `dev` successfully, and after a full day of successful runs. `dev`'s output was complete in the working tree, yet the run burned to terminal failure on attempt 1/10; `--resume 5e185759…` replayed the failure instantly (no new checkpoints; `last-error.md` mtime unchanged). The retry budget never applied — it covers verdict FAILs, not crashes.

**Architecture:**

- **Stages propagate; the graph stays non-terminal.** `run_agent` keeps its observability contract (stderr traceback + `last-error.md` + `conv.close()` in `finally`) but **re-raises** from the `except Exception` block instead of returning `ok=False`. `AgentResult` loses the now-vestigial `ok` field (returns `truncated: bool` semantics only). The agent node's `if not result.ok → {"failed": True}` branch is deleted. `make_action_node`'s try/except is deleted — action exceptions propagate the same way.
- **`failed` state key removed.** Nothing sets it anymore: drop from `LoopState` (`graph.py:41`), the initial state dict (`graph.py:145`), the router branch (`stages.py:259-260`), the bump node (`stages.py:290`), the agent/action node returns, and the `final["failed"]` guard in `run_pipeline` (`graph.py:223`). Verdict-FAIL → END routing (attempts exhausted, `on_fail` without retry) is untouched.
- **Crash reporting lives in `run_pipeline`.** Both execution paths (`graph.stream` loop and `graph.invoke`) get a `try/except Exception` around the graph execution. On catch: read `graph.get_state(config)` — `.next[0]` names the crashed stage, `.values["attempt"]` the attempt — print the parked-run message (below), and return `(False, attempt)`. `BaseException` still propagates (Ctrl-C behavior unchanged; existing `("crash",)` tests keep passing). The viz `finally` already publishes `run_finished: failure` from the checkpointed state — honest and unchanged.
- **Resume needs no changes.** With no terminal checkpoint written, the existing `--resume` path (last checkpoint's `next` = crashed stage) re-executes the crashed stage and continues. Attempt count is *not* consumed by a crash (attempts bump only in the `bump` node, on verdict/unclear retries).

Crash message (stderr, after the existing traceback/`last-error.md` prints):

```
[<subject>] CRASHED at stage '<step>' on attempt <N> — run parked (see <state_dir>/last-error.md).
Resume with: agent-engine <pipeline> --resume <thread_id>
```

**Tech Stack:** unchanged — Python ≥3.12, pytest, LangGraph 1.2.9, OpenHands SDK, stdlib viz. No new dependencies. No pipeline-YAML surface changes. No viz protocol changes (no new event types).

## Global Constraints

- TDD red→green→refactor for every task
- Mock policy unchanged (repo rule): LLM stays behind the `fake_agents` seam; no new seams
- Full suite green at the end of every task: `.venv/bin/python -m pytest tests/ -q`
- `BaseException` semantics unchanged — KeyboardInterrupt/SIGKILL still propagate out of `run_pipeline`

## Locked decisions (from investigation)

| Decision | Choice |
|---|---|
| Crash model | Stage exceptions propagate out of the node; `run_pipeline` catches `Exception`, reports, returns `(False, attempt)`. Run is parked, never terminal. |
| `BaseException` | Still propagates (existing Ctrl-C/SIGKILL resume story unchanged). |
| `failed` state key | Removed entirely (nothing sets it once stages propagate). |
| Attempt accounting | A crash consumes **no** attempt (bump node is the only attempt incrementer). |
| Automatic crash retry | **Not in this plan.** Resume is manual and explicit. Follow-up candidate below. |
| Viz | No protocol change; page shows `run_finished: failure` as today. The terminal carries the resume instructions (same channel as the `last-error.md` announcement). |
| Docstring drift | Update `graph.py` module docstring (becomes true for all crash modes) and `make_action_node` docstring ("fails the run" → "propagates; run is resumable"). |

---

### Task 1: Failing tests — Exception crash parks the run; resume re-enters at the crashed stage

**Files:**
- Test: `tests/conftest.py`, `tests/test_graph.py`, `tests/test_stages.py`

**Interface:**
- New `fake_agents` script op `("boom",)` → `raise RuntimeError("boom")` alongside `("crash",)` (conftest.py:48). `("crash",)` → KeyboardInterrupt stays as-is.
- `tests/test_graph.py::TestResume::test_resume_from_stage_exception` — mirror of `test_resume_from_crash` with `("boom",)` on `review`: first `run_pipeline` **returns `(False, 1)`** (does not raise); `capsys` shows the parked-run message containing `CRASHED at stage 'review'`, `attempt 1`, and `Resume with:` + the thread id; then `run_pipeline(..., resume=<tid>)` returns `(True, 1)` and `agents_called()` shows only `review` onward re-ran (dev/test not repeated — checkpoints preserved).
- `tests/test_graph.py::TestResume::test_resume_from_stage_exception_via_stream` — same shape through the `viz_bus=` stream path; `run_finished` from the crashed run carries `success is False`, `attempts == 1`.
- `tests/test_stages.py` — `run_agent` on exception: **raises** and still writes `last-error.md` (update existing tests asserting `ok=False`); action node exceptions propagate (update tests asserting `{"failed": True}`).
- Update/remove tests asserting the old semantics: router's `failed → END` branch, `failed` in state, `graph.py:223`'s `final["failed"]` guard.

- [ ]**Step 1: `("boom",)` op + the failing tests; watch them fail** (today: `run_pipeline` returns `(False, …)` without raising but the run is terminal — resume instantly fails; `run_agent` swallows).
- [ ]**Step 2: No production changes yet — red state confirmed.**

### Task 2: Implement — propagate in stages, catch-and-report in `run_pipeline`, delete `failed`

**Files:**
- Modify: `src/agent_engine/stages.py`, `src/agent_engine/graph.py`

**Interface:**
- `run_agent`: `except Exception` block ends with `raise` after the existing prints/`last-error.md` write. `AgentResult` drops `ok` (keep `truncated`); agent node's `ok` branch deleted.
- `make_action_node`: try/except deleted.
- `make_router`/`make_bump_node`/agent node: all `failed` reads/writes deleted; `LoopState.failed` and the initial-state entry deleted.
- `run_pipeline`: `try/except Exception` around the stream loop and around `graph.invoke`; handler reads `graph.get_state(config)` (`.next[0]` → step name, `.values["attempt"]` → N), prints the crash message, returns `(False, N)`. The `graph.py:223` "FAILED after N attempt(s)" print now applies to verdict-exhaustion only (`if not success:` with the crash path already returned).
- Docstring updates per Locked decisions.

- [ ]**Step 1: Apply; suite green.**
- [ ]**Step 2: Refactor — confirm no dangling `failed`/`ok` references (`rg` sweep), simplify returns.**

### Task 3: Regression — BaseException resume story unchanged

**Files:** none

- [ ]**Step 1:** Full suite green — in particular `test_resume_from_crash`, `test_resume_via_stream_continues`, `test_resume_unknown_thread_fails` (KeyboardInterrupt path untouched), and the verdict-FAIL/exhaustion tests (`test_stream_path_failure_returns_same` still `(False, 3)` with the "FAILED after 3 attempt(s)" print).
- [ ]**Step 2:** Double-crash scenario sanity (covered by unit tests or a scripted run): crash → resume → crash again at the same stage → second resume works; attempt never advances across crashes.

## Verification

1. `.venv/bin/python -m pytest tests/ -q` green.
2. New tests prove: Exception crash → `(False, 1)` + resume hint → `--resume` completes `(True, 1)` with only the crashed stage re-run.
3. Real pipeline smoke — **user triggers** (makes LLM calls): re-run a pipeline against a previously-crashed thread; confirm re-entry at the crashed stage.

## Amendments

- (none yet)

## Follow-up candidates (not in scope)

- **Automatic transient-error retry** — classify LLM API errors (5xx, rate-limit, provider 400s like the DeepSeek `reasoning_content` flake) and retry in-run with backoff before parking (e.g. `crash_retries: N` in pipeline YAML). Deliberately deferred: parking + manual resume is the correct minimal fix; auto-retry policy deserves its own design.
- **Viz crash surfacing** — a `run_crashed` event type carrying step/attempt/thread-id so browser users see the resume command without checking the terminal.

"""Config-driven LangGraph builder + the run_pipeline public API.

The pipeline is a cyclic state graph: one node per configured step, routers
steer the retry cycle, and a SQLite checkpointer makes runs crash-resumable
(--resume <thread-id> re-enters at the first stage that didn't complete).
"""

from __future__ import annotations

import operator
import uuid
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .actions import git_worktree_clean
from .config import load_config
from .llm import build_llm
from .loaders import select_loader
from .registry import Registry, default_registry, load_extensions
from .stages import (Runtime, build_context, clear_attempt_artifacts,
                     make_action_node, make_agent_node, make_bump_node,
                     make_router, success_node)

CHECKPOINT_DB = "loop-checkpoints.sqlite"  # under state_dir, one DB per workspace


class LoopState(TypedDict):
    """State threaded through the graph. `notes` accumulates across attempts
    (append reducer); every other key is last-write-wins."""
    subject: str
    docs: dict[str, str]
    context: str                       # built at attempt start, shared by all stages
    attempt: int
    max_attempts: int
    notes: Annotated[list[str], operator.add]
    failed: bool                       # hard stage failure — ends the run
    outcome: str | None                # "success" once routed to the success terminal
    commit_allowed: bool               # worktree was clean at run start
    step_verdicts: dict[str, str | None]  # per-step pass/fail/None(unclear)
    retry_target: str | None           # where the bump node loops back to
    thread_id: str


def build_graph(runtime: Runtime, checkpointer=None):
    """Compile the pipeline's state graph: one node per step (agent or
    action), plus the bump retry node and the success terminal. Unknown
    action names fail here, at build time, not mid-run."""
    for step in runtime.cfg.steps:
        if step.action is not None and step.action not in runtime.registry.actions:
            raise ValueError(
                f"step {step.name!r}: unknown action {step.action!r} "
                f"(registered: {sorted(runtime.registry.actions)})")
    graph = StateGraph(LoopState)
    for step in runtime.cfg.steps:
        node = (make_agent_node(runtime, step) if step.agent
                else make_action_node(runtime, step))
        graph.add_node(step.name, node)
        graph.add_conditional_edges(step.name, make_router(runtime, step))
    graph.add_node("bump", make_bump_node(runtime))
    graph.add_conditional_edges("bump", lambda state: state["retry_target"])
    graph.add_node("success", success_node)
    graph.add_edge(START, runtime.cfg.steps[0].name)
    graph.add_edge("success", END)
    return graph.compile(checkpointer=checkpointer)


def _resolve_docs(cfg, base: Path, registry: Registry,
                  args) -> tuple[dict[str, str], str]:
    """Select and invoke the document loader, then append the pipeline's
    additional_files (resolved relative to the pipeline file's dir;
    listed-but-missing fails fast)."""
    loader = select_loader(registry, args)
    if loader is not None:
        docs, subject = loader.resolve(args)
        if not docs:
            # U3 policy: an empty load silently degraded to a context the
            # agents couldn't act on. Fail fast at the call site instead.
            raise RuntimeError(
                f"Document loader {loader.name!r} returned no docs — "
                "refusing to build context from nothing")
    else:
        docs, subject = {}, cfg.name
    for rel in cfg.additional_files:
        path = base / rel
        if not path.is_file():
            raise FileNotFoundError(f"additional_files entry not found: {path}")
        docs[path.name] = path.read_text()
    return docs, subject


def run_pipeline(cfg_path, args) -> tuple[bool, int]:
    """Load a pipeline YAML, resolve docs via the selected document loader,
    and run the graph to completion. Returns (success, attempts) — the
    public API, yosk's `construct`/`resume_loop` equivalent.

    `args` carries the parsed CLI namespace: loader flags, --resume, and
    --max-attempts (which overrides the YAML value when set)."""
    cfg_path = Path(cfg_path)
    cfg = load_config(cfg_path)
    base = cfg_path.resolve().parent
    max_attempts = getattr(args, "max_attempts", None) or cfg.max_attempts

    registry = default_registry()
    load_extensions(cfg.extensions, registry)

    state_dir = base / cfg.state_dir
    runtime = Runtime(cfg=cfg, registry=registry, llm=build_llm(cfg.llm),
                      agents_dir=base / cfg.agents_dir, state_dir=state_dir,
                      workspace=Path.cwd())
    state_dir.mkdir(parents=True, exist_ok=True)

    resume = getattr(args, "resume", None)
    thread_id = resume or uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    db = str(state_dir / CHECKPOINT_DB)
    if resume:
        initial = None  # state (docs/subject/context) comes from the checkpoint
    else:
        docs, subject = _resolve_docs(cfg, base, registry, args)
        # A fresh run owns state_dir: drop cross-run leftovers (a previous
        # failure's last-error.md, stale artifacts) so nothing mistakes
        # them for this run's output. --resume keeps them.
        clear_attempt_artifacts(runtime)
        initial: LoopState = {
            "subject": subject,
            "docs": docs,
            "context": build_context(runtime, docs, subject, []),
            "attempt": 1,
            "max_attempts": max_attempts,
            "notes": [],
            "failed": False,
            "outcome": None,
            # Only a clean-at-start worktree gets an auto-commit — otherwise
            # the commit could swallow pre-existing changes. Computed BEFORE
            # the checkpointer creates its db under state_dir, which would
            # itself dirty the worktree.
            "commit_allowed": git_worktree_clean(Path.cwd()),
            "step_verdicts": {},
            "retry_target": None,
            "thread_id": thread_id,
        }
    with SqliteSaver.from_conn_string(db) as saver:
        if resume and saver.get_tuple(config) is None:
            raise ValueError(
                f"No checkpoint found for thread {thread_id!r} in {db} — "
                f"nothing to resume.")
        graph = build_graph(runtime, saver)
        final = graph.invoke(initial, config)
    success = final["outcome"] == "success"
    if not success and not final["failed"]:
        print(f"[{final['subject']}] FAILED after {final['attempt']} attempt(s).",
              flush=True)
    return success, final["attempt"]

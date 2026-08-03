"""Stage nodes, routers, and the run_agent port.

The yosk loop's hardcoded stages become per-step closures built from the
pipeline config; the fixed policies stay here, not in config:

- per-attempt hygiene: every declared artifact/produces file + last-error.md
  is deleted at attempt start, so stale files can't be misread
- verdict-first truncation: a clear verdict stands even if the run was cut
  short before the agent formally finished
- unclear verdict → implicit, attempt-bounded retry with the artifact's
  content surfaced into notes (never routable — policy, not config)
- notes accumulate across attempts into the next attempt's context
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langgraph.graph import END
from openhands.sdk import Conversation

from .agents import load_agent
from .config import TERMINALS, PipelineConfig, Route, StepConfig, route_target
from .registry import Registry
from .verdicts import parse_verdict

if TYPE_CHECKING:
    from openhands.sdk import LLM

DEFAULT_MAX_ITERATIONS = 500
LAST_ERROR = "last-error.md"


@dataclass
class Runtime:
    """Everything stage nodes need that isn't in LoopState: pipeline config,
    extension registry, the shared LLM, and resolved (absolute) paths."""
    cfg: PipelineConfig
    registry: Registry
    llm: "LLM"
    agents_dir: Path
    state_dir: Path
    workspace: Path


@dataclass
class AgentResult:
    """Outcome of a single agent stage run.

    ok=False only on unhandled exceptions. truncated=True when the run ended
    without the agent reaching FINISHED — the turn cap (ERROR) or the SDK's
    stuck detector (STUCK) both land here."""
    ok: bool = False
    truncated: bool = False


def run_agent(agent_name: str, message: str, runtime: Runtime,
              max_iterations: int = DEFAULT_MAX_ITERATIONS) -> AgentResult:
    """Run one agent stage. The agent file's body is delivered as a system
    message suffix (AgentContext); the user turn carries only the task.
    Any failure — setup or run — is reported to <state_dir>/last-error.md."""
    conv = None
    try:
        from openhands.sdk.conversation.state import ConversationExecutionStatus

        agent = load_agent(runtime.agents_dir, agent_name, runtime.llm)
        conv = Conversation(agent=agent, workspace=str(runtime.workspace),
                            max_iteration_per_run=max_iterations)
        conv.send_message(message)
        conv.run()

        truncated = conv.state.execution_status != ConversationExecutionStatus.FINISHED
        return AgentResult(ok=True, truncated=truncated)
    except Exception:
        err = traceback.format_exc()
        print(err[-4000:], file=sys.stderr, flush=True)
        runtime.state_dir.mkdir(parents=True, exist_ok=True)
        error_path = runtime.state_dir / LAST_ERROR
        error_path.write_text(f"# Agent run failed\n\n```\n{err[-4000:]}\n```")
        print(f"Agent run failed — error details written to {error_path}", flush=True)
        return AgentResult(ok=False, truncated=False)
    finally:
        if conv is not None:
            conv.close()


def build_context(runtime: Runtime, docs: dict[str, str], subject: str,
                  notes: list[str] | None = None) -> str:
    """Assemble the attempt's shared message: subject, doc bundle, the
    expected-output-paths section generated from step defs (a prompt merely
    naming files lets agents skip them), and previous-attempt notes."""
    parts = [f"You are working on {subject}.\n"]
    for name, content in docs.items():
        parts.append(f"## {name}\n\n{content}")
    lines = []
    for step in runtime.cfg.steps:
        if step.agent is None:
            continue
        for produced in step.produces:
            lines.append(f"{step.name} agent writes: `{runtime.state_dir.name}/{produced}`")
        if step.artifact is not None:
            lines.append(f"{step.name} agent writes: `{runtime.state_dir.name}/{step.artifact}`")
    if lines:
        parts.append("## Expected output paths\n\n" + "\n".join(lines))
    if notes:
        parts.append("## Previous attempt feedback\n\n" + "\n\n".join(notes))
    return "\n\n".join(parts)


def declared_artifacts(cfg: PipelineConfig) -> list[str]:
    files = []
    for step in cfg.steps:
        files.extend(step.produces)
        if step.artifact is not None:
            files.append(step.artifact)
    return files


def clear_attempt_artifacts(runtime: Runtime) -> None:
    """Per-attempt hygiene (fixed policy): delete every declared
    artifact/produces file + last-error.md so stale files from earlier
    attempts or runs can't be mistaken for this attempt's output."""
    for name in [*declared_artifacts(runtime.cfg), LAST_ERROR]:
        (runtime.state_dir / name).unlink(missing_ok=True)


def _read_stage_artifact(state_dir: Path, artifact: str,
                         verdicts: dict[str, str]) -> tuple[str | None, str | None]:
    """(verdict, text) for a stage artifact — both None when the file is missing."""
    path = state_dir / artifact
    if not path.exists():
        return None, None
    text = path.read_text()
    return parse_verdict(text, verdicts), text


def _unclear_target(runtime: Runtime, step: StepConfig) -> str:
    """Where the unclear-verdict retry loops to: on_fail's goto when that is
    a step, else the entry step (yosk always looped back to dev)."""
    target = route_target(step.on_fail)
    if target is not None and target not in TERMINALS:
        return target
    return runtime.cfg.steps[0].name


def _unclear_note(runtime: Runtime, step: StepConfig, attempt: int,
                  text: str | None, truncated: bool, max_iterations: int) -> str:
    """Explain an unclear verdict to the next attempt — and surface the
    artifact's content when it exists, so real findings are never swallowed."""
    rel = f"{runtime.state_dir.name}/{step.artifact}"
    if truncated:
        lead = (f"{step.name} agent was cut short on attempt {attempt} "
                f"(hit the {max_iterations}-turn limit or was stopped "
                f"by stuck detection)")
        if text is not None:
            return (f"## {step.name} output (attempt {attempt} — truncated)\n\n"
                    f"{lead}. Its findings so far:\n\n{text}")
        return f"{lead} and wrote no report."
    if text is None:
        return f"{step.name} agent did not write `{rel}` on attempt {attempt}."
    return (f"{step.name} agent wrote `{rel}` on attempt {attempt} but its "
            f"verdict is unparseable (expected `VERDICT: {step.verdicts.pass_}` or "
            f"`VERDICT: {step.verdicts.fail}` on its own line). "
            f"Its findings so far:\n\n{text}")


def make_agent_node(runtime: Runtime, step: StepConfig):
    """Node closure for an agent step. Steps without `artifact` run and
    continue; verdict steps parse the artifact (LAST VERDICT line wins,
    decoration-tolerant) and record pass/fail/None into step_verdicts."""
    verdicts_map = None
    if step.verdicts is not None:
        verdicts_map = {step.verdicts.pass_: "pass", step.verdicts.fail: "fail"}

    def node(state: dict) -> dict:
        attempt = state["attempt"]
        subject = state["subject"]
        max_iterations = step.max_iterations or DEFAULT_MAX_ITERATIONS
        print(f"[{subject}] Running {step.agent} agent...", flush=True)
        result = run_agent(step.agent, state["context"], runtime,
                           max_iterations=max_iterations)
        if not result.ok:
            print(f"[{subject}] {step.name} agent failed on attempt {attempt}.", flush=True)
            return {"failed": True}
        if verdicts_map is None:
            return {"failed": False}

        verdict, text = _read_stage_artifact(
            runtime.state_dir, step.artifact, verdicts_map)
        merged = {**state["step_verdicts"], step.name: verdict}
        if verdict == "pass":
            print(f"[{subject}] {step.name} VERDICT: PASS on attempt {attempt}.", flush=True)
            return {"step_verdicts": merged, "failed": False}
        if verdict == "fail":
            print(f"[{subject}] {step.name} verdict: fail on attempt {attempt}.", flush=True)
            update = {"step_verdicts": merged,
                      "notes": [f"## {step.name} output (attempt {attempt})\n\n{text}"]}
            if isinstance(step.on_fail, Route) and step.on_fail.retry:
                update["retry_target"] = step.on_fail.goto
            return update
        print(f"[{subject}] {step.name} verdict unclear on attempt {attempt}, retrying.",
              flush=True)
        return {"step_verdicts": merged,
                "notes": [_unclear_note(runtime, step, attempt, text,
                                        result.truncated, max_iterations)],
                "retry_target": _unclear_target(runtime, step)}

    return node


def make_action_node(runtime: Runtime, step: StepConfig):
    """Node closure for an action step: invoke the registered action with the
    step's params. An action exception fails the run (same as an agent's)."""
    fn = runtime.registry.actions[step.action]

    def node(state: dict) -> dict:
        try:
            return fn(state, step.params) or {}
        except Exception:
            print(traceback.format_exc()[-4000:], file=sys.stderr, flush=True)
            return {"failed": True}

    return node


def make_router(runtime: Runtime, step: StepConfig):
    """Router closure — a pure function of state, so control flow is
    deterministic by construction. Return values are node names (resolved
    dynamically by LangGraph), "bump", "success", or END (failure)."""
    order = [s.name for s in runtime.cfg.steps]

    def resolve(route) -> str:
        target = route_target(route)
        if target is None:  # omitted on_pass: next step, or success at the end
            idx = order.index(step.name)
            return order[idx + 1] if idx + 1 < len(order) else "success"
        if target == "failure":
            return END
        return target  # a step name, or the success node

    def router(state: dict) -> str:
        if state["failed"]:
            return END
        if step.verdicts is None:
            return resolve(step.on_pass)
        verdict = state["step_verdicts"].get(step.name)
        if verdict == "pass":
            return resolve(step.on_pass)
        if verdict == "fail":
            if step.on_fail is None:
                return END
            if isinstance(step.on_fail, Route) and step.on_fail.retry:
                return "bump" if state["attempt"] < state["max_attempts"] else END
            return resolve(step.on_fail)
        # Unclear — implicit retry, attempt-bounded (fixed policy).
        return "bump" if state["attempt"] < state["max_attempts"] else END

    return router


def make_bump_node(runtime: Runtime):
    """Close the retry cycle: consume one attempt, clear per-attempt
    artifacts, and rebuild the context with the accumulated notes — the
    attempt-start duties yosk's dev node owned, generalized to any target."""

    def node(state: dict) -> dict:
        clear_attempt_artifacts(runtime)
        context = build_context(runtime, state["docs"], state["subject"],
                                state["notes"])
        return {"attempt": state["attempt"] + 1,
                "step_verdicts": {},
                "context": context,
                "failed": False}

    return node


def success_node(_state: dict) -> dict:
    """The success terminal as a real node — any step may route here."""
    return {"outcome": "success"}

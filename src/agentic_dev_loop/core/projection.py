"""Workflow projection — pure functions that turn a validated PipelineConfig
into a Claude Dynamic Workflow (unit-4).

The projection runs at workflow-creation time; the generated JS is
self-contained (step data + prompt refs + routing baked in). Runtime never
parses pipeline.yaml (BR-1). Everything here is dependency-light: pydantic +
PyYAML + stdlib only (BR-2).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import Route, PipelineConfig, route_target

_KINDS = ("agent", "command", "action")


def core_version() -> str:
    """The installed distribution version — the single source of truth for
    the generated-JS header stamp (FD-5)."""
    try:
        return importlib.metadata.version("agentic-dev-loop")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0+dev"


def pipeline_hash(pipeline_path: str | Path) -> str:
    """The first 12 chars of the sha256 of the absolute pipeline-file path —
    the same digest the engine uses for its per-pipeline state dir."""
    return hashlib.sha256(
        str(Path(pipeline_path).resolve()).encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class ProjectedStep:
    """One step, projected for the workflow: routing + verdict config + the
    prompt *reference* (BR-5 — never embedded)."""

    id: str
    kind: str
    command: str | None = None
    prompt_path: str | None = None
    action: str | None = None  # action steps (workflow mode supports commit)
    params: dict | None = None  # action params (e.g. commit message template)
    verdicts: dict[str, str] | None = None  # keyword -> canonical pass/fail
    on_pass: str | None = None
    on_fail: str | None = None
    retry: bool = False  # on_fail is {goto, retry: true}
    max_attempts: int = 3
    timeout: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in _KINDS:
            raise ValueError(f"step {self.id!r}: unknown kind {self.kind!r}")
        if self.kind == "agent" and self.prompt_path is None:
            raise ValueError(f"agent step {self.id!r}: missing prompt reference")
        if self.kind == "command" and not self.command:
            raise ValueError(f"command step {self.id!r}: missing command")
        if self.kind == "action" and not self.action:
            raise ValueError(f"action step {self.id!r}: missing action name")

    @staticmethod
    def from_config(step, agents_dir: Path, max_attempts: int) -> "ProjectedStep":
        command: str | None = None
        prompt_path: str | None = None
        action: str | None = None
        if step.kind == "agent":
            # POSIX form (BR-5): the reference is a workspace-relative
            # path, and forward slashes keep the golden render machine-
            # independent (Windows CI bakes the same bytes as POSIX).
            prompt_path = (agents_dir / f"{step.agent}.agent.md").as_posix()
        elif step.kind == "command":
            command = step.command
        elif step.kind == "action":
            action = step.action
        verdicts: dict[str, str] | None = None
        if step.verdicts is not None:
            verdicts = {step.verdicts.pass_: "pass", step.verdicts.fail: "fail"}
        on_fail = route_target(step.on_fail)
        return ProjectedStep(
            id=step.name,
            kind=step.kind,
            command=command,
            prompt_path=prompt_path,
            action=action,
            params=dict(step.params) if step.params else None,
            verdicts=verdicts,
            on_pass=route_target(step.on_pass),
            on_fail=on_fail,
            retry=isinstance(step.on_fail, Route) and step.on_fail.retry,
            max_attempts=max_attempts,
            timeout=step.timeout,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "command": self.command,
            "prompt_path": self.prompt_path,
            "action": self.action,
            "params": self.params,
            "verdicts": self.verdicts,
            "on_pass": self.on_pass,
            "on_fail": self.on_fail,
            "retry": self.retry,
            "max_attempts": self.max_attempts,
            "timeout": self.timeout,
        }


@dataclass(frozen=True)
class WorkflowProjection:
    """The frozen result of `project_workflow` — everything the generated JS
    needs, nothing it doesn't (no `llm` block, no engine-only fields)."""

    pipeline_name: str
    pipeline_hash: str
    core_version: str
    steps: list[ProjectedStep] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("workflow projection requires at least one step")

    def steps_data(self) -> list[dict]:
        return [s.to_dict() for s in self.steps]


def project_workflow(cfg: PipelineConfig, agents_dir: str | Path,
                     pipeline_hash: str) -> WorkflowProjection:
    """Project a validated PipelineConfig into a WorkflowProjection.

    Reuses the already-loaded/validated config (routing targets and step
    shape are checked by `PipelineConfig`); the only build-time check added
    here is prompt-reference existence (BR-4)."""
    agents_dir = Path(agents_dir)
    steps = [ProjectedStep.from_config(s, agents_dir, cfg.max_attempts)
             for s in cfg.steps]
    projection = WorkflowProjection(
        pipeline_name=cfg.name,
        pipeline_hash=pipeline_hash,
        core_version=core_version(),
        steps=steps,
    )
    validate_prompt_refs(projection, agents_dir)
    return projection


def validate_prompt_refs(projection: WorkflowProjection,
                         agents_dir: str | Path) -> None:
    """Every agent step's `.agent.md` must exist at build time (BR-4).

    A missing prompt fails the build loudly, naming the file — never
    silently generates a broken workflow."""
    agents_dir = Path(agents_dir)
    for step in projection.steps:
        if step.kind == "agent" and step.prompt_path is not None:
            prompt = Path(step.prompt_path)
            if not prompt.is_file():
                rel = prompt
                try:
                    rel = prompt.relative_to(agents_dir)
                except ValueError:
                    pass
                raise FileNotFoundError(
                    f"workflow agent step {step.id!r}: prompt file not found: "
                    f"{rel} (under {agents_dir})")


# The wheel-shipped workflow JS template (FD-5). It ships as package data
# next to this module (a real file, not an inline string — TS-6/KD-3) and is
# filled by render_workflow_js at build time. The deterministic loop — step
# routing, the attempt counter, retry-note injection, clean-at-start, the viz
# launch, and the gated commit — lives entirely inside the template.
WORKFLOW_TEMPLATE = (
    Path(__file__).with_name("workflow.js.template").read_text(encoding="utf-8")
)


def render_workflow_js(template: str, projection: WorkflowProjection,
                       core_version: str, pipeline_hash: str) -> str:
    """Fill the wheel-shipped template from a projection (FD-5).

    Deterministic given (template, projection, core_version, pipeline_hash):
    the version + hash appear only in the first-line header, so a differing
    stamp changes the header alone — the baked steps never vary with it."""
    steps_json = json.dumps(projection.steps_data(), sort_keys=True, indent=2)
    return (
        template
        .replace("{{CORE_VERSION}}", core_version)
        .replace("{{PIPELINE_HASH}}", pipeline_hash)
        .replace("{{PIPELINE_NAME}}", json.dumps(projection.pipeline_name))
        .replace("{{STEPS_JSON}}", steps_json)
    )


def clean_at_start_flag(git_porcelain_output: str) -> bool:
    """True when `git status --porcelain` is empty — the worktree was clean
    at run start, so the auto-commit is allowed (BR-8, FD-3)."""
    return not git_porcelain_output.strip()

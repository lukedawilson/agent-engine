"""Pipeline YAML schema and loader. Strict: unknown keys fail at every level."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TERMINALS = frozenset({"success", "failure"})


class VerdictSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    pass_: str = Field(alias="pass")
    fail: str = Field(alias="fail")


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goto: str
    retry: bool = False  # True consumes an attempt; exhaustion routes to failure


RouteTarget = str | Route


def route_target(route: RouteTarget | None) -> str | None:
    if route is None:
        return None
    return route.goto if isinstance(route, Route) else route


class IsolationConfig(BaseModel):
    """Optional `isolation:` section — configures the always-on sandbox (BR-2).
    Absence means opinionated defaults, never unsandboxed behaviour. Unknown
    keys fail at load (BR-5). `state_dir` is HOST-ONLY (stamps + audit) and is
    never mounted into the sandbox (Q1)."""

    model_config = ConfigDict(extra="forbid")

    image: str | None = None            # per-pipeline override (KD-2 ref rules)
    refresh: bool = False               # force re-provision (NFR-5)
    memory: str | None = None           # override exec container memory
    cpus: float | None = None           # override exec container cpus
    allow_git_mutations: bool = False   # BR-6 knob
    state_dir: str = "~/.agentic-dev-loop/state"  # stamps + audit (host-only)

    @field_validator("memory")
    @classmethod
    def _check_memory(cls, v: str | None) -> str | None:
        if v is not None and re.fullmatch(r"\d+[kmg]", v) is None:
            raise ValueError(f"memory {v!r} must match ^\\d+[kmg]$")
        return v

    @field_validator("cpus")
    @classmethod
    def _check_cpus(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("cpus must be > 0")
        return v


class StepConfig(BaseModel):
    """One pipeline step. Its type IS the key it carries: exactly one of
    `agent`, `action`, or `command` — empty values do not count, anything
    else fails to load. See the `kind` property (the single discriminator
    graph-building dispatches on)."""
    model_config = ConfigDict(extra="forbid")

    name: str
    agent: str | None = None
    action: str | None = None
    command: str | None = None  # mechanical step: exit code is the verdict
    params: dict[str, Any] = {}
    produces: list[str] = []  # hygiene-tracked, no verdict parsing
    artifact: str | None = None  # hygiene-tracked AND verdict-parsed
    verdicts: VerdictSpec | None = None
    max_iterations: int | None = None
    timeout: float | None = Field(default=None, gt=0)  # seconds, command steps only
    env: dict[str, str | None] | None = None  # NFR-1: null = inherit host value
    setup: str | None = None  # BR-13: command steps only
    network: bool = False  # per-stage egress (command + agent steps; action steps reject)
    on_pass: RouteTarget | None = None
    on_fail: RouteTarget | None = None

    @property
    def kind(self) -> str:
        """The step's type: 'agent', 'command', or 'action'. Which of the
        three keys is set is the ONLY signal; validation has already
        guaranteed exactly one is set and non-empty by the time any instance
        exists."""
        if self.agent is not None:
            return "agent"
        if self.command is not None:
            return "command"
        return "action"

    @field_validator("produces", mode="before")
    @classmethod
    def _coerce_produces(cls, v: Any) -> Any:
        return [v] if isinstance(v, str) else v

    @model_validator(mode="after")
    def _check_shape(self) -> "StepConfig":
        for key in ("agent", "action", "command"):
            value = getattr(self, key)
            if value is not None and not value.strip():
                raise ValueError(
                    f"step {self.name!r}: {key!r} must be a non-empty string"
                )
        if sum(k is not None for k in (self.agent, self.action, self.command)) != 1:
            raise ValueError(
                f"step {self.name!r}: exactly one of 'agent', 'action', or "
                "'command' is required"
            )
        if self.command is not None:
            for field, empty in (("artifact", None), ("verdicts", None),
                                 ("produces", []), ("params", {}),
                                 ("max_iterations", None)):
                if getattr(self, field) != empty:
                    raise ValueError(
                        f"step {self.name!r}: 'command' steps cannot set {field!r}"
                    )
        if (self.artifact is None) != (self.verdicts is None):
            raise ValueError(
                f"step {self.name!r}: 'artifact' and 'verdicts' must appear together"
            )
        if self.artifact is not None and self.produces:
            raise ValueError(
                f"step {self.name!r}: 'produces' and 'artifact' are mutually exclusive"
            )
        if self.timeout is not None and self.command is None:
            raise ValueError(
                f"step {self.name!r}: 'timeout' requires 'command'"
            )
        if self.setup is not None and self.command is None:
            raise ValueError(
                f"step {self.name!r}: 'setup' is only allowed on 'command' steps"
            )
        if self.network and self.action is not None:
            raise ValueError(
                f"step {self.name!r}: 'network' is only allowed on 'agent' or "
                "'command' steps"
            )
        return self


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    base_url: str | None = None
    api_key_env: str
    timeout: float | None = None  # omitted → opinionated no-timeout default


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    extensions: list[str] = []
    additional_files: list[str] = []
    env_allowlist: list[str] = []
    llm: LlmConfig
    isolation: IsolationConfig | None = None  # None = always-on defaults
    state_dir: str = ".pr"  # default relocated to ~/.agentic-dev-loop/runs/<hash>/ at load
    max_attempts: int = 3
    agents_dir: str
    steps: list[StepConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_graph(self) -> "PipelineConfig":
        names = [s.name for s in self.steps]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate step names: {dupes}")
        for n in names:
            if n in TERMINALS:
                raise ValueError(f"step name {n!r} collides with a reserved terminal")
        valid = set(names) | TERMINALS
        for step in self.steps:
            for route in (step.on_pass, step.on_fail):
                target = route_target(route)
                if target is not None and target not in valid:
                    raise ValueError(
                        f"step {step.name!r}: unknown route target {target!r}"
                    )
        return self


def default_state_dir(pipeline_path: Path) -> str:
    """The new run-state default (Q1): checkpoint DB + last-error.md live OUTSIDE
    the workspace mount, under ~/.agentic-dev-loop/runs/<pipeline-hash>/ where
    pipeline-hash is the first 12 chars of the sha256 of the absolute
    pipeline-file path. Explicit `state_dir:` configs keep working unchanged."""
    digest = hashlib.sha256(
        str(Path(pipeline_path).resolve()).encode("utf-8")).hexdigest()[:12]
    return str(Path("~/.agentic-dev-loop/runs").expanduser() / digest)


def load_config(path: Path) -> PipelineConfig:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(
            f"pipeline config must be a mapping, got {type(data).__name__}: {path}"
        )
    if "state_dir" not in data:
        data["state_dir"] = default_state_dir(path)
    return PipelineConfig.model_validate(data)

"""Pipeline YAML schema and loader. Strict: unknown keys fail at every level."""

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


class StepConfig(BaseModel):
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
    on_pass: RouteTarget | None = None
    on_fail: RouteTarget | None = None

    @field_validator("produces", mode="before")
    @classmethod
    def _coerce_produces(cls, v: Any) -> Any:
        return [v] if isinstance(v, str) else v

    @model_validator(mode="after")
    def _check_shape(self) -> "StepConfig":
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
        return self


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    base_url: str | None = None
    api_key_env: str
    extra_body: dict[str, Any] | None = None
    timeout: float | None = None  # omitted → opinionated no-timeout default


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    extensions: list[str] = []
    additional_files: list[str] = []
    llm: LlmConfig
    state_dir: str = ".pr"
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


def load_config(path: Path) -> PipelineConfig:
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(
            f"pipeline config must be a mapping, got {type(data).__name__}: {path}"
        )
    return PipelineConfig.model_validate(data)

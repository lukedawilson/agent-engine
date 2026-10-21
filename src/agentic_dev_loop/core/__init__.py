"""Pipeline model + parse + workflow projection (unit-4 core).

Dependency-light by contract (BR-2): pydantic + PyYAML + stdlib only. A guard
test fails if this package imports engine/viz or heavy deps.
"""

from .config import (PipelineConfig, StepConfig, LlmConfig, IsolationConfig,
                     VerdictSpec, Route, route_target, load_config,
                     default_state_dir, TERMINALS)
from .results import Result
from .verdict import Verdict, VerdictError, parse_verdict, RETRY
from .projection import (ProjectedStep, WorkflowProjection, project_workflow,
                         validate_prompt_refs, render_workflow_js,
                         clean_at_start_flag, pipeline_hash, core_version,
                         WORKFLOW_TEMPLATE)

__all__ = [
    "PipelineConfig", "StepConfig", "LlmConfig", "IsolationConfig",
    "VerdictSpec", "Route", "route_target", "load_config",
    "default_state_dir", "TERMINALS",
    "Result", "Verdict", "VerdictError", "parse_verdict", "RETRY",
    "ProjectedStep", "WorkflowProjection", "project_workflow",
    "validate_prompt_refs", "render_workflow_js", "clean_at_start_flag",
    "pipeline_hash", "core_version", "WORKFLOW_TEMPLATE",
]

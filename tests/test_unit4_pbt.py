"""Unit-4 property-based tests — the pure-function invariants of the Claude
Dynamic Workflows driver (projection, prompt-ref validation, template
determinism, verdict totality, token uniqueness, and the module guard)."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

import agentic_dev_loop
from agentic_dev_loop.core import (ProjectedStep, WorkflowProjection,
                                   clean_at_start_flag, parse_verdict,
                                   pipeline_hash, project_workflow,
                                   render_workflow_js, WORKFLOW_TEMPLATE,
                                   Route)
from agentic_dev_loop.core.config import PipelineConfig, load_config
from agentic_dev_loop.viz import issue_ingest_token

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
SHIPPED_PIPELINE = REPO_ROOT / "agentic-dev-loop" / "pipeline.yaml"
SHIPPED_AGENTS = REPO_ROOT / "agentic-dev-loop" / "sdk_agents"


# ── 1. Projection round-trip ────────────────────────────────────────────

@st.composite
def command_pipelines(draw):
    n = draw(st.integers(min_value=2, max_value=6))
    max_attempts = draw(st.integers(min_value=1, max_value=50))
    names = [f"step_{i}" for i in range(n)]
    steps = []
    for i, name in enumerate(names):
        on_pass = names[i + 1] if i + 1 < n else "success"
        on_fail = None
        if i > 0:
            on_fail = {"goto": names[0], "retry": draw(st.booleans())}
        timeout = draw(st.one_of(st.none(), st.floats(0.1, 600.0)))
        steps.append({
            "name": name,
            "command": f"echo {name}",
            "on_pass": on_pass,
            "on_fail": on_fail,
            "timeout": timeout,
        })
    return {
        "name": "pbt-pipeline",
        "llm": {"model": "m", "base_url": "http://localhost", "api_key_env": "K"},
        "agents_dir": "agents",
        "max_attempts": max_attempts,
        "steps": steps,
    }


@given(command_pipelines())
@settings(max_examples=50)
def test_projection_round_trip_command_steps(cfg_dict):
    cfg = PipelineConfig.model_validate(cfg_dict)
    proj = project_workflow(cfg, REPO_ROOT / "agents", "hash123")
    assert proj.pipeline_hash == "hash123"
    assert proj.pipeline_name == cfg.name
    assert [s.id for s in proj.steps] == [s.name for s in cfg.steps]
    for ps, cs in zip(proj.steps, cfg.steps):
        assert ps.kind == cs.kind
        assert ps.max_attempts == cfg.max_attempts
        assert ps.timeout == cs.timeout
        assert ps.on_pass == (cs.on_pass.goto if isinstance(cs.on_pass, Route)
                              else cs.on_pass)
        assert ps.on_fail == (cs.on_fail.goto if isinstance(cs.on_fail, Route)
                              else cs.on_fail)
        assert ps.retry == (isinstance(cs.on_fail, Route) and cs.on_fail.retry)


def test_projection_round_trip_shipped_pipeline():
    cfg = load_config(SHIPPED_PIPELINE)
    proj = project_workflow(cfg, SHIPPED_AGENTS,
                            pipeline_hash(SHIPPED_PIPELINE))
    by_name = {s.id: s for s in proj.steps}
    assert [s.id for s in proj.steps] == ["dev", "test", "review", "qa", "commit"]
    assert all(s.max_attempts == 10 for s in proj.steps)

    dev = by_name["dev"]
    assert dev.kind == "agent"
    assert Path(dev.prompt_path).name == "dev.agent.md"
    assert dev.verdicts is None

    test = by_name["test"]
    assert test.kind == "command"
    assert "pytest" in test.command
    assert test.on_pass == "review"
    assert test.on_fail == "dev" and test.retry is True

    review = by_name["review"]
    assert review.kind == "agent"
    assert review.verdicts == {"APPROVED": "pass", "NEEDS CHANGES": "fail"}
    assert review.on_pass == "qa" and review.on_fail == "dev"

    qa = by_name["qa"]
    assert qa.verdicts == {"PASS": "pass", "FAIL": "fail"}
    assert qa.on_pass == "commit" and qa.on_fail == "dev"

    commit = by_name["commit"]
    assert commit.kind == "action"
    assert commit.on_pass == "success"


# ── 2. Prompt-ref validation ────────────────────────────────────────────

def test_prompt_ref_missing_fails_loud(tmp_path):
    cfg = PipelineConfig.model_validate({
        "name": "p", "llm": {"model": "m", "base_url": "http://x",
                             "api_key_env": "K"},
        "agents_dir": "agents", "max_attempts": 3,
        "steps": [{"name": "dev", "agent": "dev", "on_pass": "success"}],
    })
    agents = tmp_path / "agents"
    agents.mkdir()
    with pytest.raises(FileNotFoundError, match="dev.agent.md"):
        project_workflow(cfg, agents, "hash")


def test_prompt_ref_present_succeeds(tmp_path):
    cfg = PipelineConfig.model_validate({
        "name": "p", "llm": {"model": "m", "base_url": "http://x",
                             "api_key_env": "K"},
        "agents_dir": "agents", "max_attempts": 3,
        "steps": [{"name": "dev", "agent": "dev", "on_pass": "success"}],
    })
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "dev.agent.md").write_text("# dev\n")
    proj = project_workflow(cfg, agents, "hash")
    assert Path(proj.steps[0].prompt_path).is_file()


# ── 3. Template determinism ─────────────────────────────────────────────

def _sample_projection() -> WorkflowProjection:
    cfg = load_config(SHIPPED_PIPELINE)
    return project_workflow(cfg, SHIPPED_AGENTS, "abc123")


def test_template_same_inputs_same_output():
    proj = _sample_projection()
    a = render_workflow_js(WORKFLOW_TEMPLATE, proj, "1.0.0", "abc123")
    b = render_workflow_js(WORKFLOW_TEMPLATE, proj, "1.0.0", "abc123")
    assert a == b


def test_template_stamp_changes_header_only():
    proj = _sample_projection()
    a = render_workflow_js(WORKFLOW_TEMPLATE, proj, "1.0.0", "aaa")
    b = render_workflow_js(WORKFLOW_TEMPLATE, proj, "2.0.0", "bbb")
    assert a != b
    # Strip the first-line header; the baked body must be identical.
    assert a.split("\n", 1)[1] == b.split("\n", 1)[1]
    assert "2.0.0" in b.split("\n", 1)[0]
    assert "bbb" in b.split("\n", 1)[0]


def test_render_embeds_step_data_and_prompt_refs():
    proj = _sample_projection()
    js = render_workflow_js(WORKFLOW_TEMPLATE, proj, "1.0.0", "abc123")
    assert "dev.agent.md" in js
    assert '"kind": "agent"' in js or "'agent'" in js
    assert "pytest" in js


# ── 4. Verdict parse totality ───────────────────────────────────────────

VERDICTS = {"PASS": "pass", "FAIL": "fail"}

@st.composite
def arbitrary_text(draw):
    return draw(st.text(alphabet=st.characters(blacklist_categories=("Cc", "Cs")),
                        max_size=200))


@given(arbitrary_text())
@settings(max_examples=200)
def test_parse_verdict_totality(text):
    route = parse_verdict(text, VERDICTS)
    assert route in {"pass", "fail", "retry"}


def test_parse_verdict_clear_and_unclear():
    assert parse_verdict("VERDICT: PASS", VERDICTS) == "pass"
    assert parse_verdict("VERDICT: FAIL", VERDICTS) == "fail"
    assert parse_verdict("", VERDICTS) == "retry"
    assert parse_verdict("no verdict here", VERDICTS) == "retry"
    assert parse_verdict("VERDICT: PASS\nVERDICT: FAIL", VERDICTS) == "retry"


# ── 5. Token uniqueness ─────────────────────────────────────────────────

@given(st.integers(min_value=2, max_value=200))
@settings(max_examples=50)
def test_issue_ingest_token_unique(n):
    tokens = [issue_ingest_token() for _ in range(n)]
    assert len(set(tokens)) == n
    assert all(len(t) >= 32 for t in tokens)


# ── 6. Guard contract — core imports no engine/viz/heavy deps ──────────

FORBIDDEN = ("agentic_dev_loop.engine", "agentic_dev_loop.viz",
             "openhands", "langgraph", "langchain", "docker")

# `viz` may import `core` (dependency-light pydantic/PyYAML) but never the
# heavy engine/SDK deps — the workflow-mode boundary (TS-4 / BR-2).
VIZ_FORBIDDEN = ("agentic_dev_loop.engine", "openhands", "langgraph",
                 "langchain", "docker")


def _forbidden_imports(py_dir: Path, forbidden: tuple[str, ...]) -> list[str]:
    offenders: list[str] = []
    for py in py_dir.glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if name.startswith(forbidden):
                    offenders.append(f"{py.name}: forbidden import {name!r}")
    return offenders


def test_core_import_graph_guard():
    core_dir = Path(agentic_dev_loop.core.__file__).parent
    assert _forbidden_imports(core_dir, FORBIDDEN) == []


def test_viz_import_graph_guard():
    import agentic_dev_loop.viz
    viz_dir = Path(agentic_dev_loop.viz.__file__).parent
    assert _forbidden_imports(viz_dir, VIZ_FORBIDDEN) == []


def test_core_fresh_import_loads_no_heavy_deps():
    code = (
        "import sys, json\n"
        "import agentic_dev_loop.core\n"
        "heavy = sorted(m for m in sys.modules if any(\n"
        "    m == p or m.startswith(p + '.') for p in "
        "['openhands', 'langgraph', 'langchain', 'docker', "
        "'agentic_dev_loop.engine', 'agentic_dev_loop.viz']))\n"
        "print(json.dumps(heavy))\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True, env=env,
                         cwd=REPO_ROOT)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", out.stdout


def test_viz_fresh_import_loads_no_heavy_deps():
    code = (
        "import sys, json\n"
        "import agentic_dev_loop.viz\n"
        "heavy = sorted(m for m in sys.modules if any(\n"
        "    m == p or m.startswith(p + '.') for p in "
        "['openhands', 'langgraph', 'langchain', 'docker', "
        "'agentic_dev_loop.engine']))\n"
        "print(json.dumps(heavy))\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    out = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True, env=env,
                         cwd=REPO_ROOT)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", out.stdout

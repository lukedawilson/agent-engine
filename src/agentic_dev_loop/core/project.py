"""Build-time projection entry point (FD-5).

`python -m agentic_dev_loop.core.project <pipeline.yaml>` loads + validates
the pipeline, projects it, checks prompt references (BR-4), and renders the
self-contained workflow JS to `.agentic-dev-loop/workflow.js` in the
pipeline's directory. Runtime never parses the YAML (BR-1).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import load_config
from .projection import (WORKFLOW_TEMPLATE, core_version, pipeline_hash,
                         project_workflow, render_workflow_js)

OUTPUT_DIR = ".agentic-dev-loop"
OUTPUT_FILE = "workflow.js"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentic-dev-loop-project",
        description="Project pipeline.yaml into a Claude Dynamic Workflow JS.")
    parser.add_argument("pipeline", type=Path, nargs="?",
                        default=Path("pipeline.yaml"),
                        help="path to the pipeline YAML (default: pipeline.yaml)")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="where to write the generated JS (default: "
                             "<pipeline dir>/.agentic-dev-loop/workflow.js)")
    args = parser.parse_args(argv)

    pipeline_path = args.pipeline
    cfg = load_config(pipeline_path)
    base = pipeline_path.resolve().parent
    agents_dir = base / cfg.agents_dir
    phash = pipeline_hash(pipeline_path)

    # Bake workspace-relative prompt references (BR-5): the generated
    # workflow re-reads each `.agent.md` from the workspace at run time, so
    # the reference must be relative to the invocation directory (Claude
    # Code's workspace), never an absolute host path. Fall back to the
    # absolute path when the pipeline lives on a different volume (Windows).
    try:
        agents_ref = Path(os.path.relpath(agents_dir, Path.cwd().resolve()))
    except ValueError:
        agents_ref = agents_dir

    projection = project_workflow(cfg, agents_ref, phash)
    js = render_workflow_js(WORKFLOW_TEMPLATE, projection, core_version(), phash)

    out = args.output or (base / OUTPUT_DIR / OUTPUT_FILE)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(js, encoding="utf-8")
    print(f"Projected {cfg.name!r} ({len(projection.steps)} steps) -> {out}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

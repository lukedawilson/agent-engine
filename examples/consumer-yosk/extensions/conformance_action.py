"""Sample consumer action extension: run the repo's conformance script as a
hard gate.

An action has no verdict channel — it either returns (routing continues via
on_pass) or raises (the run fails, like an agent exception). Use this shape
for checks that must stop the line rather than feed a retry loop; for
retry-driven fixing prefer a verdict agent step (the example pipeline's
checks stage).

Wire-up: put this module on the import path and name it in the pipeline:

    extensions:
      - conformance_action:ConformanceExtension
    steps:
      - name: conformance
        action: run_conformance
        params: { script: tools/run-conformance.sh }
        on_pass: review
"""

import subprocess
from pathlib import Path


def run_conformance(_state: dict, params: dict) -> dict:
    """Run `params.script` in the consumer repo (process cwd). Exit 0 passes;
    any failure raises with the script's output tail, so the run dies with
    the evidence visible (make_action_node prints it, like an agent error)."""
    script = params["script"]
    result = subprocess.run(["bash", script], cwd=Path.cwd(),
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        raise RuntimeError(
            f"conformance script {script!r} failed (exit "
            f"{result.returncode}):\n{output[-3000:]}")
    return {}


class ConformanceExtension:
    name = "conformance"

    def register(self, registry) -> None:
        registry.add_action("run_conformance", run_conformance)

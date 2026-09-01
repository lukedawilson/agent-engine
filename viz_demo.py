"""Manual smoke harness for the viz page: Storybook-style, minus the pipeline.

Serves the real embedded page + the real self-loop topology (built from
examples/self/pipeline.yaml, no LLM construction), then publishes a scripted
run to the bus so every visual state can be eyeballed in the browser: pending
→ running → passed/failed nodes, verdict badges (fail on attempt 1, reset on
bump, pass on attempt 2), the attempt counter, the scrolling event log, and
the run_finished banner.

Usage:
    .venv/bin/python viz_demo.py [--port 8321] [--scenario success|failure]
                                 [--no-browser]

Ctrl-C to stop. No agents run, no LLM calls, no checkpoints — the events are
fabricated here; only viz.py's server/page code is exercised.
"""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from pathlib import Path

from agent_engine import viz
from agent_engine.config import load_config

EXAMPLE = Path(__file__).parent / "examples" / "self" / "pipeline.yaml"
SUBJECT = "plan demo.md"

NODE_GAP = 1.0    # between nodes — the pace a watcher sees
EVENT_GAP = 0.35  # between the started/state/finished bursts of one node


def real_topology() -> tuple[str, list[str]]:
    """The shipped self-loop example's vertical flowchart — solid happy-path
    chain, dotted labeled loop-backs, and the success terminal — exactly as
    a live run serves it."""
    return viz.topology_mermaid(load_config(EXAMPLE))


def emit_node(bus: viz.VizBus, name: str, state: dict | None = None,
              ok: bool = True) -> None:
    """One node's real event cadence: started → heartbeat → state →
    heartbeat → finished, so the elapsed line is eyeballable without an LLM."""
    started = time.monotonic()
    bus.publish({"type": "node_started", "node": name})
    bus.publish({"type": "heartbeat", "node": name,
                 "elapsed_seconds": int(time.monotonic() - started)})
    time.sleep(EVENT_GAP)
    bus.publish({"type": "state", **(state or {})})
    time.sleep(EVENT_GAP)
    bus.publish({"type": "heartbeat", "node": name,
                 "elapsed_seconds": int(time.monotonic() - started)})
    bus.publish({"type": "node_finished", "node": name, "ok": ok})
    time.sleep(NODE_GAP)


def run_scenario(bus: viz.VizBus, scenario: str) -> None:
    """Fabricate one run. `success`: checks fails its verdict on attempt 1,
    bump retries to dev, everything passes on attempt 2. `failure`: the
    checks node itself hard-fails on attempt 1 (red node, failure banner)."""
    bus.publish({"type": "run_started", "subject": SUBJECT,
                 "max_attempts": 3, "thread_id": "viz-demo", "attempt": 1})
    time.sleep(NODE_GAP)

    emit_node(bus, "dev", {"attempt": 1})
    if scenario == "failure":
        emit_node(bus, "checks", ok=False)
        bus.publish({"type": "run_finished", "success": False, "attempts": 1})
        return

    emit_node(bus, "checks", {"step_verdicts": {"checks": "fail"}})
    emit_node(bus, "bump", {"attempt": 2, "step_verdicts": {}})
    emit_node(bus, "dev")
    emit_node(bus, "checks", {"step_verdicts": {"checks": "pass"}})
    emit_node(bus, "review",
              {"step_verdicts": {"checks": "pass", "review": "pass"}})
    emit_node(bus, "port_sweep")
    emit_node(bus, "qa", {"step_verdicts": {"checks": "pass",
                                            "review": "pass", "qa": "pass"}})
    emit_node(bus, "commit")
    emit_node(bus, "success", {"outcome": "success"})
    bus.publish({"type": "run_finished", "success": True, "attempts": 2})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8321,
                        help="port for the demo server (default: 8321)")
    parser.add_argument("--scenario", choices=["success", "failure"],
                        default="success")
    parser.add_argument("--no-browser", action="store_true",
                        help="print the URL but don't open a browser tab")
    args = parser.parse_args()

    bus = viz.VizBus()
    topology, nodes = real_topology()
    try:
        viz.serve_viz(bus, topology, SUBJECT, args.port, nodes)
    except OSError as exc:
        print(f"{exc}\nPick another port with --port.", file=sys.stderr)
        return 1

    url = f"http://127.0.0.1:{args.port}"
    print(f"Viz demo ({args.scenario}): {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)

    try:
        run_scenario(bus, args.scenario)
        print("Run finished — page keeps its final state. Ctrl-C to stop.",
              flush=True)
        viz.wait_for_interrupt()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

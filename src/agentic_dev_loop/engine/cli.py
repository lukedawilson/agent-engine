"""Two-phase CLI: phase 1 finds the pipeline YAML; phase 2 builds the full
parser — core flags plus every document loader's contributed args (the
built-in `plan` loader plus whatever the pipeline's `extensions:` register)
— and runs the pipeline. A loader's flag therefore exists only when its
extension is listed in that pipeline's YAML."""

import argparse
import importlib.metadata
import sys
from pathlib import Path

from agentic_dev_loop.core.config import PipelineConfig, load_config
from .dryrun import dry_run
from .isolation import clean_stamps, isolation_state_dir
from .registry import Registry, default_registry, load_extensions


def _version() -> str:
    """The installed distribution version — the single source of truth."""
    try:
        return importlib.metadata.version("agentic-dev-loop")
    except importlib.metadata.PackageNotFoundError:
        print("agentic-dev-loop is not installed — version unavailable; "
              "run `pip install -e .`", file=sys.stderr)
        raise SystemExit(1)


def _add_version_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--version", action="version",
                        version=f"agentic-dev-loop {_version()}")


def _core_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-dev-loop",
        description="Run an OpenHands agent pipeline defined in YAML. "
                    "Document-loader flags contributed by the pipeline's "
                    "extensions appear once PIPELINE is known — see "
                    "`agentic-dev-loop PIPELINE --help`.")
    parser.add_argument("pipeline", type=Path,
                        help="path to the pipeline YAML")
    parser.add_argument("--resume", metavar="THREAD_ID", default=None,
                        help="resume a checkpointed run by thread id")
    parser.add_argument("--max-attempts", type=int, default=None,
                        help="override the pipeline's max_attempts")
    parser.add_argument("--no-viz", action="store_true",
                        help="suppress the live graph view (served by "
                             "default)")
    parser.add_argument("--viz-port", type=int, default=8321,
                        help="preferred port for the live graph view "
                             "(default: 8321; falls back to a free port when "
                             "busy)")
    parser.add_argument("--refresh", action="store_true",
                        help="force re-provision of every setup: hook "
                             "(bypasses the stamp cache)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate the pipeline and print a summary plan "
                             "without executing anything (no LLM, no "
                             "sandbox, no state writes)")
    parser.add_argument("--clean-stamps", action="store_true",
                        help="delete cached provision stamps and exit")
    _add_version_flag(parser)
    return parser


def _registry_for(cfg_path: Path) -> tuple[Registry, PipelineConfig]:
    """Load the pipeline config and build ONE registry with its extensions.
    The CLI loads extensions exactly once per process: the SDK tool registry
    is process-global and BR-3 rejects a second registration of any tool
    name, so the registry built here is passed down to the dry run and the
    run path instead of being rebuilt."""
    cfg = load_config(cfg_path)
    registry = default_registry()
    load_extensions(cfg.extensions, registry)
    return registry, cfg


def build_parser(cfg_path) -> argparse.ArgumentParser:
    """The full parser for one pipeline: core flags + loader-contributed."""
    registry, _ = _registry_for(cfg_path)
    parser = _core_parser()
    for loader in registry.document_loaders:
        loader.add_cli_args(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument("pipeline", type=Path, nargs="?")
    _add_version_flag(probe)
    known, _ = probe.parse_known_args(argv)
    if known.pipeline is None:
        # No pipeline → the extension surface is unknowable; the core parser
        # handles --help and the missing-positional error itself (both exit).
        _core_parser().parse_args(argv)
        return 2  # unreachable — parse_args exits first
    registry, cfg = _registry_for(known.pipeline)
    parser = _core_parser()
    for loader in registry.document_loaders:
        loader.add_cli_args(parser)
    args = parser.parse_args(argv)
    if args.clean_stamps:
        state = isolation_state_dir(cfg)
        removed = clean_stamps(state)
        print(f"Removed {removed} cached provision stamp(s) from "
              f"{state / 'stamps'}", flush=True)
        return 0
    if args.dry_run:
        return dry_run(args.pipeline, args, registry)
    # The run path alone needs the heavy graph/SDK imports — defer so a
    # dry run, --clean-stamps, and --help stay side-effect free.
    from .graph import run_pipeline
    success, _attempts = run_pipeline(args.pipeline, args, registry=registry)
    if not success:
        print("agentic-dev-loop: pipeline failed — exiting with code 1",
              file=sys.stderr)
    return 0 if success else 1

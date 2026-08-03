"""Two-phase CLI: phase 1 finds the pipeline YAML; phase 2 builds the full
parser — core flags plus every document loader's contributed args (the
built-in `plan` loader plus whatever the pipeline's `extensions:` register)
— and runs the pipeline. A loader's flag therefore exists only when its
extension is listed in that pipeline's YAML."""

import argparse
from pathlib import Path

from .config import load_config
from .graph import run_pipeline
from .registry import default_registry, load_extensions


def _core_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-engine",
        description="Run an OpenHands agent pipeline defined in YAML. "
                    "Document-loader flags contributed by the pipeline's "
                    "extensions appear once PIPELINE is known — see "
                    "`agent-engine PIPELINE --help`.")
    parser.add_argument("pipeline", type=Path,
                        help="path to the pipeline YAML")
    parser.add_argument("--resume", metavar="THREAD_ID", default=None,
                        help="resume a checkpointed run by thread id")
    parser.add_argument("--max-attempts", type=int, default=None,
                        help="override the pipeline's max_attempts")
    return parser


def build_parser(cfg_path) -> argparse.ArgumentParser:
    """The full parser for one pipeline: core flags + loader-contributed."""
    cfg = load_config(cfg_path)
    registry = default_registry()
    load_extensions(cfg.extensions, registry)
    parser = _core_parser()
    for loader in registry.document_loaders:
        loader.add_cli_args(parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument("pipeline", type=Path, nargs="?")
    known, _ = probe.parse_known_args(argv)
    if known.pipeline is None:
        # No pipeline → the extension surface is unknowable; the core parser
        # handles --help and the missing-positional error itself (both exit).
        _core_parser().parse_args(argv)
        return 2  # unreachable — parse_args exits first
    args = build_parser(known.pipeline).parse_args(argv)
    success, _attempts = run_pipeline(args.pipeline, args)
    return 0 if success else 1

"""Built-in `plan` document loader + the loader-selection flow."""

import argparse
from pathlib import Path

from .registry import DocumentLoader, Registry


def resolve_plan_docs(plan_path: Path | str) -> dict[str, str]:
    """Load a single plan doc as the pipeline's full context — plan mode is
    self-contained (no unit/inception docs; shared files like coding
    standards come from the pipeline's `additional_files:`, appended by the
    runner)."""
    path = Path(plan_path)
    if not path.is_file():
        raise FileNotFoundError(f"Plan doc not found: {path}")
    return {path.name: path.read_text()}


class PlanDocumentLoader:
    name = "plan"
    defaultable = False  # needs a path — never autodetects

    def add_cli_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--plan", type=Path, default=None,
                            help="Path to a single plan doc")

    def resolve(self, args: argparse.Namespace) -> tuple[dict[str, str], str]:
        docs = resolve_plan_docs(args.plan)
        return docs, f"plan {args.plan.name}"


def select_loader(registry: Registry, args: argparse.Namespace) -> DocumentLoader | None:
    """The document-loader coexistence model — load many, invoke one:

    1. A loader flag present in argv (parsed value not None) selects its
       loader; other loaders are bypassed. Flags from two different loaders
       in one invocation → error naming both (genuine ambiguity).
    2. No loader flag → the sole `defaultable` loader runs (e.g. aidlc
       autodetects the current unit). Multiple defaultables → error.
    3. None defaultable → None: run with no injected docs; the subject is
       the pipeline's `name:`.

    Convention: loader flags must default to None so "present" is decidable.
    """
    invoked = {loader_name for dest, loader_name in registry.cli_dests.items()
               if getattr(args, dest, None) is not None}
    if len(invoked) > 1:
        raise ValueError(
            f"Flags from multiple document loaders in one invocation: "
            f"{sorted(invoked)}")
    if invoked:
        name = invoked.pop()
        return next(l for l in registry.document_loaders if l.name == name)
    defaultable = [l for l in registry.document_loaders if l.defaultable]
    if len(defaultable) > 1:
        raise ValueError(
            f"Multiple defaultable document loaders: "
            f"{[l.name for l in defaultable]}")
    return defaultable[0] if defaultable else None

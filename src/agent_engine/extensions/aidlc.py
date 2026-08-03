"""AI-DLC document-loader extension. Loading IS choosing: name
`agent_engine.extensions.aidlc:AidlcExtension` in the pipeline's
`extensions:` list and the pipeline gains `--ai-dlc-unit U<N>` plus bare-run
autodetect of the current unit from `aidlc-docs/aidlc-state.md`.

Resolvers are verbatim ports of yosk's `resolve_unit_docs` /
`get_current_unit`, with `docs_dir` parameterised (was the module-level
AIDLC_DOCS_DIR) and the coding-standards merge dropped (the pipeline's
`additional_files:` now owns shared files).
"""

import argparse
import re
from pathlib import Path

_DOC_SUFFIXES = (".md", ".yaml", ".yml", ".txt")


def resolve_unit_docs(docs_dir: Path | str, unit_id: str) -> dict[str, str]:
    docs: dict[str, str] = {}
    docs_dir = Path(docs_dir)
    unit_id = unit_id.strip()
    if unit_id[:1] in ("U", "u"):
        unit_id = unit_id[1:]

    unit_patterns = [f"unit-{unit_id}", f"unit_{unit_id}"]
    construction_dir = docs_dir / "construction"
    unit_dir = None
    if construction_dir.is_dir():
        for entry in sorted(construction_dir.iterdir()):
            if not entry.is_dir():
                continue
            if any(entry.name.lower() == p.lower() for p in unit_patterns):
                unit_dir = entry
                for file in sorted(entry.rglob("*")):
                    if file.is_file() and file.suffix in _DOC_SUFFIXES:
                        key = str(file.relative_to(entry))
                        docs[key] = file.read_text()

    if unit_dir is None:
        raise FileNotFoundError(
            f"No docs directory found for unit {unit_id} under {construction_dir} "
            f"(looked for {', '.join(unit_patterns)})")

    # At this point docs holds only unit-dir files — an empty load means the
    # pipeline would build context from inception docs alone (the 2026-07-19
    # U3 silent-degradation bug). Fail fast instead.
    if not any(not k.startswith("inception/") for k in docs):
        raise RuntimeError(
            f"Unit dir {unit_dir} matched but yielded no docs — "
            "refusing to build context from inception docs alone")

    # Namespaced keys so an inception doc can never silently overwrite a
    # unit doc with the same filename.
    inception = docs_dir / "inception" / "application-design"
    if inception.is_dir():
        for file in sorted(inception.iterdir()):
            if file.is_file() and file.suffix in (".md", ".txt"):
                docs[f"inception/{file.name}"] = file.read_text()

    # The unit's code-generation plans are the build spec — absent is fine,
    # present is how the spec reaches agents.
    plans_dir = docs_dir / "construction" / "plans"
    if plans_dir.is_dir():
        for file in sorted(plans_dir.glob(f"unit-{unit_id}-*-code-generation-plan.md")):
            docs[f"plans/{file.name}"] = file.read_text()

    return docs


def get_current_unit(docs_dir: Path | str) -> str:
    """Read the current unit from the aidlc-state.md Current Stage line."""
    state_file = Path(docs_dir) / "aidlc-state.md"
    if not state_file.is_file():
        raise FileNotFoundError(f"aidlc-state file not found: {state_file}")
    # Anchor to the Current Stage line — the file accumulates history, so an
    # unanchored search could silently pick up an earlier "Unit N" mention.
    match = re.search(r"Current Stage[^\n]*Unit (\d+)", state_file.read_text())
    if not match:
        raise RuntimeError(
            f"Could not determine current unit from {state_file} "
            "(no 'Unit N' in the Current Stage line)")
    return f"U{match.group(1)}"


def _normalize_unit(unit: str) -> str:
    unit = unit.strip()
    if unit[:1] in ("U", "u"):
        unit = unit[1:]
    return f"U{unit}"


class AidlcDocumentLoader:
    """`--ai-dlc-unit U<N>`, or bare-run autodetect from aidlc-state.md."""

    name = "ai-dlc"
    defaultable = True

    def __init__(self, docs_dir: Path | str = "aidlc-docs"):
        self.docs_dir = Path(docs_dir)

    def add_cli_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--ai-dlc-unit", metavar="U<N>", default=None,
                            help="AI-DLC unit ID (e.g. U2); defaults to the "
                                 "current unit in aidlc-docs/aidlc-state.md")

    def resolve(self, args: argparse.Namespace) -> tuple[dict[str, str], str]:
        unit = (_normalize_unit(args.ai_dlc_unit) if args.ai_dlc_unit
                else get_current_unit(self.docs_dir))
        return resolve_unit_docs(self.docs_dir, unit), f"unit {unit}"


class AidlcExtension:
    name = "ai-dlc"

    def register(self, registry) -> None:
        registry.add_document_loader(AidlcDocumentLoader())

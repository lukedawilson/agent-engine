"""AI-DLC document-loader extension. Loading IS choosing: name
`agent_engine.extensions.aidlc:AidlcExtension` in the pipeline's
`extensions:` list and the pipeline gains `--ai-dlc-unit` (any
unambiguous unit spelling: U4 / 4 / 004 / U004 / full slug) plus bare-run
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
_UNIT_DIR_NUMBER = re.compile(r"unit[-_](\d+)")


def _leading_number(text: str) -> int | None:
    """Leading digits of a unit id (``"004-preset-management"`` -> 4), or
    None for ids that do not start with a number."""
    match = re.match(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _dir_unit_number(dir_name: str) -> int | None:
    """Numeric prefix of a unit dir name (``"unit-004-preset-management"``
    -> 4, ``"unit-14"`` -> 14)."""
    match = _UNIT_DIR_NUMBER.match(dir_name.lower())
    return int(match.group(1)) if match else None


def resolve_unit_docs(docs_dir: Path | str, unit_id: str) -> dict[str, str]:
    docs: dict[str, str] = {}
    docs_dir = Path(docs_dir)
    unit_id = unit_id.strip()
    if unit_id[:1] in ("U", "u"):
        unit_id = unit_id[1:]

    unit_patterns = [f"unit-{unit_id}", f"unit_{unit_id}"]
    number = _leading_number(unit_id)
    construction_dir = docs_dir / "construction"
    candidates: list[Path] = []
    if construction_dir.is_dir():
        for entry in sorted(construction_dir.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name.lower()
            if name == unit_patterns[0].lower() or name == unit_patterns[1].lower():
                candidates.append(entry)
            elif number is not None and _dir_unit_number(entry.name) == number:
                candidates.append(entry)

    candidates = sorted(set(candidates), key=lambda p: p.name.lower())
    if len(candidates) > 1:
        raise RuntimeError(
            f"Ambiguous unit id '{unit_id}': multiple unit directories match "
            f"({', '.join(p.name for p in candidates)}). Pass the full unit "
            "slug to disambiguate.")

    unit_dir = candidates[0] if candidates else None
    if unit_dir is None:
        look_for = ", ".join(unit_patterns)
        if number is not None:
            look_for += f", or any unit dir numbered {number}"
        raise FileNotFoundError(
            f"No docs directory found for unit {unit_id} under {construction_dir} "
            f"(looked for {look_for})")

    for file in sorted(unit_dir.rglob("*")):
        if file.is_file() and file.suffix in _DOC_SUFFIXES:
            key = str(file.relative_to(unit_dir))
            docs[key] = file.read_text()

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
    """`--ai-dlc-unit` (any unambiguous spelling), or bare-run
    autodetect from aidlc-state.md."""

    name = "ai-dlc"
    defaultable = True

    def __init__(self, docs_dir: Path | str = "aidlc-docs"):
        self.docs_dir = Path(docs_dir)

    def add_cli_args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--ai-dlc-unit", metavar="U<N>", default=None,
                        help="AI-DLC unit ID: any unambiguous spelling "
                             "(U4, 4, 004, U004) or the full unit slug "
                             "(U004-preset-management); defaults to the "
                             "current unit in aidlc-docs/aidlc-state.md")

    def resolve(self, args: argparse.Namespace) -> tuple[dict[str, str], str]:
        unit = (_normalize_unit(args.ai_dlc_unit) if args.ai_dlc_unit
                else get_current_unit(self.docs_dir))
        return resolve_unit_docs(self.docs_dir, unit), f"unit {unit}"


class AidlcExtension:
    name = "ai-dlc"

    def register(self, registry) -> None:
        registry.add_document_loader(AidlcDocumentLoader())

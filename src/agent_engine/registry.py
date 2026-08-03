"""Extension registry — the seam between core and consumer/bundled extensions.

Core pre-registers the built-ins (actions `kill_listeners`/`commit`, document
loader `plan`); everything else arrives via `load_extensions` from the
pipeline's `extensions:` list — `module:Class` strings, explicit only, no
auto-discovery.
"""

import argparse
import importlib
from collections.abc import Callable
from typing import Protocol


class DocumentLoader(Protocol):
    """Supplies the pipeline's doc bundle + subject. Selected by its CLI
    flag at invocation; `defaultable` loaders may also run with no flag."""

    name: str
    defaultable: bool

    def add_cli_args(self, parser: argparse.ArgumentParser) -> None: ...

    def resolve(self, args: argparse.Namespace) -> tuple[dict[str, str], str]:
        """Return (docs, subject). Empty docs fail fast at the call site."""
        ...


class Extension(Protocol):
    name: str

    def register(self, registry: "Registry") -> None: ...


def _contributed_options(loader: DocumentLoader) -> list[tuple[str, str]]:
    """The (option string, dest) pairs a loader would add — probed with a
    throwaway parser so collisions are caught at load time, not parse time,
    and the selection flow can map parsed args back to their loader."""
    probe = argparse.ArgumentParser(add_help=False)
    loader.add_cli_args(probe)
    return [(opt, action.dest) for action in probe._actions
            for opt in action.option_strings]


class Registry:
    def __init__(self) -> None:
        self.actions: dict[str, Callable] = {}
        self.document_loaders: list[DocumentLoader] = []
        self.cli_option_owners: dict[str, str] = {}  # option string -> loader name
        self.cli_dests: dict[str, str] = {}  # argparse dest -> loader name

    def add_action(self, name: str, fn: Callable) -> None:
        """Register a node-shaped action: (state, params) -> state update."""
        if name in self.actions:
            raise ValueError(f"Duplicate action name {name!r}")
        self.actions[name] = fn

    def add_document_loader(self, loader: DocumentLoader) -> None:
        pairs = _contributed_options(loader)
        for opt, _dest in pairs:
            owner = self.cli_option_owners.get(opt)
            if owner is not None:
                raise ValueError(
                    f"CLI option {opt!r} is contributed by both document "
                    f"loader {owner!r} and {loader.name!r}")
        for opt, dest in pairs:
            self.cli_option_owners[opt] = loader.name
            self.cli_dests[dest] = loader.name
        self.document_loaders.append(loader)

    def add_tool(self, name: str, tool: type) -> None:
        """Register an SDK tool class (agent frontmatter names resolve
        against the SDK's global registry)."""
        from openhands.sdk.tool import register_tool
        register_tool(name, tool)


def default_registry() -> Registry:
    """Core built-ins: actions `kill_listeners`/`commit`, document loader
    `plan` (flag `--plan PATH`)."""
    from . import actions as _actions
    from .loaders import PlanDocumentLoader

    reg = Registry()
    reg.add_action("kill_listeners", _actions.kill_listeners)
    reg.add_action("commit", _actions.commit)
    reg.add_document_loader(PlanDocumentLoader())
    return reg


def load_extensions(refs: list[str], registry: Registry) -> None:
    """Import, instantiate, and register each `module:Class` ref. Any failure
    is a loud error naming the ref."""
    for ref in refs:
        module_name, sep, class_name = ref.partition(":")
        if not sep or not module_name or not class_name:
            raise ValueError(
                f"Invalid extension ref {ref!r} — expected 'module:Class'")
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
        except (ImportError, AttributeError) as e:
            raise ValueError(f"Cannot load extension {ref!r}: {e}") from e
        try:
            ext = cls()
        except Exception as e:
            raise ValueError(f"Cannot instantiate extension {ref!r}: {e}") from e
        ext.register(registry)

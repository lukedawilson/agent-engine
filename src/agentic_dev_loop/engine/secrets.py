"""Host-side secret store (unit 019): provider registry, run-start resolution,
the ``.env*`` ban, and output scrubbing.

Secrets are declared in the pipeline yaml as refs only - never values. At run
start the engine resolves every declared ref host-side (``env`` provider
first) and injects each value into a declaring step's exec env only. The
``.env*`` ban keeps secret-bearing files out of the workspace, and the
scrubber keeps resolved values out of every engine-written output path.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol

from agentic_dev_loop.core.config import PipelineConfig, StepConfig

REDACTED = "[REDACTED]"
ENV_FILE_WHITELIST = frozenset({".env.example", ".env.template", ".env.sample"})


class SecretResolutionError(RuntimeError):
    """A loud fail-fast secret failure naming the ref, step(s), and provider."""


class SecretProvider(Protocol):
    """A provider resolves locator keys to values, host-side, once per run."""

    name: str

    def resolve(self, keys: list[str]) -> dict[str, str]:
        """Resolve each locator key; a missing key raises loudly."""
        ...


class EnvProvider:
    """Resolve secrets from host environment variables (the shipped default).
    ``key`` is both the host variable to read and the step env name to inject."""

    name = "env"

    def __init__(self, environ: Mapping[str, str] | None = None):
        self._environ = os.environ if environ is None else environ

    def resolve(self, keys: list[str]) -> dict[str, str]:
        missing = sorted(k for k in keys if k not in self._environ)
        if missing:
            raise SecretResolutionError(
                "environment variable(s) not set: " + ", ".join(missing))
        return {k: self._environ[k] for k in keys}


PROVIDERS: dict[str, SecretProvider] = {"env": EnvProvider()}


def resolve_secrets(cfg: PipelineConfig,
                    environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Resolve every declared ref host-side once (run start). Returns
    ``{ref_name: value}``. An unresolvable ref or unknown provider fails fast,
    naming the ref, the declaring step(s), and the provider error."""
    if environ is not None:
        providers = {"env": EnvProvider(environ)}
    else:
        providers = PROVIDERS
    resolved: dict[str, str] = {}
    for ref, spec in cfg.secrets.items():
        provider = providers.get(spec.from_)
        if provider is None:
            raise SecretResolutionError(
                f"secret ref {ref!r}: unknown provider {spec.from_!r}")
        try:
            resolved[ref] = provider.resolve([spec.key])[spec.key]
        except SecretResolutionError as e:
            steps = [s.name for s in cfg.steps if ref in s.secrets]
            raise SecretResolutionError(
                f"secret ref {ref!r} (provider {spec.from_!r}, key {spec.key!r})"
                f" used by step(s) {steps or ['<none>']}: {e}") from e
    return resolved


def step_secret_env(cfg: PipelineConfig, step: StepConfig,
                    resolved: Mapping[str, str]) -> dict[str, str]:
    """The ``{env_name: value}`` mapping to inject for one step: only the refs
    it declares, keyed by each ref's ``key`` (the env name the step reads)."""
    return {cfg.secrets[ref].key: resolved[ref] for ref in step.secrets}


def redact_values(text: str, values: Iterable[str]) -> str:
    """Replace every resolved secret value in ``text`` with ``[REDACTED]``.
    Longest-first so a value that is a substring of another is fully removed."""
    if not text:
        return text
    secrets = sorted({v for v in values if v}, key=len, reverse=True)
    for value in secrets:
        text = text.replace(value, REDACTED)
    return text


def scan_env_files(workspace: Path | str) -> None:
    """The ``.env*`` ban: any ``.env*`` file at the workspace root - other than
    the convention fixtures (``.env.example`` / ``.env.template`` /
    ``.env.sample``) - fails fast, naming the files and the remedy. Applies
    regardless of ``network:`` flags: the workspace must simply not hold
    secrets."""
    root = Path(workspace)
    hits = sorted(
        p.name for p in root.glob(".env*")
        if p.is_file() and p.name not in ENV_FILE_WHITELIST
    )
    if hits:
        raise SecretResolutionError(
            "secret-bearing file(s) found in the workspace root: "
            + ", ".join(hits)
            + " - move these values into `secrets:` refs / host env and "
            "delete the files (`.env.example`, `.env.template`, `.env.sample` "
            "are allowed fixtures)")

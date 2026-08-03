"""LLM construction from pipeline config. Fail fast on a missing key —
never fall back to another env var (no silent fallbacks)."""

import os

from openhands.sdk import LLM

from .config import LlmConfig


def build_llm(cfg: LlmConfig) -> LLM:
    api_key = os.environ.get(cfg.api_key_env)
    if not api_key:
        raise RuntimeError(f"{cfg.api_key_env} environment variable is required")
    return LLM(
        model=cfg.model,
        api_key=api_key,
        base_url=cfg.base_url,
        timeout=cfg.timeout,  # policy: no LLM timeout unless explicitly set
        extra_body=cfg.extra_body,
    )

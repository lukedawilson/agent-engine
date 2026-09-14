"""LLM construction from pipeline config. Fail fast on a missing key —
never fall back to another env var (no silent fallbacks)."""

import os

from openhands.sdk import LLM
from openhands.sdk.llm.utils import model_features as _model_features

from .config import LlmConfig

# Compat shim: OpenHands SDK 1.17 gates reasoning_content passback on a closed
# model-name list (SEND_REASONING_CONTENT_MODELS) that does not know
# deepseek-v4-pro. DeepSeek's thinking mode 400s on any multi-turn request
# whose history omits prior reasoning_content. Unlike force_string_serializer,
# the SDK exposes no instance-level override, so register the model here.
# Remove once the SDK lists the model or adds an override.
_DEEPSEEK_MODEL = "deepseek-v4-pro"
if _DEEPSEEK_MODEL not in _model_features.SEND_REASONING_CONTENT_MODELS:
    _model_features.SEND_REASONING_CONTENT_MODELS.append(_DEEPSEEK_MODEL)


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

"""build_llm tests. LLM is an SDK network class — mocking it is permitted."""

from unittest.mock import patch

import pytest

from agent_engine.config import LlmConfig
from agent_engine.llm import build_llm

KEY = "AGENT_ENGINE_TEST_KEY"


def _cfg(**kw):
    return LlmConfig(**({"model": "openai/deepseek-v4-pro", "api_key_env": KEY} | kw))


class TestBuildLlm:
    def test_missing_api_key_env_raises_naming_the_var(self, monkeypatch):
        """Fail fast naming the missing var — never fall back to another key."""
        monkeypatch.delenv(KEY, raising=False)
        with pytest.raises(RuntimeError, match=KEY):
            build_llm(_cfg())

    def test_builds_llm_from_config(self, monkeypatch):
        monkeypatch.setenv(KEY, "sk-test")
        with patch("agent_engine.llm.LLM") as mock_cls:
            result = build_llm(_cfg(
                base_url="https://api.deepseek.com",
                extra_body={"chat_template_kwargs": {"thinking": False}}))

        assert result is mock_cls.return_value
        kw = mock_cls.call_args.kwargs
        assert kw["model"] == "openai/deepseek-v4-pro"
        assert kw["api_key"] == "sk-test"
        assert kw["base_url"] == "https://api.deepseek.com"
        assert kw["extra_body"] == {"chat_template_kwargs": {"thinking": False}}
        assert kw["timeout"] is None  # opinionated no-timeout default

    def test_timeout_passed_through_when_set(self, monkeypatch):
        monkeypatch.setenv(KEY, "sk-test")
        with patch("agent_engine.llm.LLM") as mock_cls:
            build_llm(_cfg(timeout=30))

        assert mock_cls.call_args.kwargs["timeout"] == 30

"""Tests for CapturedOutput — the pipeline-captured agent response channel."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from openhands.sdk.event.llm_convertible.message import MessageEvent
from openhands.sdk.llm.message import Message, TextContent

from agent_engine.outputs import CaptureError, CapturedOutput


def _agent_event(text: str) -> MessageEvent:
    return MessageEvent(
        source="agent",
        llm_message=Message(role="assistant", content=[TextContent(type="text", text=text)]),
    )


def _user_event(text: str) -> MessageEvent:
    return MessageEvent(
        source="user",
        llm_message=Message(role="user", content=[TextContent(type="text", text=text)]),
    )


def _conv(*events) -> SimpleNamespace:
    return SimpleNamespace(events=list(events))


class TestFromAgentResult:
    def test_captures_last_agent_message(self, tmp_path: Path):
        conv = _conv(
            _user_event("the task"),
            _agent_event("first thought"),
            _agent_event("final answer"),
        )
        result = CapturedOutput.from_agent_result(conv, "implementation-summary.md", tmp_path)
        assert result.is_ok()
        captured = result.unwrap()
        assert captured.raw_text == "final answer"
        assert captured.artifact_path == tmp_path / "implementation-summary.md"

    def test_ignores_user_and_environment_events(self, tmp_path: Path):
        conv = _conv(_user_event("please do this"), _agent_event("done"))
        result = CapturedOutput.from_agent_result(conv, "out.md", tmp_path)
        assert result.unwrap().raw_text == "done"

    def test_joins_multiple_text_parts(self, tmp_path: Path):
        event = MessageEvent(
            source="agent",
            llm_message=Message(
                role="assistant",
                content=[TextContent(type="text", text="part one\n"), TextContent(type="text", text="part two")],
            ),
        )
        result = CapturedOutput.from_agent_result(_conv(event), "out.md", tmp_path)
        assert result.unwrap().raw_text == "part one\npart two"

    def test_no_events_is_empty_response(self, tmp_path: Path):
        result = CapturedOutput.from_agent_result(_conv(), "out.md", tmp_path)
        assert result.is_err()
        assert result.error == CaptureError.EMPTY_RESPONSE

    def test_no_agent_events_is_empty_response(self, tmp_path: Path):
        result = CapturedOutput.from_agent_result(_conv(_user_event("hi")), "out.md", tmp_path)
        assert result.is_err()
        assert result.error == CaptureError.EMPTY_RESPONSE

    def test_blank_agent_text_is_empty_response(self, tmp_path: Path):
        result = CapturedOutput.from_agent_result(_conv(_agent_event("  \n ")), "out.md", tmp_path)
        assert result.is_err()
        assert result.error == CaptureError.EMPTY_RESPONSE


class TestWrite:
    def test_round_trip(self, tmp_path: Path):
        state_dir = tmp_path / ".pr"
        captured = CapturedOutput(raw_text="hello findings", artifact_path=state_dir / "out.md")
        result = captured.write()
        assert result.is_ok()
        assert (state_dir / "out.md").read_text() == "hello findings"

    def test_creates_missing_parent_dirs(self, tmp_path: Path):
        captured = CapturedOutput(
            raw_text="deep", artifact_path=tmp_path / "a" / "b" / "c" / "out.md"
        )
        assert captured.write().is_ok()
        assert (tmp_path / "a" / "b" / "c" / "out.md").read_text() == "deep"

    def test_full_text_no_truncation(self, tmp_path: Path):
        long_text = "\n".join(f"line {i}" for i in range(500))
        captured = CapturedOutput(raw_text=long_text, artifact_path=tmp_path / "out.md")
        assert captured.write().is_ok()
        assert (tmp_path / "out.md").read_text() == long_text

    def test_io_error_is_typed(self, tmp_path: Path):
        blocker = tmp_path / "blocker"
        blocker.write_text("file where a dir should be")
        captured = CapturedOutput(raw_text="x", artifact_path=blocker / "out.md")
        result = captured.write()
        assert result.is_err()
        assert result.error == CaptureError.IO_ERROR

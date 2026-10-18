"""Captured agent output: value objects that own the response→artifact and
response→verdict channels (unit-1).

The pipeline — not the agent — writes the step's artifact from the agent's
final SDK response. `Verdict.from_text` parses that same text for routing.
Expected conditions are typed `Result` errors, never exceptions.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path

from openhands.sdk.event.llm_convertible.action import ActionEvent
from openhands.sdk.event.llm_convertible.message import MessageEvent
from openhands.sdk.llm.message import content_to_str

from .results import Result

# The OpenHands FinishTool's registered name — the tool whose `message` IS the
# agent's final response (see `_final_agent_text`).
FINISH_TOOL = "finish"

# Leading markdown/list/quote decoration tolerated on a verdict line.
_LEAD_DECOR = "#*_`>- "
# Decoration tolerated between VERDICT and ':' and after the keyword.
_DECOR = "*_`> "
# Caveat delimiters: after one of these, arbitrary prose may follow the
# keyword without the line losing its decision status. '.' doubles as the
# bare sentence terminator.
_CAVEAT = "—–,;:."
# Negators recognized immediately before the keyword.
_NEGATORS = ("NOT", "DOES NOT", "DID NOT")


class CaptureError(enum.Enum):
    EMPTY_RESPONSE = "empty_response"
    IO_ERROR = "io_error"


class VerdictError(enum.Enum):
    NO_VERDICT = "no_verdict"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Verdict:
    """A parsed decision: `value` is the canonical outcome (e.g. 'pass').

    Parsing policy (BR-2): the last decoration-tolerant `VERDICT: X` line
    that carries a *decision* wins; a keyword followed directly by prose is
    discussion, not a decision. Conflicting decisions are never silently
    resolved — they surface as AMBIGUOUS and retry.
    """

    value: str

    @staticmethod
    def from_text(text: str, verdicts: dict[str, str]) -> "Result[Verdict, VerdictError]":
        decisions: set[str] = set()
        saw_verdict_line = False
        for line in text.splitlines():
            is_line, decision = _parse_line(line, verdicts)
            if is_line:
                saw_verdict_line = True
            if decision is not None:
                decisions.add(decision)
        if len(decisions) == 1:
            return Result.ok(Verdict(value=next(iter(decisions))))
        if len(decisions) > 1:
            return Result.err(VerdictError.AMBIGUOUS)
        if saw_verdict_line:
            return Result.err(VerdictError.AMBIGUOUS)
        return Result.err(VerdictError.NO_VERDICT)


def _parse_line(line: str, verdicts: dict[str, str]) -> tuple[bool, str | None]:
    """Parse one line -> (is_verdict_line, decision_or_None).

    Ported verbatim from the pre-unit-1 `verdicts.py` parser; the original
    returned None for both non-verdict lines and verdict lines without a
    decision — the flag now separates those cases for BR-2.5/BR-2.6.
    """
    stripped = line.strip().lstrip(_LEAD_DECOR)
    if not stripped.upper().startswith("VERDICT"):
        return False, None
    rest = stripped[len("VERDICT"):].lstrip(_DECOR)
    if not rest.startswith(":"):
        return True, None
    body = rest[1:].strip()
    negated = False
    for negator in _NEGATORS:
        if body.upper().startswith(negator + " "):
            negated = True
            body = body[len(negator):].strip()
            break
    body = body.lstrip(_DECOR)
    for keyword in sorted(verdicts, key=len, reverse=True):
        if not body.upper().startswith(keyword.upper()):
            continue
        after = body[len(keyword):].strip().lstrip(_DECOR).strip()
        if after.startswith("?"):
            return True, None
        if after.startswith("!"):
            if after[1:].strip():
                return True, None  # bare '!' is emphasis; '!' plus prose is not
        elif after and after[0] not in _CAVEAT and not after.startswith("-"):
            return True, None  # bare prose — discussion, not a decision
        if negated:
            if len(verdicts) == 2:
                other = next(k for k in verdicts if k != keyword)
                return True, verdicts[other]
            return True, None  # negation on a larger set is ambiguous
        return True, verdicts[keyword]
    return True, None


@dataclass(frozen=True)
class CapturedOutput:
    """The agent's final response, captured by the pipeline (FR-1.2)."""

    raw_text: str
    artifact_path: Path

    @staticmethod
    def from_agent_result(
        conv, artifact: str, state_dir: Path
    ) -> "Result[CapturedOutput, CaptureError]":
        text = _final_agent_text(conv)
        if not text.strip():
            return Result.err(CaptureError.EMPTY_RESPONSE)
        return Result.ok(CapturedOutput(raw_text=text, artifact_path=state_dir / artifact))

    def write(self) -> Result[None, CaptureError]:
        """Write the captured response to the step's artifact path (BR-4/BR-5)."""
        try:
            self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
            self.artifact_path.write_text(self.raw_text)
            return Result.ok(None)
        except OSError:
            return Result.err(CaptureError.IO_ERROR)


def _final_agent_text(conv) -> str:
    """Extract the agent's final response from an SDK conversation.

    The OpenHands agent signals completion by calling `FinishTool`; its
    `FinishAction.message` *is* the final response and arrives as an
    `ActionEvent` (tool_name ``"finish"``), never a `MessageEvent`. Read that
    first; fall back to the last agent `MessageEvent` only when the agent
    finished with a plain-text response instead of a finish call.

    Reads `conv.events` — callers must do this BEFORE the conversation is
    closed (the SDK releases the event stream on close).
    """
    events = getattr(conv, "events", [])
    for event in reversed(events):
        if isinstance(event, ActionEvent) and event.tool_name == FINISH_TOOL:
            message = getattr(event.action, "message", None)
            if message and message.strip():
                return message
    agent_events = [
        event
        for event in events
        if isinstance(event, MessageEvent) and event.source == "agent"
    ]
    if not agent_events:
        return ""
    return "".join(content_to_str(agent_events[-1].llm_message.content))

"""Verdict parsing — the shared decision contract (BR-6).

`Verdict.from_text` parses the captured response for routing; expected
conditions are typed `Result` errors, never exceptions. `parse_verdict`
collapses that `Result` to a route string for routing consumers: a clear
decision maps to its canonical value, anything unclear maps to ``retry`` —
totality for arbitrary input (no crash, no silent routing).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from .results import Result

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

RETRY = "retry"


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


def parse_verdict(text: str, verdicts: dict[str, str]) -> str:
    """Route for a verdict artifact: the canonical decision value on a single
    clear decision, else ``retry``. Never raises — unclear verdicts retry."""
    result = Verdict.from_text(text, verdicts)
    if result.is_ok():
        return result.value.value
    return RETRY


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

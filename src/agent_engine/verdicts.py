"""Verdict-line parsing. Policy: the LAST decoration-tolerant `VERDICT: X`
line wins (ported unchanged from yosk — see module docstring history)."""

import re


def parse_verdict(text: str, verdicts: dict[str, str]) -> str | None:
    """Return the verdict from the LAST VERDICT: line — agents may weigh
    outcomes before concluding, so the final mention is the decision.

    Tolerates markdown decoration agents add around a verdict line
    (`**VERDICT: PASS**`, `## VERDICT: PASS`, `- VERDICT: PASS`,
    `VERDICT: **PASS**`) — QA run 004 burned three attempts because only a
    bare line-start match was accepted. A verdict keyword followed directly
    by prose (e.g. "VERDICT: PASS was considered") is still discussion, not
    a decision, and does not match."""
    keys = "|".join(re.escape(k) for k in sorted(verdicts, key=len, reverse=True))
    pattern = re.compile(
        r"^[\s#*_`>\-]*VERDICT:\s*[*_`]*\s*(" + keys + r")(?=[*_`]|[*_`\s]*\.?[*_`\s]*$)",
        re.IGNORECASE)
    result = None
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            result = verdicts[match.group(1).upper()]
    return result

"""Verdict-line parsing. Policy: the LAST decoration-tolerant `VERDICT: X`
line wins (ported unchanged from yosk — see module docstring history).

Since the regex era (QA run 004) the parser also recognizes decisions the
agents phrase with caveats: a keyword followed by prose is a decision when
the prose is introduced by a caveat delimiter (`,`, `.`, `:`, `;`, `—`, `–`,
or `-`) — "VERDICT: APPROVED — pending the divider split" routes as approved.
A keyword followed directly by prose ("VERDICT: PASS was considered") is
still discussion, not a decision. `NOT`/`DOES NOT`/`DID NOT` before the
keyword inverts it on two-key verdict sets; on larger sets negation is
ambiguous and yields no verdict."""

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


def parse_verdict(text: str, verdicts: dict[str, str]) -> str | None:
    """Return the verdict from the LAST VERDICT: line — agents may weigh
    outcomes before concluding, so the final mention is the decision.

    Tolerates markdown decoration agents add around a verdict line
    (`**VERDICT: PASS**`, `## VERDICT: PASS`, `- VERDICT: PASS`,
    `VERDICT: **PASS**`, `**VERDICT**: PASS`) — QA run 004 burned three
    attempts because only a bare line-start match was accepted. A verdict
    keyword followed directly by prose (e.g. "VERDICT: PASS was considered")
    is still discussion, not a decision, and does not match."""
    result = None
    for line in text.splitlines():
        decision = _parse_line(line, verdicts)
        if decision is not None:
            result = decision
    return result


def _parse_line(line: str, verdicts: dict[str, str]) -> str | None:
    """Parse one verdict line, or return None when it carries no decision."""
    stripped = line.strip().lstrip(_LEAD_DECOR)
    if not stripped.upper().startswith("VERDICT"):
        return None
    rest = stripped[len("VERDICT"):].lstrip(_DECOR)
    if not rest.startswith(":"):
        return None
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
            return None
        if after.startswith("!"):
            if after[1:].strip():
                return None  # bare '!' is emphasis; '!' plus prose is not
        elif after and after[0] not in _CAVEAT and not after.startswith("-"):
            return None  # bare prose — discussion, not a decision
        if negated:
            if len(verdicts) == 2:
                other = next(k for k in verdicts if k != keyword)
                return verdicts[other]
            return None  # negation on a larger set is ambiguous
        return verdicts[keyword]
    return None

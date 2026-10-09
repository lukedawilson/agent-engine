"""Verdict parsing tests — ported verbatim from yosk's TestVerdictParsing,
with the yosk-specific constants inlined as the config-supplied mappings a
consumer's `verdicts:` block produces (keyword -> canonical outcome)."""

from agent_engine.verdicts import parse_verdict

REVIEW_VERDICTS = {"APPROVED": "approved", "NEEDS CHANGES": "needs_changes"}
TEST_VERDICTS = {"PASS": "pass", "FAIL": "fail"}


class TestVerdictParsing:
    def test_parse_approved(self):
        assert parse_verdict("VERDICT: APPROVED\nAll looks good.", REVIEW_VERDICTS) == "approved"

    def test_parse_needs_changes(self):
        assert parse_verdict("VERDICT: NEEDS CHANGES\nFile X needs work.", REVIEW_VERDICTS) == "needs_changes"

    def test_parse_case_insensitive(self):
        assert parse_verdict("verdict: approved", REVIEW_VERDICTS) == "approved"
        assert parse_verdict("VERDICT: needs changes", REVIEW_VERDICTS) == "needs_changes"

    def test_parse_unknown_returns_none(self):
        assert parse_verdict("Verdict: MAYBE", REVIEW_VERDICTS) is None
        assert parse_verdict("No verdict here", REVIEW_VERDICTS) is None

    def test_parse_verdict_on_own_line(self):
        text = "preamble.\nVERDICT: APPROVED\ntrailing."
        assert parse_verdict(text, REVIEW_VERDICTS) == "approved"

    def test_last_match_wins(self):
        """Agents weigh outcomes before concluding; the final VERDICT line is
        the decision, not the first mention."""
        text = ("VERDICT: NEEDS CHANGES was considered.\n"
                "But after re-checking, all standards are met.\n"
                "VERDICT: APPROVED\n")
        assert parse_verdict(text, REVIEW_VERDICTS) == "approved"

    def test_test_parse_pass(self):
        assert parse_verdict("VERDICT: PASS", TEST_VERDICTS) == "pass"

    def test_test_parse_fail(self):
        assert parse_verdict("VERDICT: FAIL\n3 tests failed.", TEST_VERDICTS) == "fail"

    def test_test_parse_missing_returns_none(self):
        assert parse_verdict("No verdict", TEST_VERDICTS) is None
        assert parse_verdict("", TEST_VERDICTS) is None

    def test_test_parse_case_insensitive(self):
        assert parse_verdict("verdict: pass", TEST_VERDICTS) == "pass"
        assert parse_verdict("VERDICT: fail", TEST_VERDICTS) == "fail"

    def test_test_last_match_wins(self):
        text = "VERDICT: FAIL initially.\nFixed the issues.\nVERDICT: PASS\n"
        assert parse_verdict(text, TEST_VERDICTS) == "pass"

    def test_test_parse_bold_verdict_with_prose(self):
        """QA run 004 attempts 1-2: test agent styled its verdict as bold
        with trailing prose — must still parse."""
        text = ("# CI Fix Report\n\n## Summary\n\n"
                "**VERDICT: PASS** — All 10/10 conformance checks pass after "
                "fixing code duplication in test files.\n")
        assert parse_verdict(text, TEST_VERDICTS) == "pass"

    def test_test_parse_heading_verdict(self):
        """QA run 004 attempt 5: test agent styled its verdict as a
        markdown heading — must still parse."""
        assert parse_verdict("## VERDICT: PASS", TEST_VERDICTS) == "pass"
        assert parse_verdict("### VERDICT: FAIL", TEST_VERDICTS) == "fail"

    def test_review_parse_bold_verdict(self):
        assert parse_verdict("**VERDICT: NEEDS CHANGES**", REVIEW_VERDICTS) == "needs_changes"
        assert parse_verdict("**VERDICT: APPROVED**", REVIEW_VERDICTS) == "approved"

    def test_test_parse_bold_value(self):
        assert parse_verdict("VERDICT: **PASS**", TEST_VERDICTS) == "pass"

    def test_parse_bullet_or_blockquote_verdict(self):
        assert parse_verdict("- VERDICT: PASS", TEST_VERDICTS) == "pass"
        assert parse_verdict("> VERDICT: FAIL", TEST_VERDICTS) == "fail"

    def test_parse_decorated_prose_still_rejected(self):
        """Decoration tolerance must not turn verdict-*discussion* into a
        verdict: a bare verdict keyword followed by prose is not a decision,
        and last-match-wins still applies over decorated mentions."""
        text = "VERDICT: PASS was briefly considered.\n**VERDICT: FAIL**\n"
        assert parse_verdict(text, TEST_VERDICTS) == "fail"

    def test_parse_verdict_tolerates_trailing_period(self):
        """A trailing full stop is sentence punctuation, not prose — agents
        emit `VERDICT: PASS.` constantly and it must not read as unclear."""
        assert parse_verdict("VERDICT: PASS.", TEST_VERDICTS) == "pass"
        assert parse_verdict("VERDICT: FAIL.", TEST_VERDICTS) == "fail"
        assert parse_verdict("VERDICT: NEEDS CHANGES.", REVIEW_VERDICTS) == "needs_changes"

    def test_parse_verdict_period_then_prose_is_caveat(self):
        """A period introducing more prose reads as a decision with caveats,
        not as discussion."""
        assert parse_verdict("VERDICT: PASS. More discussion.", TEST_VERDICTS) == "pass"
        assert parse_verdict("VERDICT: NEEDS CHANGES. See the notes.", REVIEW_VERDICTS) == "needs_changes"

    def test_caveat_prose_after_em_dash(self):
        assert parse_verdict("VERDICT: APPROVED — pending the divider split",
                             REVIEW_VERDICTS) == "approved"
        assert parse_verdict("VERDICT: NEEDS CHANGES — see issues below",
                             REVIEW_VERDICTS) == "needs_changes"
        assert parse_verdict("VERDICT: FAIL — 3 tests broke", TEST_VERDICTS) == "fail"

    def test_caveat_prose_after_comma(self):
        assert parse_verdict("VERDICT: APPROVED, but fix the README bullet",
                             REVIEW_VERDICTS) == "approved"
        assert parse_verdict("VERDICT: PASS, with lint nits noted", TEST_VERDICTS) == "pass"

    def test_caveat_prose_after_semicolon_or_colon(self):
        assert parse_verdict("VERDICT: APPROVED; see notes", REVIEW_VERDICTS) == "approved"
        assert parse_verdict("VERDICT: NEEDS CHANGES: see issues below",
                             REVIEW_VERDICTS) == "needs_changes"

    def test_caveat_prose_after_hyphen(self):
        assert parse_verdict("VERDICT: APPROVED - pending", REVIEW_VERDICTS) == "approved"

    def test_decoration_between_verdict_and_colon(self):
        assert parse_verdict("**VERDICT**: APPROVED", REVIEW_VERDICTS) == "approved"
        assert parse_verdict("VERDICT : APPROVED", REVIEW_VERDICTS) == "approved"

    def test_bare_prose_still_rejected(self):
        """No delimiter before the prose means discussion, not a decision."""
        assert parse_verdict("VERDICT: PASS was considered", TEST_VERDICTS) is None
        assert parse_verdict("VERDICT: APPROVED with nits", REVIEW_VERDICTS) is None

    def test_question_mark_rejected(self):
        assert parse_verdict("VERDICT: APPROVED?", REVIEW_VERDICTS) is None

    def test_bang_alone_allowed_but_not_with_prose(self):
        assert parse_verdict("VERDICT: FAIL!", TEST_VERDICTS) == "fail"
        assert parse_verdict("VERDICT: FAIL! The build broke.", TEST_VERDICTS) is None

    def test_not_keyword_inverts_on_two_key_sets(self):
        assert parse_verdict("VERDICT: NOT APPROVED", REVIEW_VERDICTS) == "needs_changes"
        assert parse_verdict("VERDICT: NOT NEEDS CHANGES", REVIEW_VERDICTS) == "approved"
        assert parse_verdict("VERDICT: NOT PASS", TEST_VERDICTS) == "fail"

    def test_not_keyword_with_decoration_prose_and_tenses(self):
        assert parse_verdict("VERDICT: NOT **APPROVED**", REVIEW_VERDICTS) == "needs_changes"
        assert parse_verdict("VERDICT: NOT APPROVED — pending the divider split",
                             REVIEW_VERDICTS) == "needs_changes"
        assert parse_verdict("VERDICT: DID NOT PASS", TEST_VERDICTS) == "fail"
        assert parse_verdict("VERDICT: DOES NOT PASS", TEST_VERDICTS) == "fail"

    def test_negated_discussion_still_rejected(self):
        assert parse_verdict("VERDICT: NOT PASS was considered", TEST_VERDICTS) is None

    def test_negation_ambiguous_on_multi_key_sets(self):
        many = {"A": "a", "B": "b", "C": "c"}
        assert parse_verdict("VERDICT: NOT A", many) is None

    def test_not_unknown_keyword_rejected(self):
        assert parse_verdict("VERDICT: NOT MAYBE", REVIEW_VERDICTS) is None

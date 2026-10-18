# Business Rules — unit-1 (output-passing fix)

## BR-1: Capture is the only feedback channel for produces:/artifact:

The pipeline writes the artifact; agents do not. If an agent writes the same path itself (via terminal), the pipeline write happens last and wins. This is intentional — the captured response is authoritative.

## BR-2: Verdict extraction rules

| Rule | Detail |
| --- | --- |
| BR-2.1 | Only `VERDICT:`-prefixed lines participate in parsing |
| BR-2.2 | Markdown decoration tolerated (`**VERDICT: PASS**`, `_VERDICT: FAIL_`) |
| BR-2.3 | Last occurrence wins among **consistent** keys |
| BR-2.4 | Conflicting keys in a 2-key verdict set (`PASS`/`FAIL`, `APPROVED`/`NEEDS_CHANGES`) → AMBIGUOUS, never silently resolved |
| BR-2.5 | No `VERDICT:` line → NO_VERDICT |
| BR-2.6 | NO_VERDICT and AMBIGUOUS are typed `Result` error codes — never raised exceptions |

## BR-3: Attempt semantics

- Empty final response or agent error → attempt failure (FD-4).
- NO_VERDICT / AMBIGUOUS → existing unclear-verdict retry: attempt-bounded, never silently routable.
- Retry note includes the reason (empty response / no verdict / ambiguous verdict).

## BR-4: Truncation

- Verdict channel: verdict-first truncation (verdict line + its context preserved at the head of the truncated text).
- Summary artifact: full response, untruncated, written to `state_dir`.
- `build_context`: truncates each artifact to its existing budget — behavior unchanged.

## BR-5: Artifact hygiene (unchanged policy, now pipeline-owned)

- Artifacts deleted at every attempt start (stale-artifact hygiene).
- Pipeline writes the fresh artifact at step completion.
- No artifact is ever parsed from a previous attempt.

## BR-6: Schema stability

- Pipeline YAML unchanged: no new keys, no renamed keys.
- `file_editor` removed from dev/review `tools:` lists only — YAML steps untouched.
- Existing pipelines get capture implicitly (always-on, no opt-out).

## BR-7: Compatibility

- Verdict semantics preserved from the existing parser (bug fixes in the AMBIGUOUS path only).
- Historical fixture behaviors must all still hold: markdown-decorated verdicts, verdict-first truncation, unclear-verdict retry, stale-artifact hygiene.

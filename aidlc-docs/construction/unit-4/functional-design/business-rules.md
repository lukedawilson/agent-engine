# Unit 4 Functional Design — Business Rules

| Rule | Detail |
| --- | --- |
| **BR-1** | **Build-time parse** — pipeline.yaml is parsed at workflow creation; generated JS is self-contained (step data + prompt refs + routing baked). Runtime never parses; a running workflow is unaffected by mid-run pipeline edits; changing the pipeline means rebuilding the workflow. (FR-4.3, Q3 reversal) |
| **BR-2** | **Module boundary contract** — `core` = pipeline model + parse + projection (pydantic/PyYAML only); `engine` = graph/stages/sandbox/CLI (heavy deps); `viz` = stdlib-only server + event model. A guard test fails if `core` imports `engine`/`viz` or heavy deps. (FR-4.1) |
| **BR-3** | **No Docker in workflow mode** — workflow steps run in Claude Code's own environment under its permission model; the engine sandbox is never invoked. Docker sandboxing remains engine-mode-only. (FR-4.2) |
| **BR-4** | **Prompt existence fail-fast** — the build step verifies every agent step's `.agent.md` exists; a missing prompt fails the build loudly, naming the file. Never silently generates a broken workflow. (FD-1) |
| **BR-5** | **Prompts referenced, not embedded** — the generated JS carries the prompt path; the subagent re-reads `.agent.md` from the workspace at spawn, so prompt edits by earlier steps take effect within a run. (FD-1) |
| **BR-6** | **Verdict contract identical both modes** — verdict agents still write the `VERDICT: PASS/FAIL` artifact; subagent steps report their verdict in final output; the JS routes exactly as the engine does. (FR-4.5, Q7) |
| **BR-7** | **Bounded retries with retry note** — the JS keeps its own attempt counter in workflow state; on `goto`, the failing subagent's final output is injected into the next dev attempt as the retry note (engine `notes`-channel equivalent). Exceeding `max_attempts` fails the workflow loudly. (FD-2) |
| **BR-8** | **Commit gating preserved** — the first workflow step captures clean-at-start (empty `git status --porcelain`) before any subagent work; the docker-free commit shim refuses loudly when not allowed and uses the trusted hooksPath + templated message. (FD-3, Q4, FR-4.6) |
| **BR-9** | **Viz ingest token-auth** — the viz server generates an ingest token at launch (workflow state); step subagents POST stage events with that token; the read-only SSE view is tokenless; server binds localhost. (FD-4, FR-4.7) |
| **BR-10** | **Skill distribution** — SKILL.md + workflow JS template + docs ship in the PyPI wheel; `agentic-dev-loop install-skill` installs to `~/.claude/skills/agentic-dev-loop/`; the generated JS header records the `core` version + pipeline hash. (FD-5) |
| **BR-11** | **Engine-only fields ignored in workflow mode** — `isolation:`, per-step `network:`, and `setup:` have no effect in workflow mode and never crash the build or run; semantics documented in the skill docs. (FR-4.9) |
| **BR-12** | **One pipeline.yaml, both modes** — the same file drives engine mode (sandboxed) and workflow mode (Claude Code env); trust model per mode is documented. (FR-4.9) |
| **BR-13** | **No MCP layer** — subagents reach `core`/`viz` via shell/python directly; the earlier ae_* MCP-tool design is dropped. (FR-4.8) |

## Security-baseline mapping

| Rule | Disposition | Where |
| --- | --- | --- |
| SECURITY-01 (secret scanning) | N/A | Workflow mode adds no new secret storage; pipeline.yaml credential handling unchanged |
| SECURITY-02 (secure defaults for exposed services) | Enforced | BR-9: viz binds localhost, ingest token-authenticated |
| SECURITY-03 (least privilege) | Enforced | BR-2/BR-3: workflow steps confined to Claude Code's permission model; engine sandbox untouched |
| SECURITY-04 (dependency pinning) | N/A | No new runtime deps for core/viz (stdlib-light) |
| SECURITY-05 (input validation) | Enforced | BR-1/BR-4: build-time validation + prompt existence fail-fast |
| SECURITY-06 (credential hygiene) | Enforced | BR-8: trusted hooksPath; no credentials enter workflow state beyond what CC already holds |
| SECURITY-07 (audit trail) | Enforced | Generated JS version + pipeline hash header; workflow state records step outcomes |
| SECURITY-08 (network segmentation) | N/A | Engine sandbox unchanged; workflow mode is explicitly CC-environment |
| SECURITY-09 (supply chain) | Enforced | BR-10: skill ships in the signed PyPI wheel; JS header records core version |
| SECURITY-10 (fail closed) | Enforced | BR-4/BR-8: missing prompts and un-gated commits fail loudly |
| SECURITY-11 (defense in depth) | Enforced | BR-2 guard test keeps boundary honest; BR-8 gates the only mutation point |
| SECURITY-12 (least data exposure) | Enforced | BR-9: SSE read-only view tokenless; ingest requires token |
| SECURITY-13 (secure by default) | Enforced | BR-3: no sandbox escape path introduced; BR-11: unknown fields ignored safely |
| SECURITY-14 (secrets in logs) | N/A | No new logging surface in this unit |
| SECURITY-15 (documented threat model) | Enforced | Trust-model change (CC env instead of sandbox) documented in skill docs per FR-4.9 |

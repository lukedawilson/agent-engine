# Unit 4 Intent (draft) — Claude Code as a second agent backend

**Status**: INTENT ONLY — draft, not started. Written 2026-10-18 from an
exploratory discussion. No code written, no AI-DLC workflow started, no
decisions committed. Revisit before proceeding.

## Intent

Plug Claude Code into agent-engine as an alternative agent-execution backend
alongside OpenHands, for users on a Pro/Enterprise (subscription) plan where
an Anthropic API key isn't available. Desired metering: usage counts against
the same limits as interactive use (TUI / web / desktop), not separate API
billing.

## Relationship to existing units

The current AI-DLC intent (units 1–3) is guardrails & sandboxing:

- unit-1 — output-passing fix (capture, don't trust agent file-writes)
- unit-2 — SDK-level hardening
- unit-3 — kernel-level isolation (opt-in) — NOT STARTED

This is a **separate** concern: a second agent backend. It *interacts* with
unit-3's isolation design (see below) but is not part of it.

## Findings (exploratory; live-sourced, not training data)

### 1. Billing / auth landscape — the headline risk

Metering is **auth-driven, not client-driven**. Per current docs
([support.claude.com/15036540](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan),
[17154008](https://support.claude.com/en/articles/17154008)):

- **Pro**: no API key path. Sign in (OAuth) → SDK/`claude -p` draws from plan
  limits (shared with web/desktop/TUI). Pro gets **no** API credits.
- **Max / Team**: since Oct 7 2026, include monthly API credits (Max 5x $100,
  Max 20x $200, Team pooled ≤$500) claimed into a Claude Console org, spent
  via an **API key**.
- **Enterprise**: not eligible for those credits; separate sales/invoiced
  contract.
- Setting `ANTHROPIC_API_KEY` forces API billing even on a subscription —
  the #1 footgun for this intent.

**Durability risk**: unattended/automated usage is exactly what Anthropic has
been trying to pull off subscriptions. Boris Cherny (Apr 2026): "our
subscriptions weren't built for the usage patterns of these third-party
tools." May 2026 → move SDK/`claude -p` to API-rate billing; Jun 15 2026 →
paused ("nothing has changed"); Oct 7 2026 → credits for Max/Team. "Same
limits as TUI" holds today; it is policy, not contract.

### 2. What the SDK actually is

- **Python SDK** (`claude-agent-sdk`, PyPI 0.2.168, "Alpha") is a **thin
  wrapper** that bundles/spawns the Claude Code CLI (Node) as a subprocess
  (`_internal/transport/subprocess_cli.py`). Agent-loop/tool logic lives in
  the CLI.
- **TS SDK** (`@anthropic-ai/claude-agent-sdk`, 0.3.x) ships per-platform
  **native binaries** and peer-depends on `@anthropic-ai/sdk` — the official
  Anthropic API client.
- Both ultimately make HTTPS calls to `api.anthropic.com` (the Messages API
  host). "No API key" ≠ "not hitting the API" — it's the same backend,
  metered differently by auth.

### 3. Efficiency: avoiding a process per message

- One-shot `query()` is stateless (process per call). **`ClaudeSDKClient`** is
  stateful: one `connect()` (one subprocess), many messages, context kept.
- **Session resume/store**: `resume` / `continue` / `session_id`,
  `InMemorySessionStore`, `import_session_to_store` — a retry can resume a
  prior session (system prompt built once, reused) instead of cold-starting.
  Maps to the engine's `thread_id`/checkpoint model.
- **In-process tools** (`@tool` / SDK MCP servers) and **hooks** (e.g.
  `PreToolUse` deny) run in-process — no subprocess per tool call; hooks give
  harder enforcement of "never `git commit`" than prompt text.
- **TS-side** `prewarm()`/`SpareProcess.claim()` (process pooling); Python
  parity unverified.
- **Irreducible floor**: Python SDK still = one CLI subprocess per session.
  Zero-subprocess ⇒ TS native binary or raw Messages API (the latter forfeits
  subscription metering).

### 4. Reverse-engineering the web app — rejected

Technically possible (undocumented `claude.ai/api/...` endpoints), but:
violates Anthropic ToS/usage policy → account termination risk (loses the
very subscription this depends on); fragile/undocumented (the repo's own
Framer lesson); and redundant — the sanctioned OAuth headless path already
delivers TUI-equivalent metering. Do not pursue.

### 5. Kernel isolation interaction

unit-3 (`requirements.md` FR-2.1) splits the agent into trust classes:
LLM calls host-side (trusted); `terminal` tool + command steps sandboxed.
OpenHands keeps these separable. **Claude Code collapses them** — model loop
and Bash/Write tool execution live in the same process being sandboxed.

Two fits:

- **A. Containerize the whole Claude Code session** (reuse the engine's
  `Sandbox`, FR-2.2). Boundary then also contains LLM egress + credentials
  (`.claude/`, key) and sandboxes Read/Write too (stronger). Network-egress
  policy becomes load-bearing.
- **B. Claude Code's native sandbox** (`SandboxSettings` /
  `SandboxNetworkConfig` in `ClaudeAgentOptions`). No container, but a second
  mechanism not unified with the engine's `Sandbox`.

**DDD consequence**: the design forbids a `Sandbox` protocol ("single-impl
interfaces forbidden; extract only when a second backend lands"). A Claude
backend *is* that second backend — for the **agent runner** (`run_agent`,
hardcoded to OpenHands `Conversation` today) and for **isolation**. Sequence
the extraction once, against a real second backend, not speculatively.

**Stays clean**: `command` steps are backend-agnostic and route through
`Sandbox.run` regardless; FR-2.3 fail-fast, NFR-3 least-privilege, host-side
commit all carry over.

## Open questions (revisit later)

1. Metering durability: how long does signed-in headless use stay on plan
   limits? Treat as fragile, not guaranteed.
2. Isolation fit: A (containerize session) vs B (native CC sandbox) vs both —
   decide in unit-3 FD, not now.
3. Python SDK parity: `prewarm`/spare-process, resume-across-session-store
   behavior — needs a Phase-5 spike before committing.
4. Capacity: plan limits (5-hr session + weekly) are human-sized, not
   pipeline-sized — an agent-engine run may exhaust them in one go.
5. Agent-definition mapping: `.agent.md` → Claude system prompt (inline body
   or `append`); verdict protocol (`VERDICT:` line in final response) should
   carry over unchanged.

## Sources

- https://github.com/anthropics/claude-agent-sdk-python (repo + README)
- https://pypi.org/pypi/claude-agent-sdk (0.2.168, Alpha)
- https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
- https://support.claude.com/en/articles/17154008 (monthly API credits)
- https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan
- https://news.ycombinator.com/item?id=45644862 (Ask HN: production-ready? No)
- https://news.ycombinator.com/item?id=49997654 (Oct 7 credits change)
- https://arstechnica.com/ai/2026/06/anthropic-pauses-token-based-billing-for-its-claude-agent-sdk/
- Repo-internal: `aidlc-docs/inception/requirements/requirements.md`,
  `application-design.md`, `unit-of-work.md`

# NFR Requirements Plan - unit-2 (SDK-level hardening)

## Unit Context (from functional-design)

Unit 2 hardens host-side surfaces (command/action subprocess invocation, tool registration). Security is the dominant NFR; scalability/performance/availability/maintainability/usability are N/A (desktop library, single pipeline process - same as unit-1). Tech stack unchanged.

## NFR Steps

- [x] Analyze unit-2 functional-design artifacts for NFR implications
- [x] Resolve NFR open questions (below)
- [x] Generate `aidlc-docs/construction/unit-2/nfr-requirements/nfr-requirements.md`
- [x] Generate `aidlc-docs/construction/unit-2/nfr-requirements/tech-stack-decisions.md`
- [x] Security-baseline dispositions table (blocking set)

## Open Questions

### Question NFR-1: environment-hygiene scope for command/action subprocesses

The FD (BR-4.3 / BR-5.4) says command/action subprocesses get a "scrubbed child environment". The concrete secret the pipeline holds is the LLM API key (`llm.api_key_env`, e.g. `OPENAI_API_KEY`), injected into the parent process. Command/action steps (pytest, git, lsof) never need it.

A) Scrub known secrets - start from the inherited `os.environ` and remove the pipeline's secret(s) (the `llm.api_key_env` value); everything else passes through (recommended - backward compatible; addresses the concrete secret the pipeline owns)

B) Whitelist minimal - build a fresh env with only `PATH` + a small known-safe set; strictest, but may break commands relying on other inherited vars (`HOME`, `VIRTUAL_ENV`, `LANG`, …)

C) Hybrid - whitelist a known-safe set plus an explicit allowlist the pipeline author can extend

X) Other

[Answer]: C - Hybrid. Build the child env from a fixed known-safe whitelist (PATH + the minimal vars tests/git need), plus an explicit, author-extensible allowlist (a new optional config key). Refined: the LLM API key (`llm.api_key_env`, i.e. `OPENAI_API_KEY` in the shipped pipeline) is **included by default** in the child env.

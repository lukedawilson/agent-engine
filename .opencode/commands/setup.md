---
description: Set up or repair the agentic-dev-loop pipeline's .venv. Use when ./trigger-agentic-dev-loop.sh fails with "No such file or directory" for .venv/bin/agentic-dev-loop, or when pip falls back to building Rust (maturin) wheels.
---

Set up the repo's Python virtualenv so `./trigger-agentic-dev-loop.sh` runs:

!`./setup-venv.sh`

The script is idempotent and handles the environment-specific trap: on this
machine a Termux userland (Android-targeting Python) shares a PATH with the
Debian proot system (`python3` → Debian, but `pip` → Termux). Building the
venv with the Android Python makes pip fall back to source builds (Rust/maturin)
for compiled packages like `pydantic-core` and `litellm`; the script selects the
non-Android interpreter and uses the venv's own pip.

After it runs, report:
- which Python interpreter was selected, and any Android/Termux interpreters skipped
- whether `python3-venv` / `python3-pip` had to be apt-installed
- whether the `.venv` was rebuilt
- the smoke-check result (`.venv/bin/agentic-dev-loop` present)

Then confirm the LLM secret is in place for the pipeline: `trigger-agentic-dev-loop.sh`
auto-sources a gitignored `.env` in the repo root. If `OPENAI_API_KEY` (or
whatever the pipeline's `llm.api_key_env` names) is missing, ask the user for it,
write it to `.env` as `OPENAI_API_KEY=<key>`, and verify with:

```bash
set -a; . ./.env; set +a
.venv/bin/python -c "from agent_engine.config import load_config; from agent_engine.llm import build_llm; build_llm(load_config('agentic-dev-loop/pipeline.yaml').llm); print('LLM OK')"
```

Do not run the full pipeline (it makes live LLM calls) unless the user asks.

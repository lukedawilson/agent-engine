# agentic-dev-loop

An opinionated library for building **stage-gated autonomous dev pipelines**.
A pipeline is a YAML file of steps; each step runs an OpenHands agent (with a
file-artifact verdict protocol), a deterministic Python action, or a
mechanical shell command (exit code = verdict); LangGraph drives routing,
retries, checkpoints and resume. The fixed policies — artifact hygiene,
attempt-bounded retries, fail-fast on empty context, a single gated commit
point — are the product.

Publicly depends on [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk)
for agent execution and [LangGraph](https://github.com/langchain-ai/langgraph)
(+ `langgraph-checkpoint-sqlite`) for the state graph.

## Sandboxed execution

The agent `terminal` tool and command steps run inside an **always-on**,
Docker-based kernel-level sandbox — `--network none`, read-only rootfs,
dropped capabilities, writes only on the bind-mounted workspace. The
`isolation:` section configures the sandbox (image override, resource caps,
per-step `env:`/`setup:`, git-mutation blocking); it can never disable it. A
missing or unusable Docker engine fails fast with an `AE-SBX-*` message. See
[docs/setup.md](docs/setup.md) for the engine setup, first-run image pull, the
`pipeline.yaml` contract, stamp caching, and troubleshooting.

## Install & test

```bash
pip install agentic-dev-loop  # published release
pip install -e .              # from this repo (development)
python -m pytest tests/ -q
```

Requires Python ≥ 3.12.

## Quick start

```bash
export OPENAI_API_KEY=...   # whatever env var your pipeline's api_key_env names
agentic-dev-loop agentic-dev-loop/pipeline.yaml --plan plan.md
agentic-dev-loop agentic-dev-loop/pipeline.yaml --aidlc-unit unit-2
agentic-dev-loop agentic-dev-loop/pipeline.yaml --resume <thread-id> --max-attempts 5
agentic-dev-loop agentic-dev-loop/pipeline.yaml --plan plan.md --dry-run
./trigger-agentic-dev-loop.sh --plan plan.md   # same thing, from the repo root
```

Exit code is `0` on pipeline success, `1` otherwise. Each run prints its
thread id; `--resume` continues the latest checkpoint of a previous thread
(crash, Ctrl-C, exhaustion) with all accumulated notes intact. A live graph
view is served on localhost by default (browser auto-opens; `--viz-port`
sets a preferred port, default 8321) — pass `--no-viz` to suppress it. A
stale viz server from a crashed run of the same repo is swept automatically
at startup; if another repo's run holds the port, the engine prints a notice
and serves on a free port. The sidebar
nests each stage's console output (ANSI colours preserved) under a
collapsible section: completed stages auto-collapse, the running stage stays
expanded and live-tails its console. To eyeball the viz page without
running a pipeline, `.venv/bin/python viz_demo.py` serves the real topology
and replays a scripted run (every node state, verdict badges, retry cycle).

`--dry-run` performs the full load-and-validate pass — YAML parse, step
config validation, extension and document-loader loading, agents_dir /
verdict / routing-target resolution, and pure image-ref resolution — without
executing anything, then prints a summary plan (pipeline path, subject,
resolved loader + docs, per-step kind and key params, and the resolved
isolation profile). It makes no LLM call, touches no Docker daemon, and
writes no state, so it needs no API key; it exits `0` on a clean load and
`1` with the usual load error otherwise.

`--aidlc-unit` takes the unit directory name under
`aidlc-docs/construction/` verbatim — `unit-2`,
`unit-002-custom-configuration`, or any slug AI-DLC's own naming uses
(AI-DLC imposes no naming convention on unit directories). No spelling
tolerance, no numeric aliases: the slug must name the directory exactly,
and a wrong slug fails loudly listing the directories that do exist.

## What a run looks like

The shipped self-loop example (`agentic-dev-loop/`, launched from the repo root
so the pipeline constructs this library itself) is:

```
dev ──▶ test ──▶ review ──▶ qa ──▶ commit
▲          │         │         │
└──────────┴─────────┴─────────┘   fail verdicts / a failing test gate
                                   retry to dev (attempt-bounded)
```

1. **dev** runs the `dev` agent with full context (selected docs +
   `additional_files:` + auto-generated expected-output paths). Its writes
   are untracked; the pipeline only cares about declared `produces:` files.
2. **test** is a mechanical command step: it runs the suite
   (`.venv-sandbox/bin/python -m pytest tests/ -q -m "not docker"`) inside the
   sandbox. Exit 0 passes and moves on; anything else (including no exit by
   `timeout`) fails and rewinds to `dev` with the failing output in the retry
   note.
3. **review / qa** are verdict agents: each must write its declared
   artifact (e.g. `qa-report.md`) whose **last** `VERDICT: <word>` line
   decides routing. `pass` follows `on_pass`, `fail` follows `on_fail` —
   here `{goto: dev, retry: true}`, which consumes an attempt and feeds the
   artifact back to the dev agent as a retry note.
4. **commit** is the single commit point: `git add -A` + templated message,
   but only when the worktree was clean at run start (your in-progress edits
   are never swept into a loop commit).
5. Attempts are bounded by `max_attempts` (YAML or `--max-attempts`).
   Exhaustion or a `failure` route ends the run; `success` commits and exits.

Every stage boundary is checkpointed to `<state_dir>/loop-checkpoints.sqlite`
— resume loses nothing but the in-flight stage.

## pipeline.yaml reference

Verbatim from `agentic-dev-loop/pipeline.yaml` (comments added):

```yaml
name: agentic-dev-loop-construction
extensions:
  - agentic_dev_loop.extensions.aidlc:AidlcExtension
additional_files:
  - ../README.md                     # shared context for every agent step

llm:
  model: openai/deepseek-v4-pro
  base_url: https://api.deepseek.com
  api_key_env: OPENAI_API_KEY        # missing env var → run fails fast, naming it
  # timeout: null                    # default = no client timeout (long agent runs)

# state_dir omitted → default ~/.agentic-dev-loop/runs/<pipeline-hash>/
# (artifacts + checkpoints live OUTSIDE the sandbox mount)
max_attempts: 10                      # retries across the whole graph
agents_dir: sdk_agents                # consumer-owned <name>.agent.md files

steps:
  - name: dev
    agent: dev                        # → sdk_agents/dev.agent.md
    produces: implementation-summary.md  # written under state_dir (str or list)
    on_pass: test                     # explicit; omitted → next step in order

  - name: test
    command: .venv-sandbox/bin/python -m pytest tests/ -q -m "not docker"   # sandboxed: exit code is the verdict
    setup: python -m venv .venv-sandbox && .venv-sandbox/bin/pip install -e ".[dev]"   # provision (network ON, stamp-cached)
    timeout: 600                                     # seconds
    on_pass: review
    on_fail: {goto: dev, retry: true}

  - name: review
    agent: review
    artifact: review-findings.md
    verdicts: {pass: APPROVED, fail: NEEDS CHANGES}
    on_pass: qa
    on_fail: {goto: dev, retry: true}

  - name: qa
    agent: qa
    artifact: qa-report.md
    max_iterations: 200               # per-run agent iteration cap
    verdicts: {pass: PASS, fail: FAIL}
    on_pass: commit
    on_fail: {goto: dev, retry: true}

  - name: commit
    action: commit                    # built-in action
    on_pass: success                  # terminal (also the default for the last step)
    params:
      message: "feat: construct {subject} (agent dev loop)"  # {subject} templated
```

### Step types

How a step behaves is determined solely by which of three mutually-exclusive
keys it carries — exactly one of `agent:`, `command:`, or `action:` is
required, an empty value does not count, and zero or several keys fail to
load. Graph-building dispatches on this `kind` (see `StepConfig.kind` in
`config.py`).

- **`agent: <name>`** — an *agent step*: loads `sdk_agents/<name>.agent.md`
  and runs it via the OpenHands SDK against the accumulated context. May
  declare `produces:` (hygiene-tracked outputs, no verdict parsing) or
  `artifact:` + `verdicts:` (verdict-parsed routing). `max_iterations` caps
  the agent's own loop.
- **`command: <shell>`** — a *command step*: mechanical, never an LLM call.
  The command runs inside the sandbox (the bind-mounted workspace); exit 0
  passes, anything else (including no exit by `timeout`) fails. `timeout:` and
  `setup:` are its only extra fields.
- **`action: <name>`** — an *action step*: invokes a registered node-shaped
  function `(state, params) -> state update` with the step's `params:`. The
  built-in is `commit`; extensions register more via `registry.add_action`.
  Unknown action names fail at graph build time, not mid-run.

- `agent`, `action`, and `command` are mutually exclusive; exactly one is
  required — an empty value does not count.

### Step semantics

- A `command` step is **mechanical** — the command runs inside the
  sandbox; exit 0 passes, anything else (including no exit by `timeout`,
  default 600s) fails and follows `on_fail` with the output tail in the
  retry note. The kind is the `command:` key, never the step's name.
- `artifact` + `verdicts` mark a **verdict step**. `on_pass`/`on_fail` may be
  a step name, the terminal `success`/`failure`, or `{goto: X, retry: true}`.
  `on_pass` omitted → next step in list order. `on_fail` omitted → `failure`.
  No loops happen unless you write them.
- A verdict agent that writes nothing, or writes an artifact with no
  parseable verdict, triggers an attempt-bounded retry with a note — verdicts
  are never silently routable, and the **last** verdict line wins (markdown
  decoration like `**VERDICT: PASS**` is tolerated).
- `produces:` / `artifact` files are deleted at every attempt start, so a
  retry can never re-read a stale artifact from the previous attempt.
- `params` on the `commit` action support `{subject}` templating
  (e.g. `"feat: {subject} (agent dev loop)"`).

## Extension points

Extensions are plain Python classes referenced by `extensions:` entries as
`module:Class` (the module must be importable — e.g. on `PYTHONPATH`):

```python
class MyExtension:
    name = "mine"
    def register(self, registry) -> None:
        registry.add_action("run_conformance", run_conformance)   # step actions
        registry.add_tool("figma", FigmaTool)                     # OpenHands tools
        registry.add_document_loader(MyLoader())                  # context sources
```

Working samples of all three kinds ship as the test fixture
`tests/sample_ext.py` (actions, tools, a document loader — plus constructor-
failure coverage).

**Actions** receive `(state, params)`; returning continues the pipeline,
raising fails the run. Actions have no verdict channel — for retry-driven
fixing, prefer a verdict agent step.

**Document loaders** decide which docs enter the run context:

```python
class MyLoader:
    name = "wiki"
    defaultable = False                     # may autodetect when no flag is given?
    def add_cli_args(self, parser):         # flag defaults MUST be None
        parser.add_argument("--wiki-page", default=None)
    def resolve(self, args):                # -> (docs: dict[str, str], subject: str)
        return fetch_docs(args.wiki_page), f"wiki {args.wiki_page}"
```

Loader-selection flow: a loader's flag in argv selects it; flags from two
loaders in one invocation error out; with no flag, the sole `defaultable`
loader autoruns (the bundled `ai-dlc` loader autodetects the current unit
from `aidlc-docs/aidlc-state.md`), otherwise the run proceeds with no
injected docs and the pipeline `name:` as subject. A unit id must name
its directory exactly (`--aidlc-unit unit-3`); there is no numeric
fallback or spelling tolerance, and an unmatched slug fails loud listing
the available directories. A selected loader that
yields zero docs **fails fast** — context is never silently degraded.
Duplicate CLI option strings across loaders are a load-time error naming both.

## Fixed policies (intentionally not configurable)

- **Fail fast on missing config/secrets** — no silent fallbacks.
- **Verdicts are file artifacts under `state_dir`**; the last
  decoration-tolerant `VERDICT: X` line wins.
- **Attempt-bounded retries** with full retry-note accumulation.
- **Per-attempt artifact hygiene** — stale artifacts are deleted, never
  re-parsed.
- **Single commit point**, gated on a clean-at-start worktree; the commit
  action no-ops rather than sweep up your unrelated edits.
- **Unclear verdicts are never routable** — always an attempt-bounded retry.
- **Command steps are mechanical** — never an LLM call; the exit code is the
  verdict; a timeout kills the process group.
- **Port sweeps are explicit actions** with required `port`, optional
  `match` substring filter — the startup sweep of the engine's own viz
  server (cwd-scoped, best-effort) is the one built-in exception.
- **No client-side LLM timeout by default** (`timeout: null`) — agent runs
  are long; set `timeout` if your provider needs one.
- **Crash-safe resume** — every stage boundary is a checkpoint.

## The example consumer

`agentic-dev-loop/` is a complete, runnable consumer that turns the library on
its own repo: the pipeline above, its three agent definitions (`sdk_agents/`),
and this README wired in as shared context. Run it from the repo root with
`./trigger-agentic-dev-loop.sh --plan plan.md`. The e2e suite
(`tests/test_e2e_fixtures.py`) replays historical failure fixtures against
it — markdown-decorated verdicts, stale-artifact hygiene, verdict-first
truncation, unclear-verdict retry, dirty-worktree commit skip, and
empty-context fail-fast.

## AI-DLC

The development lifecycle workflow lives in
`.aidlc/aidlc-rules/aws-aidlc-rules/core-workflow.md` (the entry point;
phase details under `aws-aidlc-rule-details/`). Working docs — plans, user
stories, units of work, state — live in `aidlc-docs/`, created as the
workflow runs. The bundled `ai-dlc` document loader (see Extension points)
wires the pipeline's `--aidlc-unit` flag to those docs.

OpenCode commands over the workflow: `/epic-status`, `/ticket-details`,
`/unit-status`, `/update-subtask` (ticket boards over `aidlc-docs/`),
`/apply-aidlc-patches` (numbered `.patch` files under `.aidlc/aidlc-patches/`,
applied by `apply-patches.sh`), `/load-backend-rules`
(`coding-standards-ddd.yaml`), `/software-selection`, `/postmortem`,
`/figma`, and `/export-opencode-tools-to-claude` (syncs commands and skills
into `.claude-local/` for the Claude CLI).

Skills: `brainstorming`, `hypothesis-generation`, `writing-plans`.

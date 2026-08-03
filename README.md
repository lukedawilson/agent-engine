# agent-engine

An opinionated library for building **stage-gated autonomous dev pipelines**.
A pipeline is a YAML file of steps; each step runs an OpenHands agent (with a
file-artifact verdict protocol) or a deterministic Python action; LangGraph
drives routing, retries, checkpoints and resume. The fixed policies —
artifact hygiene, attempt-bounded retries, fail-fast on empty context, a
single gated commit point — are the product.

Publicly depends on [OpenHands SDK](https://github.com/OpenHands/software-agent-sdk)
for agent execution and [LangGraph](https://github.com/langchain-ai/langgraph)
(+ `langgraph-checkpoint-sqlite`) for the state graph.

## Install & test

```bash
pip install -e .          # from this repo
python -m pytest tests/ -q
```

Requires Python ≥ 3.11.

## Quick start

```bash
export OPENAI_API_KEY=...   # whatever env var your pipeline's api_key_env names
agent-engine examples/consumer-yosk/pipeline.yaml --plan plan.md
agent-engine examples/consumer-yosk/pipeline.yaml --ai-dlc-unit U2
agent-engine examples/consumer-yosk/pipeline.yaml --resume <thread-id> --max-attempts 5
```

Exit code is `0` on pipeline success, `1` otherwise. Each run prints its
thread id; `--resume` continues the latest checkpoint of a previous thread
(crash, Ctrl-C, exhaustion) with all accumulated notes intact.

## What a run looks like

The consumer-yosk example pipeline is:

```
dev ──▶ checks ──▶ review ──▶ port_sweep ──▶ qa ──▶ commit
▲          │           │                │
└──────────┴───────────┴────────────────┘   fail verdicts retry to dev
                                          (attempt-bounded)
```

1. **dev** runs the `dev` agent with full context (selected docs +
   `additional_files:` + auto-generated expected-output paths). Its writes
   are untracked; the pipeline only cares about declared `produces:` files.
2. **checks / review / qa** are verdict agents: each must write its declared
   artifact (e.g. `.pr/ci-fix.md`) whose **last** `VERDICT: <word>` line
   decides routing. `pass` follows `on_pass`, `fail` follows `on_fail` —
   here `{goto: dev, retry: true}`, which consumes an attempt and feeds the
   artifact back to the dev agent as a retry note.
3. **port_sweep** is a built-in action (kill listeners on a port) — no agent,
   no verdict.
4. **commit** is the single commit point: `git add -A` + templated message,
   but only when the worktree was clean at run start (your in-progress edits
   are never swept into a loop commit).
5. Attempts are bounded by `max_attempts` (YAML or `--max-attempts`).
   Exhaustion or a `failure` route ends the run; `success` commits and exits.

Every stage boundary is checkpointed to `<state_dir>/loop-checkpoints.sqlite`
— resume loses nothing but the in-flight stage.

## pipeline.yaml reference

Verbatim from `examples/consumer-yosk/pipeline.yaml` (comments added):

```yaml
name: yosk-construction
extensions:
  - agent_engine.extensions.aidlc:AidlcExtension
additional_files:
  - coding-standards-ddd.yaml        # shared context for every agent step

llm:
  model: openai/deepseek-v4-pro
  base_url: https://api.deepseek.com
  api_key_env: OPENAI_API_KEY        # missing env var → run fails fast, naming it
  extra_body:
    chat_template_kwargs:
      thinking: false
  # timeout: null                    # default = no client timeout (long agent runs)

state_dir: .pr                        # artifacts + checkpoints live here
max_attempts: 3                       # retries across the whole graph
agents_dir: sdk_agents                # consumer-owned <name>.agent.md files

steps:
  - name: dev
    agent: dev                        # → sdk_agents/dev.agent.md
    produces: implementation-summary.md  # written under state_dir (str or list)
    on_pass: checks                   # explicit; omitted → next step in order

  - name: checks
    agent: checks
    artifact: ci-fix.md               # verdict file the agent must write
    verdicts: {pass: PASS, fail: FAIL}
    on_pass: review
    on_fail: {goto: dev, retry: true} # consumes an attempt

  - name: review
    agent: review
    artifact: review.md
    verdicts: {pass: APPROVED, fail: CHANGES_REQUESTED}
    on_pass: port_sweep
    on_fail: {goto: dev, retry: true}

  - name: port_sweep
    action: kill_listeners            # built-in action
    params: {port: 8080, match: "Yosk"}
    on_pass: qa

  - name: qa
    agent: qa
    artifact: qa-report.md
    max_iterations: 200               # per-run agent iteration cap
    verdicts: {pass: PASS, fail: FAIL}
    on_pass: commit
    on_fail: {goto: dev, retry: true}

  - name: commit
    action: commit                    # built-in action
    params:
      message: "feat: construct plan plan.md (agent dev loop)"
```

Step semantics:

- `agent` and `action` are mutually exclusive; exactly one is required.
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

Working samples ship in `examples/consumer-yosk/extensions/`
(`figma_tool.py`, `conformance_action.py`).

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
injected docs and the pipeline `name:` as subject. A selected loader that
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
- **Port sweeps are explicit actions** with required `port`, optional
  `match` substring filter.
- **No client-side LLM timeout by default** (`timeout: null`) — agent runs
  are long; set `timeout` if your provider needs one.
- **Crash-safe resume** — every stage boundary is a checkpoint.

## The example consumer

`examples/consumer-yosk/` is a complete, runnable consumer: the pipeline
above, its four agent definitions (`sdk_agents/`), a shared standards doc,
and two extension modules. The e2e suite (`tests/test_e2e_fixtures.py`)
replays historical failure fixtures against it — markdown-decorated
verdicts, stale-artifact hygiene, verdict-first truncation, unclear-verdict
retry, dirty-worktree commit skip, and empty-context fail-fast.

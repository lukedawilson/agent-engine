# AI-DLC Audit Log

## Workspace Detection — Initial Request
**Timestamp**: 2026-10-17T10:58:41Z
**User Input**: "Ok, we're going to address this intent in two stages: 1. Harden the existing tooling injection via what the OpenHands SDK provides 2. Introduce proper kernel-level isolation. First, I want you to bring in AI-DLC - take it from ~/dev/agentic-dev-template" — then "Don't need a port plan, just do it" — then "1. Commit and push AI-DLC stuff 2. Start the ai-dlc flow specifying the SDK-level hardening and kernel-level isolation as a guardrails and sandboxing intent"
**AI Response**: Ported AI-DLC workflow from ~/dev/agentic-dev-template (commit b6e70ee, pushed to origin/main). Started AI-DLC workflow per core-workflow.md: loaded mandatory common rules (process-overview, session-continuity, content-validation, question-format-guide), loaded 4 extension opt-in files (domain-standards, resiliency-baseline, security-baseline, property-based-testing — all have .opt-in.md, none always-enforced), displayed welcome message.
**Context**: INCEPTION - Workspace Detection. Intent recorded: (1) SDK-level hardening of existing tooling injection; (2) kernel-level isolation for guardrails and sandboxing of agent-engine.

## Workspace Detection — Findings
**Timestamp**: 2026-10-17T10:58:41Z
**User Input**: N/A (automated stage execution)
**AI Response**: Scan complete. aidlc-docs/aidlc-state.md does not exist (new project assessment). Existing code found: Python library (agent-engine, src/agent_engine/, ~2,650 LOC across 13 modules), pyproject.toml (setuptools), LangGraph + OpenHands SDK stack, tests/ suite (16 test files), example consumer in agent-engine/. brownfield = true. No reverse engineering artifacts in aidlc-docs/inception/reverse-engineering/ → next phase = Reverse Engineering.
**Context**: INCEPTION - Workspace Detection. aidlc-docs/ directory structure created (inception/{plans,requirements,user-stories,application-design,reverse-engineering}, construction/{plans,build-and-test}, operations).

---

## Workspace Detection — Completion Message Presented
**Timestamp**: 2026-10-17T10:58:41Z
**User Input**: N/A (automated stage execution)
**AI Response**: Presented welcome message + workspace detection completion message. Brownfield project, Reverse Engineering needed, no artifacts present. Proceeding automatically to Reverse Engineering per workspace-detection.md Step 6.
**Context**: INCEPTION - Workspace Detection → Reverse Engineering transition.

---

## Reverse Engineering — Executed
**Timestamp**: 2026-10-17T10:58:41Z
**User Input**: N/A (automated stage execution)
**AI Response**: Read all 13 library modules + pyproject.toml + pipeline.yaml + 3 agent files. Generated 8 artifacts in aidlc-docs/inception/reverse-engineering/ (business-overview, architecture, code-structure, api-documentation, component-inventory, technology-stack, dependencies, code-quality-assessment) + reverse-engineering-timestamp.md. Updated aidlc-state.md. Key finding for the intent: tool injection is prompt-level allowlisting over a full-authority terminal; shell surfaces = terminal tool, command steps (shell=True), actions.py subprocess calls. Presented completion message; waiting for user approval per reverse-engineering.md Step 13.
**Context**: INCEPTION - Reverse Engineering.

---

## Requirements Analysis — Q1 answer
- 2026-10-17T11:05:00Z — Q1 (Stage 1 scope): **C** — Everything: SDK surface, command steps, action-step subprocess calls, extension tool registration

## Requirements Analysis — Q2 answer
- 2026-10-17T11:12:00Z — Q2 (Stage 2 platform): **C** — container runtime. "C is better, because we will want to support Linux (and even, sigh, Windows)". Docker Engine API as abstraction; runtime per platform.

## Requirements Analysis — Q3–Q7 answers
- 2026-10-17T11:20:00Z — Q3 (isolation scope): **B** — terminal tool + command steps; everything else host-side (trusted code)
- Q4 (profile defaults): DEFERRED to FD. Intent: isolation OPTIONAL, no forced container use
- Q5 (compat posture): Stage 2 = opt-in (user statement). Stage 1 = pending Q5a
- Q6 (unavailable-isolation failure mode): DEFERRED to FD (kernel unit)
- Q7 (granularity): two+ units — Unit 1 SDK hardening FIRST, Unit 2+ kernel isolation (intent only here)
- 2026-10-17T11:25:00Z — Q5a (stage 1 posture): **A** — default-on / always-on ("Always-on"); per-pipeline opt-out escape hatches
- 2026-10-17T11:30:00Z — Q5 CORRECTION: Stage 1 = always-on with NO opt-out flags ("We're guardrailed by design")
- 2026-10-17T11:30:00Z — Q6 (unavailable isolation): **A** — fail fast, refuse to run
- 2026-10-17T11:35:00Z — Security extension: **A** — enforce as blocking constraints. Full rules loaded (deferred rule loading per requirements-analysis.md Step 5.1)
- 2026-10-17T11:40:00Z — Domain Standards extension: **A** — enforce as blocking. Full rules loaded
- 2026-10-17T11:45:00Z — Resiliency extension: **A (scoped)** — "keep it light. This is running on someone's desktop... we don't need the full server treatment (load, etc.)". Retry/recovery guidance in scope; server load/HA/DR out. Full rules loaded
- 2026-10-17T11:52:00Z — PBT extension: **B (Partial)** — pure functions + serialization round-trips only. Full rules loaded

## Requirements Analysis — Q11-follow-up (file_editor gap)
- 2026-10-17T12:00:00Z — Follow-up (file_editor host-side surface): **A** — drop file_editor entirely. User rationale: it exists only to write the agent's report, and that mechanism "has failed anyway, since it often forgets to write the report. So we need a better mechanism for it to feed back its findings." → new requirement (Q12).

## Requirements Analysis — Q12 (findings-feedback mechanism)
- 2026-10-17T12:05:00Z — **A** — pipeline captures the agent's final SDK response and writes the artifact itself; verdict parsing reads from the captured response. NOTE: parsing-logic details deferred to Functional Design (existing parsing has had bugs — dedicated FD discussion). Capture mechanism itself = Stage-1 requirement.

## Requirements Analysis — Step 7-8 executed
- 2026-10-17T12:10:00Z — requirements.md generated at aidlc-docs/inception/requirements/requirements.md (intent analysis + FR/NFR tables incorporating all Q1-Q12 answers; Unit 1 always-on, Unit 2 opt-in; extensions scoping recorded). aidlc-state.md Stage Progress updated.
- 2026-10-17T12:10:00Z — Review requested (Step 9 completion message presented). Waiting for user approval.

## Requirements Analysis — APPROVED (user directives)
- 2026-10-17T12:15:00Z — User approved requirements with three directives:
  1. UNIT REORDER: the findings/verdict-passing mechanism (Q12) becomes UNIT 1, executed BEFORE tool-hardening — "It's a genuine bug-in-waiting and should be fixed first."
  2. User Stories: skipped (confirmed — no need).
  3. Units must be VERTICAL SLICES (each unit delivers end-to-end user-visible behavior through the stack), not horizontal layers.
- Proceeding to Workflow Planning.

## Workflow Planning — executed
- 2026-10-17T12:20:00Z — execution-plan.md generated at aidlc-docs/inception/plans/execution-plan.md (risk Medium; US/NFRD skip; AD/UG/FD/NFRA/ID/CG/BT execute; unit order Unit1→Unit2→Unit3 vertical slices). aidlc-state.md updated with Execution Plan Summary. Review requested.

## Workflow Planning - Approval
**Timestamp**: 2026-10-17T12:25:00Z
**AI Prompt**: "Ready to proceed with this plan?"
**User Response**: "Three stages: 1. Fix the way output is passed between stages (and then remove file writing tools from agents that no longer need them) 2. SDK-level hardening 3. Kernel-level isolation"
**Status**: Approved (user restated the three units; Unit 1 explicitly includes removing file-writing tools — file_editor — from agents after the output-passing fix)
**Context**: Workflow plan created with 7 stages to execute, 2 skipped

## Application Design — plan created
- 2026-10-17T12:30:00Z — application-design-plan.md created (mandatory artifacts checklist + 6 Domain Exposition questions Q-AD1..Q-AD6). Presenting questions inline per AGENTS.md override.

## Application Design — Domain Exposition complete
- 2026-10-17T12:45:00Z — Q-AD1..Q-AD6 all answered **A** (with recommendations accepted):
  1. New feedback-domain component (outputs.py-style): capture + verdict parsing together
  2. Pipeline writes captured response to existing artifact path; build_context untouched
  3. Tool restrictions = .agent.md frontmatter only
  4. New isolation component: IsolationBackend protocol + DockerBackend impl
  5. FakeBackend as test seam; real Docker only in opt-in integration tests
  6. Source-agnostic pure parser: parse(text) -> Verdict
- Proceeding to Step 10: generate application design artifacts (components.md, component-methods.md, services.md [descent audit], component-dependency.md, application-design.md).

## Application Design — artifacts generated
- 2026-10-17T12:55:00Z — Generated components.md, component-methods.md, services.md (descent audit), component-dependency.md, application-design.md (consolidated). All six Q-AD decisions incorporated (all A). Review requested.

## Application Design — DDD-rule amendments applied (user approved)
- 2026-10-17T13:05:00Z — /load-backend-rules loaded coding-standards-ddd.yaml; conflicts flagged vs AD; user accepted all revision recommendations. Applied:
  1. Q-AD4: IsolationBackend protocol REPLACED by single concrete `Sandbox` type (Docker Engine API; platform variance internal). Interface extracted only when a second backend (native Linux namespaces) lands.
  2. Q-AD5: FakeBackend seam REMOVED (testability-driven structure forbidden); pure parts unit-tested, real Docker in opt-in integration tests.
  3. Q-AD6: parser returns typed Result[Verdict] (NO_VERDICT/AMBIGUOUS) — no exceptions for expected conditions.
  4. services.md descent audit: Outputs/IsolationProvider services REMOVED (one caller = no service) → CapturedOutput.from_agent_result static constructor, Sandbox.for_config static method. Zero new services.
  5. requirements.md: open question added — Unit 3 FD "Linux: Docker vs native namespace isolation".
- Files amended: application-design-plan.md, components.md, component-methods.md, services.md, component-dependency.md, application-design.md, requirements.md.

## Application Design — Domain Model APPROVED
- 2026-10-17T13:20:00Z — User approved the amended domain model ("I'm happy with this domain model — approved"). Change-surface Mermaid class diagram embedded in application-design.md Domain Shape section. User requested a full-pipeline diagram (all components, change-marked) for reference; per-unit FD docs will reference the approved diagram.

## Full-pipeline domain diagram recorded
- 2026-10-17T13:30:00Z — Full-pipeline Mermaid class diagram (all components, change-marked by unit) recorded in component-dependency.md. User-requested caveat included: parts of the EXISTING unchanged model are known to need refactoring under a future intent (outside this scope); diagram records today's structure for traceability. Proceeding to Units Generation.

## Units Generation — Part 1 Planning answers
- 2026-10-17T13:45:00Z — U-1 unit naming: **A** — numeric `unit-1`/`unit-2`/`unit-3` (matches ai-dlc loader `construction/unit-<N>/` expectation; reconciles the ported-commands layout gap)
- 2026-10-17T13:46:00Z — U-2 story-map source: **A** — map FR/NFR IDs to units; no stories generated
- 2026-10-17T13:47:00Z — U-3 Unit 2 scope: **A** — confirm mapping (FR-1.1, FR-1.4, FR-1.5, FR-1.6, FR-1.7); command-step hardening stays in Unit 2

## Units Generation — Part 1 approval
- 2026-10-17T13:50:00Z — Approval prompt: "Unit of work plan complete. Review the plan in aidlc-docs/inception/plans/unit-of-work-plan.md. Ready to proceed to generation?"
- 2026-10-17T13:50:00Z — User response: "Yes"

## Units Generation — Part 2 Generation executed
- 2026-10-17T14:00:00Z — Generated unit-of-work.md (3 units: unit-1 output-passing fix, unit-2 SDK hardening, unit-3 kernel isolation; responsibilities + key domain objects + out-of-scope), unit-of-work-dependency.md (matrix + mermaid + coupling rules + validation), unit-of-work-story-map.md (all FR/NFR mapped to units; no unassigned). Plan checkboxes [x], state updated. Review requested.

## Units Generation — Approval
- 2026-10-17T14:05:00Z — User response: "Agreed" (approving units generation, proceeding to CONSTRUCTION PHASE)

## Construction — unit-1 Functional Design answers
- 2026-10-17T14:20:00Z — FD-1 capture scope: **A** — capture replaces exactly produces:/artifact: channels; other terminal-produced files untouched
- FD-2 verdict semantics: **A** — last-VERDICT-line-wins + decoration tolerance + caveat handling; typed Result[Verdict] (NO_VERDICT/AMBIGUOUS), no exceptions
- FD-3 truncation: **A** — verdict-first truncation for verdict channel; summary keeps full response; build_context truncates to budget
- FD-4 missing/empty response: **A** — attempt failure, increment attempt, retry per existing policy
- FD-5 YAML: **A** — implicit capture, schema unchanged, no opt-out

## Construction — unit-1 Functional Design artifacts generated
- 2026-10-17T14:30:00Z — Generated business-logic-model.md, business-rules.md, domain-entities.md under aidlc-docs/construction/unit-1/functional-design/. DDD descent audit passed (VOs own parse/write; StagesRuntime delegates only; no new services). PBT-01 properties identified. Review requested.

## Construction — unit-1 Functional Design approval
- 2026-10-17T14:35:00Z — User response: "Approve and continue" (unit-1 FD approved; proceeding to NFR Requirements)

## Construction — unit-1 NFR Requirements generated
- 2026-10-17T14:55:00Z — NFR answers: NFR-1=A (generic Result[T,E]), NFR-2=A (hypothesis dev dep), NFR-3=A (no new data-protection requirements). Generated nfr-requirements.md (5 NFRs; scalability/performance/availability/maintainability/usability N/A per user scoping; security rule dispositions table) + tech-stack-decisions.md (5 decisions, 1 deferred item) under aidlc-docs/construction/unit-1/nfr-requirements/. Review requested.

## Construction — unit-1 NFR Requirements approval
- 2026-10-17T15:00:00Z — User response: "Approve and continue" (unit-1 NFR Requirements approved; proceeding to Infrastructure Design)

## Construction — unit-1 Infrastructure Design generated
- 2026-10-17T15:10:00Z — All 7 infrastructure categories N/A with justification (unit-1 = in-process data-flow change, desktop library; zero infrastructure footprint). Generated infrastructure-design.md + deployment-architecture.md under aidlc-docs/construction/unit-1/infrastructure-design/; unit-3 infra (daemon socket, mounts, images) explicitly deferred. No open questions. Review requested.

## Construction — unit-1 Infrastructure Design approval
- 2026-10-17T15:20:00Z — User response: "Approve and continue" (unit-1 Infrastructure Design approved; proceeding to Code Generation)

## Construction — unit-1 Code Generation plan
- 2026-10-17T15:30:00Z — Logging approval prompt: unit-1 code-generation plan created at aidlc-docs/construction/plans/unit-1-code-generation-plan.md (13 TDD steps; brownfield: modify stages.py + 2 agent files + pyproject; create results.py/outputs.py + 4 test files; delete verdicts.py; N/A steps documented). Awaiting user approval of the plan (covers entire generation sequence).

## Construction — unit-1 code-generation plan approval
- 2026-10-17T15:40:00Z — User response: "Yes, record it as a note. Then TDD unit 1, red/green/refactor" — self-hosting note recorded in plan; plan APPROVED; proceeding to Part 2 (Generation) via strict TDD.

## Construction — unit-1 Code Generation complete
- 2026-10-17T16:30:00Z — All 13 plan steps executed TDD. Full suite 373 passed. Files: created results.py/outputs.py + 4 test files + code docs; modified stages.py, 3 agent files, pyproject.toml, conftest.py, 3 test files; deleted verdicts.py + test_verdicts.py. Review requested.

## Construction — unit-2 Functional Design session resumption
- 2026-10-18T00:00:00Z — Resumed workflow. aidlc-state.md current stage: CONSTRUCTION — unit-1 complete, next = unit-2 Functional Design. Loaded: common rules (process-overview, session-continuity, content-validation, question-format-guide), unit-of-work.md, unit-of-work-story-map.md, unit-of-work-dependency.md, requirements.md, domain-standards + security-baseline + coding-standards-ddd extensions, and unit-1 FD artifacts (format reference). Reverse-engineered current code: agents.py (load_agent), registry.py (add_tool), config.py, actions.py, stages.py (_run_command), sdk_agents/*.agent.md, plus SDK AgentDefinition/Agent schema + register_tool + agent_definition_to_factory.
- 2026-10-18T00:00:00Z — User request (raw): "./trigger-agent-engine.sh --ai-dlc-unit U2" failed with FileNotFoundError (no construction/unit-2/ docs); user selected "Run Unit 2 Functional Design now".

## Construction — unit-2 Functional Design answers
- 2026-10-18T00:00:00Z — FD-1 task_tracker: **B** — drop the instruction; dev stays terminal-only (least-privilege; pipeline owns cross-step progress). User later confirmed "drop task list tool".
- FD-2 tool set: **B** — capabilities + FinishTool + ThinkTool. `tools:` = exact capability allowlist; FinishTool (done signal) + ThinkTool (reasoning scaffold) always present as infra. Empty `tools:` → think + finish only. User confirmed "keep think tool available".
- FD-2b filter_tools_regex: **A** — drop it; explicit allowlist is the whole story.
- FD-3 command shell: **A** — hybrid (shlex argv when no metacharacters, shell=True for complex, env hygiene in both).
- FD-4 reserved names: **A** — collision = any name in the SDK global registry (list_registered_tools) + non-empty identifier.
- FD-5 action subprocess: **B** — deeper (pid-token numeric validation + shutil.which binary resolution + explicit shell=False + env hygiene).

## Construction — unit-2 Functional Design artifacts generated
- 2026-10-18T00:00:00Z — Generated business-logic-model.md, business-rules.md, domain-entities.md under aidlc-docs/construction/unit-2/functional-design/. DDD descent audit passed (all new behaviour = step 0 static helpers or step 2 existing-entity methods; no new VO/entity/service; no single-impl interface; no persistence). PBT-02 properties identified. **Scope amendment**: FR-1.1 reduced by FD-2/FD-2b — no filter_tools_regex, no include_default_tools frontmatter knob (requirements.md FR-1.1 + unit-of-work.md "new frontmatter fields" wording to be amended). Review requested.

## Construction — unit-2 Functional Design approval
- 2026-10-18T00:00:00Z — User response: "Approved" (unit-2 FD approved; proceeding to NFR Requirements). Scope amendment applied: requirements.md FR-1.1 + unit-of-work.md unit-2 responsibility/key-domain-object wording updated to the reduced tool-surface scope.

## Construction — unit-2 NFR Requirements answers
- 2026-10-18T00:00:00Z — NFR-1 environment hygiene: **C** — Hybrid. Fixed known-safe whitelist (PATH + minimal vars) + author-extensible allowlist (new optional config key); secrets excluded by default.

## Construction — unit-2 NFR Requirements artifacts generated
- 2026-10-18T00:00:00Z — Generated nfr-requirements.md (5 NFRs: env hygiene, input validation, fail-closed, PBT, backward compat; scalability/performance/availability/maintainability/usability N/A; security dispositions: SECURITY-05/06/12/15 applicable, rest N/A) + tech-stack-decisions.md (6 decisions: no new deps, whitelist+allowlist env, proc module, add_tool validation, shutil.which, optional config key; 3 deferred to unit-3) under aidlc-docs/construction/unit-2/nfr-requirements/. FD artifacts updated (child_env → whitelist+allowlist; BR-7 → one optional additive key). Review requested.

## Construction — unit-2 NFR Requirements approval
- 2026-10-18T00:00:00Z — User response (raw): "Include OPENAI_API_KEY by default in the allowlist. Then approve and continue" — NFR-1 refined: the LLM API key (`llm.api_key_env`) is **included by default** in the child env (not scrubbed). Env-allowlist key pinned as `env_allowlist: list[str] = []` (pipeline-level, optional, additive). Artifacts updated (nfr-requirements.md, tech-stack-decisions.md, FD business-rules/logic-model/domain-entities). NFR Requirements APPROVED; proceeding to Infrastructure Design.

## Construction — unit-2 Infrastructure Design generated
- 2026-10-18T00:00:00Z — All 7 infrastructure categories N/A with justification (unit-2 = in-process host-side hardening, desktop library; zero infra footprint). Generated infrastructure-design.md + deployment-architecture.md under aidlc-docs/construction/unit-2/infrastructure-design/; container infra (daemon socket, mounts, image toolchain) explicitly deferred to unit-3. No open questions. Review requested.

## Construction — unit-2 Infrastructure Design approval
- 2026-10-18T00:00:00Z — User response: "Approve and continue" (unit-2 Infra Design approved; proceeding to Code Generation). User addition (raw): "Unit also includes updating the example agent Def front matter so it will still work" — unit-2 scope now explicitly includes updating/verifying the shipped example agent definitions (`agent-engine/sdk_agents/*.agent.md`) so they remain valid under the new tool-surface semantics (BR-1) and the FR-1.4 change.

## Construction — unit-2 Code Generation plan
- 2026-10-18T00:00:00Z — Logging approval prompt: unit-2 code-generation plan created at aidlc-docs/construction/plans/unit-2-code-generation-plan.md (14 TDD steps; brownfield: create proc.py + 2 test files; modify registry.py, stages.py, actions.py, config.py, agents.py docstring, dev.agent.md; no new runtime deps; FR-1.1 = test + docstring only, no load_agent logic change). Awaiting user approval of the plan (covers the entire generation sequence).

## Construction — unit-2 Code Generation — delegated to user's dev loop
- 2026-10-18T00:00:00Z — User response (raw): "I'll run the dev loop myself, so just create the artefacts and stop" — unit-2 code generation (Part 2) is delegated to the user's dev loop (self-hosting via `./trigger-agent-engine.sh --ai-dlc-unit U2`). Assistant creates design/plan artefacts only and writes no application code. All unit-2 design artefacts (FD, NFR, Infrastructure Design) + the code-generation plan are in place; the dev agent executes the plan's 14 TDD steps.

## Construction — unit-2 capture-path defects fixed (blocking the dev loop)
- 2026-10-19T00:00:00Z — Root-caused why the dev loop retried to exhaustion: `_final_agent_text` read `conv.events`, which the SDK never provides (the events live on `conv.state.events`), so every agent response was captured empty ("no final response"). Fixed by delegating to the SDK's own `get_agent_final_response(conv.state.events)`; added a real-Conversation integration test (`TestLLM` scripted to finish) so synthetic fixtures can't mask it again. Also fixed `--max-attempts` being dropped on `--resume` (re-applied via `graph.update_state`). Both committed (`34b4891`, `4062fdf`).

## Construction — unit-2 Code Generation complete (dev loop succeeded)
- 2026-10-19T00:00:00Z — Dev loop completed on attempt 16 (first with the capture fix): dev → test → review → qa all passed, qa VERDICT: PASS, outcome=success. Full suite green: 391 passed. Auto-commit skipped by policy (worktree dirty at run start) — unit-2 code committed manually by user. Files: new `src/agent_engine/proc.py` + `tests/test_proc.py`; modified `registry.py`, `actions.py`, `stages.py`, `config.py`, `agents.py`, `sdk_agents/dev.agent.md`, and test files.

## Construction — unit-3 Functional Design session resumption
- 2026-10-19T09:54:51Z — Resumed workflow. aidlc-state.md current stage: CONSTRUCTION — unit-2 complete (approved 2026-10-19), next = unit-3 Functional Design. Loaded: core-workflow.md, session-continuity.md, functional-design.md rules; unit-of-work.md (unit-3 definition), unit-of-work-story-map.md (FR-2.1–2.6 assignments), requirements.md (FR-2.1–2.6), unit-3-functional-design-plan.md (domain exposition drafted, FD-1–FD-5 open), unit-2 FD artifacts (format reference). Extensions enabled per state: domain-standards, security-baseline (scoped), resiliency (scoped), PBT (partial).
- 2026-10-19T09:54:51Z — User request (raw): "continue unit 3" — proceeding with unit-3 Functional Design stage; presenting FD open questions inline, one at a time, writing answers back to the plan after each.

## Construction — unit-3 Functional Design answers
- 2026-10-19T09:54:51Z — FD-1 default isolation profile: **A** — network-egress blocked + writes restricted to the bind-mounted workspace/state_dir (most conservative default).
- 2026-10-19T09:54:51Z — FD-2 Linux backend: **B** — Docker on macOS/Windows + native namespace isolation on Linux. Two backends ⇒ shared Sandbox interface extracted now; FR-2.2 scope amendment required (abstraction = Sandbox surface; Docker Engine API = macOS/Windows backend). Follow-up FD-2b raised re: native-backend toolchain source.
- 2026-10-19T09:54:51Z — User input (raw): "Make sure we have some way to test the linux side - I don't have a linux box at the moment" — Linux-testability constraint recorded; resolution drafted in plan (pure-function unit tests run everywhere; native-backend integration tests run on a GitHub Actions Linux runner and/or an optional local lima VM; macOS dev loop exercises the Docker backend only; backend-selection logic unit-tested via fake availability probe).
- 2026-10-19T09:54:51Z — FD-2b native toolchain: **A** — host toolchain inside namespaces; no image on Linux (matches the no-daemon motivation).
- 2026-10-19T09:54:51Z — FD-2c Linux failure mode: **A** — native-only on Linux, fail fast; explicit backend-selection knob in config feeds FD-4.
- 2026-10-19T09:54:51Z — FD-3 preliminary: User response (raw): "(1) but commit is also inside (it's a destructive action). What do you mean by 'action steps'?" — user wants the commit action inside the boundary; asked for clarification of step-type terminology. Assistant explained step types from code (agent/command/action; actions.py = commit, kill_listeners_on_port, git_worktree_clean); follow-up FD-3b raised.
- 2026-10-19T09:54:51Z — FD-3b: User response (raw): "No, in that case, the commit ACTION doesn't need to be 'in'. What's necessary is to block the agents doing arbitrary commits themselves unless we allow it" — commit action stays host-side (FR-2.6 unchanged); NEW requirement: the sandbox profile blocks agent-initiated git mutations inside the sandbox by default, with an author-controlled allow mechanism. Follow-up FD-3c raised (block scope + allow shape). Residual risk accepted + recorded: agent-influenced git hooks can still execute host-side during the trusted commit action.
- 2026-10-19T09:54:51Z — FD-3c git-mutation block: **A** — block all repo-mutating git operations by default (commit, push, reset, branch/tag create/delete, stash, merge, rebase, worktree add …); reads always allowed; one profile knob re-allows mutations per-pipeline.
- 2026-10-19T09:54:51Z — FD-4 always-on directive: User response (raw): "Sandboxing is always-on. We're not giving developers a foot-gun here, this is an opinionated harness that runs stuff in isolation. If you don't like it, use claude code and have your agents hack your bank account if you want :-)" — **MAJOR SCOPE CHANGE**: isolation is mandatory, not opt-in. Consequences recorded: FR-2.3 becomes "no usable runtime ⇒ fail fast always" (hard prerequisite for every run, including the self-hosted dev loop); unit-of-work.md unit-3 "OPT-IN — not requested ⇒ behavior unchanged" wording overturned; NFR-1 backward-compat now = pipeline semantics unchanged but a sandbox runtime is a new environment requirement; config section becomes always-on sandbox configuration (not an opt-in flag); fail-fast messages must name the missing runtime and how to install it. FD-4 re-posed accordingly.
- 2026-10-19T09:54:51Z — FD-4b config defaults: **A** — optional `isolation:` section with opinionated defaults (default profile, pinned default image, auto-detected backend with override knob); sandbox active regardless.
- 2026-10-19T09:54:51Z — FD-5 testability: **A** — fake at the Sandbox interface level; pure translation logic tested everywhere; real-backend integration tests marked and opt-in (Docker: daemon-present machines; native: CI Linux runner / lima VM), never silently skipped. All FD questions answered; proceeding to artifact generation.

## Construction — unit-3 Functional Design artifacts

- 2026-10-19T10:20:54Z — Generated the three functional-design artifacts under `aidlc-docs/construction/unit-3/functional-design/`: business-logic-model.md (core flow, FD key-decisions table, algorithms incl. pure translation functions, data-flow mermaid, PBT-03 property table), business-rules.md (BR-1..BR-12 + Security-baseline mapping), domain-entities.md (trace list, Sandbox entity + two backends, request/result VOs, modified PipelineConfig/_run_command/terminal-tool wiring, descent audit, FR/NFR traceability, deferred amendments).
- 2026-10-19T10:20:54Z — DDD validation passed (descent audit in domain-entities.md; no service/VO abuse; single extracted interface justified by two day-one backends). Security-baseline compliance check passed (mapping table in business-rules.md; SECURITY-01/02/04/08/14 N/A). PBT properties identified (PBT-03 invariants + PBT-02 round-trips in business-logic-model.md).
- 2026-10-19T10:20:54Z — Plan title/unit-context amended from opt-in to always-on per FD-4; all plan checkboxes marked [x]. Awaiting user review/approval of the functional design.

## Construction — unit-3 Functional Design approved
- 2026-10-19T10:24:25Z — User approval (raw): "Approved, btw" — unit-3 Functional Design approved; stage complete. aidlc-state.md updated: unit-3 IN PROGRESS, FD approved, next = NFR Requirements.

## Construction — unit-3 NFR Requirements started
- 2026-10-19T12:26:17Z — NFR Requirements stage started. FD analysis found two FD-internal conflicts to resolve: BR-9.1 vs BR-9.2 (sandbox env = unit-2 child_env which includes the LLM key by default, vs "no secrets enter the sandbox") and BR-1.3 per-step lifecycle vs Docker container startup cost. Repo has no CI workflows; FD BR-12.4 promises the Linux workflow ships with unit-3. Plan created at aidlc-docs/construction/plans/unit-3-nfr-requirements-plan.md with 6 open questions (NFR-1 secrets-in-sandbox, NFR-2 lifecycle, NFR-3 daemon transport, NFR-4 native kernel-feature strictness, NFR-5 toolchain delivery with network off, NFR-6 Windows CI).
- 2026-10-19T12:32:00Z — NFR-1 answered. User (raw): "I thought we decided this already! The pipeline.yaml steps get respective env sections with the env vars their corresponding steps can see". Follow-up (per-step env doesn't exist today; unit-2 shipped global env_allowlist): **A** — per-step `env:` mapping on StepConfig (VAR: value | null=inherit). Resolved: sandbox env = fixed safe base + declared env only; env_allowlist never leaks into sandbox; LLM key never auto-included inside; host-side steps keep child_env unless they declare env. Resolves BR-9.1/BR-9.2.
- 2026-10-19T12:34:00Z — NFR-2 answered: **A** — persistent per run. Docker: lazy container at first sandboxed exec, `docker exec` per request, destroyed at pipeline end + error paths; native: bwrap per request. Per-command statelessness preserved; lifecycle backend-internal. BR-1.3 amended (per-request exec, per-run container lifecycle).
- 2026-10-19T12:36:00Z — NFR-3 answered: **A** — `docker` CLI subprocess via `shutil.which("docker")`; CLI handles unix socket/npipe/WSL2/contexts; zero new runtime dependencies. Structured data via CLI output (create/start return codes + IDs, `docker inspect --format`).
- 2026-10-19T12:38:00Z — NFR-4 answered: **A** — tiered. bwrap + unprivileged user namespaces mandatory (fail fast with install instructions); Landlock best-effort (kernel ≥ 5.13, else loud one-time warning); seccomp via bwrap's built-in `--seccomp` filter, no libseccomp dependency.
- 2026-10-19T12:52:00Z — NFR-5 discussion. User (raw): "Let's stop and discuss - this is a significant architectural fork". Assistant decomposed the fork (provisioning source vs runtime policy; agent-vs-command asymmetry). User (raw): "The code could be anything - nodejs, react, C#, we're not platform-specific. So all the sandboxes need to be able to somehow access a working dev environment. We could give each step in pipeline.yaml a pre-command or hook which prepares everything and gives it to the sandbox" with `setup: npm i && npm run build` / `setup: dotnet build` examples.
- 2026-10-19T12:58:00Z — NFR-5 refined design agreed. User confirmed: (1) setup runs inside the backend environment, never host (ABI correctness); (2) separate provision container with network ON vs execution container `--network none`; (3) one pinned dev image (python+node+git) + per-pipeline `image:` override; (5) accepted risk: agent can mutate setup outputs in the rw workspace, containment still holds. Caching (point 4) open — user asked "why not just leverage docker's caching?".
- 2026-10-19T13:00:00Z — MAJOR DIRECTIVE. User (raw): "Also, drop native linux sandboxing from this intent (but keep the interface)". Docker becomes the only backend on all platforms; Sandbox interface retained as extension seam. Consequences: BR-3.2 removed; backend-selection simplifies (no `backend:` override knob); bwrap_argv/landlock_ruleset/seccomp_policy dropped; NFR-4 withdrawn; Linux CI = Docker-backend tests on ubuntu-latest. FD amendments to be applied to business-rules/domain-entities/business-logic-model during NFR artifact generation.
- 2026-10-19T13:06:00Z — NFR-5 caching answered. User (raw): "Ok, stamp-caching: skip on match, and a pipeline-level isolation.refresh (or CLI --refresh) flag forces re-provision." Docker builder layer-cache rejected (shadowing, fragile auto-staging, deps hidden in images); stamp = runtime analogue of layer caching, keyed by setup cmd + lockfile hashes, stored in state_dir. NFR-5 fully resolved.
- 2026-10-19T13:10:00Z — NFR-6 answered: **A** — add Windows CI job (windows runner with Docker Desktop) running Docker-backend integration tests; Linux job = Docker-backend tests on ubuntu-latest. All NFR open questions resolved (NFR-4 withdrawn per native-drop directive). Proceeding to FD amendments + NFR artifact generation.

## Construction — unit-3 NFR Requirements artifacts
- 2026-10-19T13:24:00Z — Generated `aidlc-docs/construction/unit-3/nfr-requirements/nfr-requirements.md` (NFR-3.1..NFR-3.10 + category dispositions + Security-baseline blocking-set dispositions) and `tech-stack-decisions.md` (TS-1..TS-9 + deferred items). Security-baseline compliance: no blocking findings.
- 2026-10-19T13:24:00Z — FD artifacts amended in place per NFR-stage decisions (user directives logged above): native backend dropped (BR-3/BR-4, domain-entities, business-logic-model), BR-1.3 persistent-per-run (NFR-2), BR-9 per-step env (NFR-1), new BR-13 setup hook (NFR-5), BR-12 CI ubuntu+windows (NFR-6), SECURITY-07 mapping updated. Amendment banner added to all three FD artifacts.
- 2026-10-19T13:24:00Z — Plan checkboxes complete. Awaiting user review/approval of NFR requirements.

## Construction — unit-3 NFR Requirements approved
- 2026-10-19T13:30:12Z — User approved NFR requirements; raw input: "approve and continue". Proceeding to Infrastructure Design.

## Construction — unit-3 Infrastructure Design started
- 2026-10-19T13:41:15Z — Started Infrastructure Design stage. Plan created at aidlc-docs/construction/plans/unit-3-infrastructure-design-plan.md (logical components listed; 7-category applicability analysis: Deployment PARTIAL, Compute YES, Storage YES, Messaging N/A, Networking YES, Monitoring PARTIAL, Shared YES). Repo confirmed PUBLIC (lukedawilson/agent-engine) — GHCR anonymous pulls viable.
- 2026-10-19T13:42:30Z — ID-1 dev image source: **A** — own agent-engine/dev image published to GHCR via CI, digest-pinned, rebuilt on toolchain bumps.
- 2026-10-19T13:43:45Z — ID-2 engine baseline: **A** — any compliant daemon with engine API version floor (≥1.43/Engine 24); Windows: OSType probe fails fast in Windows-containers mode with switch instructions.
- 2026-10-19T13:45:00Z — ID-3 state_dir: **A** — ~/.agent-engine/state (per-user); one stamp per setup key under state_dir/stamps/; manual CLI clean command; provision outputs stay in workspace.
- 2026-10-19T13:46:15Z — ID-4 resource caps: **A** — default caps on both containers (execution 4g/2cpu, provision 8g/4cpu), per-pipeline override via isolation section.
- 2026-10-19T13:48:00Z — ID-5 audit sink: **A** — JSONL at state_dir/sandbox-audit.jsonl (per-execution records) + console via existing logger; 5MB rotation with one rolled file; host-side only.
- 2026-10-19T13:49:30Z — ID-6 CI runners: **A** — GitHub-hosted ubuntu-latest + windows-latest; CI publishes dev image to GHCR and runs Docker-backend integration tests. All 6 ID questions answered; proceeding to artifact generation.

## Construction — unit-3 Infrastructure Design artifacts
- 2026-10-19T13:55:00Z — Generated infrastructure-design.md (component→infra mapping, category dispositions, engine baseline, image/supply chain, resource caps, storage layout, audit sink, container hardening flag table, CI, open CG considerations) and deployment-architecture.md (topology + runtime-sequence mermaid, per-OS environment matrices, fresh-machine steps, failure-mode table).
- 2026-10-19T13:55:00Z — shared-infrastructure.md warranted: dev image + GHCR registry + CI workflows + per-user state dir are repo-wide shared infra (units 1-2 had none). Created at aidlc-docs/construction/shared-infrastructure.md.
- 2026-10-19T13:55:00Z — Plan checkboxes complete. Awaiting user review/approval of infrastructure design.
- 2026-10-19T14:05:00Z — Change request during infra-design review. User raw: "Also need to provide proper setup instructions for the users' agents, since setup is more complex (e.g. on setting up the dev images, writing the pipeline.yaml file, etc.)". ID-7 answer **A**: user onboarding guide ships WITH the repo (docs/setup.md linked from README); outline fixed in infra design, written at Code Generation. Artifacts amended (infrastructure-design.md new deliverable section + outline; deployment-architecture.md points fail-fast messages at the guide).
- 2026-10-19T14:20:00Z — Change request during infra-design review. User: "does docker truly count as 'kernel-level isolation'?" then "Can we accurately call it kernel-level sandboxing?" Assistant answer: YES — kernel-level sandboxing is accurate (kernel enforces namespaces/cgroups/seccomp/caps); kernel-level isolation would overclaim (separate kernel = VM/gVisor class). ID-8 resolved: terminology amended to "kernel-level sandboxing" across construction docs + state; threat-model section added to infra design; inception-doc wording (requirements.md, unit-of-work.md, unit-4 doc) queued as deferred amendments.

## Construction — unit-3 Infrastructure Design approved
- 2026-10-19T14:08:00Z — User approved infrastructure design; raw input: "Approve and continue". Proceeding to Code Generation.

## Construction — unit-3 Code Generation Part 1 (planning)
- 2026-10-19T14:15:00Z — Code generation plan created at aidlc-docs/construction/plans/unit-3-code-generation-plan.md: 16 numbered TDD steps, story traceability (FR-2.1..2.6, NFR-3/4/6/7, BR-1..13), 8 locked key decisions (KD-1 single isolation.py module; KD-2 image digest bootstrap w/ AGENT_ENGINE_DEV_IMAGE override; KD-3 dual state dirs; KD-4 SDK terminal executor seam + per-run re-registration; KD-5 fake Sandbox in unit tests, marked docker integration; KD-6 --refresh/--clean-stamps; KD-7 root-in-container; KD-8 sleep infinity exec target). Files: created isolation.py + 3 test files + Dockerfile + 2 workflows + docs/setup.md + code/ summary; modified config/stages/agents/graph/cli + 6 test files + COMPAT-SHIMS. actions.py explicitly unchanged.
- 2026-10-19T14:15:00Z — Approval prompt presented to user for the code generation plan (Part 1). Waiting for explicit approval before writing any code.
- 2026-10-19T14:26:00Z — User response to code-generation plan approval (raw): "Get the docs ready for the agent-engine to implement, but do NOT write code." Directive: prepare implementation documentation as the handoff for a future implementing agent; NO code files written. Code execution deferred.

## Construction — unit-3 Code Generation docs handoff
- 2026-10-19T14:35:00Z — Implementation handoff spec created at aidlc-docs/construction/unit-3/code/implementation-spec.md (docs-first directive): exact isolation.py API surface (VOs, 9 pure functions, Sandbox ABC + DockerBackend, probe, audit/stamp helpers, constants incl. KD-2 digest bootstrap), 6 docker command templates (probe/ensure_image/exec-container/exec/provision/destroy incl. exit-124 timeout convention + /usr/bin/timeout requirement), config schema (IsolationConfig extra=forbid + StepConfig.env/setup), AE-SBX-001..012 error catalog pointing at docs/setup.md, SDK terminal seam (SandboxTerminalExecutor + per-run re-registration + COMPAT-SHIMS entry spec), Runtime/stages/cli wiring detail, ci.yml + publish-image.yml + Dockerfile specs, docs/setup.md 6-section outline, full test plan (unit/PBT/marked-docker/sdk-compat), guardrails. Plan file annotated with STATUS note (code execution deferred to implementing agent). No code files written.

## Construction — unit-3 loop-mechanics hardening (docs-first amendments)
- 2026-10-19T14:52:00Z — User intent (raw): "I don't want insurance, I want to be sure an agent won't break the loop mechanics mid-run, or start sandboxing before it has all the right setup etc."
- 2026-10-19T14:52:00Z — Q1 loop-mechanics exposure: **A** — (1) sandbox mount set = workspace ONLY (iso state dir unmounted: stamps/audit become host-only, unreachable); (2) PipelineConfig.state_dir default relocates to user-level ~/.agent-engine/runs/<pipeline-hash>/ (out of the mount entirely; explicit state_dir configs keep working). Remaining decisions pending: eager-vs-lazy startup setup; commit-action trusted hooksPath.
- 2026-10-19T14:55:00Z — Q2 startup setup: **A** — eager startup: probe → digest-verified image → create+start execution container → pre-provision every declared setup (stamp-cached, --refresh respected) → then build graph and run steps. Zero infra operations mid-run; mid-run failure = step result or loud daemon death.
- 2026-10-19T14:57:00Z — Q3 commit hooks: **A** — trusted commit action runs `git -c core.hooksPath=<agent-engine-managed trusted dir>`; FD BR-7 residual reclassified accepted→mitigated. All three hardening decisions made; applying one consistent amendment batch to implementation-spec.md, CG plan, FD/infra/NFR artifacts, and test plan.
- 2026-10-19T15:00:00Z — User requirement (raw): "Also, the plan needs to involve updating pipeline.yaml in this repo so it works with this Brave New World" — the repo's own pipeline must keep working under always-on sandboxing (state_dir relocation, per-step env/setup, git-mutation policy, sandboxed command steps). Adding pipeline.yaml migration to the plan + spec.

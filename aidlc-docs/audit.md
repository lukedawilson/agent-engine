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

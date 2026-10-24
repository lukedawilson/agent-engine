# Application Design Plan - Guardrails & Sandboxing

**Stage**: INCEPTION - Application Design
**Inputs**: requirements.md (approved), execution-plan.md (approved), reverse-engineering artifacts
**Scope note**: Domain Standards extension is blocking → this stage runs Domain Exposition before proposing component models, and Phase-2 Domain Validation at approval. `services.md` is generated as a **descent audit** (helper → VO → entity method → new entity → domain service → app service), not a service-layer proposal. No persistence abstractions (no Repository/DAO types).

## Design Plan Checklist

- [ ] Analyze requirements + RE artifacts for component boundaries
- [ ] Domain Exposition Q&A (questions below, inline chat per AGENTS.md override; answers written back here)
- [ ] Generate `components.md` - component definitions + high-level responsibilities
- [ ] Generate `component-methods.md` - method signatures (business rules in FD)
- [ ] Generate `services.md` - descent audit (Domain Standards Phase 2)
- [ ] Generate `component-dependency.md` - dependency matrix + communication patterns
- [ ] Generate `application-design.md` - consolidated
- [ ] Validate completeness + consistency (requirements traceability)

## Domain Exposition Questions (Phase 1)

### Q-AD1 - Component Identification: response-capture ownership (Unit 1)

The pipeline must capture the agent's final SDK response and produce the artifacts (summary + verdicts). Which component boundary?

- A) New component (`outputs.py`-style): capture + verdict parsing live together as the feedback domain
- B) Extend existing components: capture in `stages.py` Runtime, parsing stays in `verdicts.py`
- X) Other (describe)

[Answer]: A - new component (e.g. outputs.py): capture + verdict parsing together as the feedback domain

### Q-AD2 - Component Methods: inter-stage medium for findings

After capture, how do findings reach downstream agents (review/qa)?

- A) Pipeline writes the captured response to the existing artifact file path (`implementation-summary.md`) - swap the writer from agent to pipeline; `build_context` and file-based context stay as-is
- B) Pass findings in-memory via `LoopState`; drop file artifacts for summaries entirely
- X) Other (describe)

[Answer]: A - pipeline writes the captured response to the existing artifact path (implementation-summary.md); swap the writer agent→pipeline; build_context untouched

### Q-AD3 - Component Identification: tool-restriction config surface (Unit 2)

Where does per-agent tool restriction live once the SDK knobs are exposed?

- A) `.agent.md` frontmatter only (SDK-native: `tools`, `filter_tools_regex`, `include_default_tools`) - pipeline YAML stays config-light
- B) Also add per-step overrides in `pipeline.yaml`
- X) Other (describe)

[Answer]: A - .agent.md frontmatter only (SDK-native tools/filter_tools_regex/include_default_tools); pipeline YAML stays config-light

### Q-AD4 - Component Identification: isolation backend boundary (Unit 3)

Unit 3 sandboxes terminal tool + command steps behind the Docker Engine API. What's the component boundary?

- A) New `isolation` component: `IsolationBackend` protocol + `DockerBackend` implementation; stages request execution through it
- B) Fold docker-client usage directly into `Runtime`/stages (no separate protocol)
- X) Other (describe)

[Answer]: A - new isolation component. AMENDED (DDD rules): single concrete `Sandbox` type speaking the Docker Engine API - no protocol (single-impl interfaces forbidden); platform variance (daemon detection, mount translation, CRLF) is internal behavior; shared interface extracted only when a second backend (e.g. native Linux namespaces) is implemented.

### Q-AD5 - Design Patterns: isolation testability seam

How are container tests kept runnable without a running daemon?

- A) The `IsolationBackend` protocol is the seam - tests use a `FakeBackend`; real Docker covered by opt-in integration tests
- B) Tests require a real ephemeral container (CI provisioned)
- X) Other (describe)

[Answer]: AMENDED (DDD rules) - no FakeBackend protocol seam (no testability-driven structure): unit-test the pure parts (request building, result mapping, path translation); real Docker covered by opt-in integration tests.

### Q-AD6 - Component Dependencies: verdict parser shape

The captured-response parsing redesign is flagged for FD ("we've had bugs in this area"). At the component level:

- A) Parsing is a source-agnostic pure component: `parse(text) -> Verdict` - file and response are just inputs (PBT-friendly)
- B) Keep parsing embedded in stage logic, reading whichever source is configured
- X) Other (describe)

[Answer]: A, AMENDED (DDD rules) - source-agnostic pure parser returning a typed RESULT object: Verdict.from_text(text) -> Result[Verdict] with typed error codes (NO_VERDICT / AMBIGUOUS); no exceptions for expected conditions.

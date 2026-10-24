# Services - Descent Audit (Domain Standards Phase 2)

Per the Domain Standards extension and the loaded backend DDD rules (`coding-standards-ddd.yaml`), this file replaces the template's service-layer design. **Services are exceptions, not the default.** Every piece of new/changed logic is audited downward first: helper → value object → entity method → new entity → domain service → application service. No persistence abstractions (no Repository/DAO types).

## Descent Audit

| Logic | Placement | Rationale |
| --- | --- | --- |
| Parse verdict text (decoration-tolerant, last-line-wins) | **Value object** - `Verdict.from_text(text) -> Result[Verdict]` | Pure function of text; owns the verdict concept's creation rules; expected failure (no/ambiguous verdict) is a typed error code, not an exception; PBT-friendly |
| Capture agent final response → artifact + parsed verdict | **Value object** - `CapturedOutput.from_agent_result(...)` static constructor | Inputs and outputs belong to one aggregate → static constructing method per DDD descent; one caller (Runtime) means **no service** |
| Write captured text to artifact path, per-attempt hygiene | **Value object method** - `CapturedOutput.write(path)` | The entity handles its own persistence (no repository); attempt hygiene stays on the existing Runtime policy |
| Execute a command inside the boundary | **Concrete value object** - `Sandbox.run(request)` | Single Docker-Engine-API implementation → **no protocol** (single-impl interfaces forbidden); platform variance is internal behavior |
| Resolve the sandbox for the current config; fail fast when unavailable | **Static method** - `Sandbox.for_config(config)` | Constructing/transforming operation on the aggregate; startup misconfiguration → raise immediately (existing fail-fast policy) |
| Validate tool name at registration (collision, reserved) | **Entity invariant** - `ToolRegistry` | Belongs to the registry's integrity, checked at mutation |
| Agent frontmatter → SDK tool config wiring | **Entity** - `AgentDefinition` factory | Converts one definition form to another; fail-fast on unknown names |
| Route a step after a verdict (on_pass/on_fail/goto+retry) | **Entity method** - `Step.route(verdict)` | Routing rules are the step's own data |
| Attempt accounting + exhaustion | **Entity** - `Attempt` | Owns its counter and bound |

**Services identified (exceptions only):**

| Service | Kind | Purpose | Justification (per DDD rules) |
| --- | --- | --- | --- |
| Stages Runtime node functions | Application service (existing) | Step execution orchestration | Pre-existing; shared by every step kind; orchestrates aggregates without holding business rules |

**Zero new services.** Every candidate operation descended onto a value object or entity - the DDD rules' "one caller means no service" and "never lift an operation off its aggregate" applied throughout. No repository/DAO/DTO/service-layer scaffolding; no interfaces with single implementations; no testability-driven structure (no `FakeBackend` seam - pure parts are unit-tested directly, real Docker via opt-in integration tests).

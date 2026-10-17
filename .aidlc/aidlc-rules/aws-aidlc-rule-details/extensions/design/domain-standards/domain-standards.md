# Domain Standards

## Overview

**MANDATORY cross-cutting constraint on Application Design and Functional Design.**

This extension forces a two-phase domain design flow. The AI-DLC template's default path proposes components, services, and data structures first and questions them afterwards — which reliably produces anaemic domain models with service-layer scaffolding that must be rewritten later. This extension inverts that: the domain is exposed from the product requirements before any model is proposed, and every later proposal is validated against that exposed domain.

**Flow (enforced at both stages):**

1. **Load `coding-standards-ddd.yaml` BEFORE any model proposal.** The yaml is currently injected only at construction code generation — after the model already exists. Its descent rule, services-as-exceptions, domain-and-persistence rules, and forbidden patterns are the vocabulary of this extension and are required reading for every question drafted and every model proposed at Application Design and Functional Design.
2. **Phase 1 — Domain Exposition.** Run the exposition Q&A (DOMAIN-01) before proposing any domain model, component, service, or persistence structure (DOMAIN-02). Derive the proposed model from the answers (DOMAIN-03).
3. **Phase 2 — Domain Validation.** Validate the proposed model against the requirements and the standards (DOMAIN-04..08). Findings are blocking.

**Rationale (from this project's history):** the v0 application design needed a complete rework (revs 1–3 anaemic → rev 4 rich domain); `ChromeClassifier`/`ChromeRules` value objects were proposed where plain static helpers belonged; the Site/LiveSite split was found by the user, not the pipeline — the tension was latent in the requirements the whole time. Each failure shares one root cause: the pipeline proposed a structure instead of exposing the domain, then bent the requirements around the structure.

### Blocking Domain Standards Finding Behavior

1. On stage completion, all findings MUST be listed under the heading **Domain Standards Findings**, each with its rule ID and the offending design/quotation.
2. The completion message MUST NOT present a Continue option while unresolved findings exist — only Request Changes.
3. Findings are resolved by amending the design artifacts or the plan, not by adding justifications in chat.
4. Every finding, and its resolution, is logged in `audit.md`.
5. Where a rule targets something the unit does not have (e.g. no services exist to audit), the artifact states "N/A — <reason>" rather than omitting the section.

### Default Enforcement

All rules are blocking by default. Extension configuration in `aidlc-state.md` records enablement.

### Verification Criteria Format

All verification is judgment-based — reading the design and the questions as designs. There is no mechanical scan, and there must not be one: the failure mode this extension prevents is not the emission of literally banned tokens but the defaulting to anaemic structure and the stretching of domain vocabulary to dress it up. Each rule's Verification section lists the shapes to judge against, with the concrete abuse patterns that recur.

---

## Phase 1 — Domain Exposition

### DOMAIN-01 — Exposition Q&A derived from the requirements

The stage plan MUST contain an exposition question section, asked and answered BEFORE any model work. Every exposition question is derived from a specific product requirement.

**The six probe dimensions are a coverage checklist, not question text.** Each emitted question:

- cites the source requirement (e.g. "FR7's save"),
- names that requirement's own concepts in the requirement's own vocabulary,
- presents the concrete alternatives the requirement's wording leaves open.

A question that could appear verbatim in another project's plan is a blocking finding.

**Probe dimensions (cover each):**

1. **Concepts named** — what things does the requirement talk about, in the product's own words?
2. **State ownership** — which of those concepts own state, and what state?
3. **Runtime contexts** — where does that state live: build-time vs run-time, our box vs the customer's box? Which process writes it?
4. **Change-togetherness** — what changes together, what changes independently?
5. **Invariants and failure modes** — what must always be true, and what can go wrong?
6. **Actors** — who acts on each concept, and with what authority?

**Verification:** the plan's exposition section shows one or more questions per probe dimension, each citing its source requirement; the `[Answer]:` tags are answered before any model proposal; no question is project-agnostic boilerplate.

**Worked example (the Site/LiveSite lesson).** FR7: "save writes values.json and regenerates the static site in the same flow". A valid exposition question: *"FR7's save — where does the process that writes values.json and regenerates the page run? On the customer's deployed bundle (each edit writes and regenerates there), or on the builder (the builder owns regeneration even after export)? If it runs on the bundle, the builder never sees a save after export — the two sides have different state."* The generic form — "Which runtime contexts does the saved state live in?" — fails: it names no requirement, no concept, no alternative.

### DOMAIN-02 — No premature proposals

No domain-model, component, service, or persistence questions or proposals may appear in the plan before the exposition Q&A is answered. Component/service questions are Phase-2 material: they validate an exposed domain, they do not create one.

**Verification:** the plan's question ordering shows exposition first; any model/component/service proposal placed before the answered exposition is a blocking finding.

### DOMAIN-03 — Answer-derived model

The proposed domain model is derived from the exposition answers. The design artifact carries a trace list: every domain concept → the exposition answer it came from. Concepts without a trace are either removed or explicitly labelled infrastructure — and infrastructure is never presented as domain. Coined labels that name no requirement concept ("the X model") are not traces.

**Verification:** the trace list exists in the design artifact; every concept traces to an exposition answer or is labelled; no untraced concept is presented as domain.

---

## Phase 2 — Domain Validation

### DOMAIN-04 — Requirements traceability

The proposed model covers the requirements: every requirement has a place in the model where its work happens. A requirement whose concepts appear nowhere is either given a home or recorded as an explicit, reasoned deferral — silently dropping it is a blocking finding.

**Verification:** the artifact carries a per-requirement coverage list (requirement → model home, or explicit deferral with reason).

### DOMAIN-05 — Rich domain model

The model is judged as a design, not a vocabulary. Blocking shapes:

- **Delegating entities** — an entity whose methods all forward to a service or data-access type, i.e. a behaviourless data holder wearing an entity name.
- **Service-named value objects** — value objects whose names do a service's job (`ChromeClassifier`, `ChromeRules`) where the behaviour is plain stateless helpers, or whose names were chosen to dress up an anaemic design.
- **Coined "the X model/pattern" labels** for loose ideas named on the spot rather than real concepts.
- **Per-endpoint domain services** — a service that exists solely because a use case needed a home, when the behaviour belongs on an entity.
- **Behaviourless aggregates** — an aggregate with state but no behaviour of its own is a finding, not a default.

**Verification:** entities and value objects carry behaviour; any entity with no behaviour is a blocking finding; none of the named abuse shapes appear.

### DOMAIN-06 — Descent audit

Every behaviour is assigned by the descent order and the assignment is shown:

(0) plain static helper → (1) value object → (2) method on an existing entity → (3) new entity → (4) domain service (stateless, genuinely cross-entity) → (5) application service (shared by two or more entry points).

The artifact carries a descent-audit section listing behaviours and their placement step. A behaviour that cannot be placed is a blocking finding, not a service.

**Verification:** the audit section exists; every behaviour has a step; every service names the step that justified it.

### DOMAIN-07 — Services as exceptions

Each service states its justification: which entry points share it, or which cross-entity operation it carries. A 1:1 controller→aggregate delegate does not exist. Names like Manager/Helper/Orchestrator/Facade are banned — but the check is judgment: a service is a finding when its shape is anaemic, whatever it is called.

**Verification:** every service has a stated justification; no service duplicates a single aggregate's surface for a single endpoint.

### DOMAIN-08 — No persistence abstractions

No Repository/DAO/store/unit-of-work types, no predominantly-Load/Save/Query types separate from an entity. Persistence is a method on the aggregate that owns the state. The code-generation plan's Repository Layer steps are marked N/A, not generated.

**Verification:** no persistence-abstraction type appears in the design or the code-generation plan; persistence appears as aggregate methods.

---

# Superseded template steps

Where the AWS template conflicts, this extension supersedes it:

1. **Application Design's "Service Layer Design" question category** is replaced by the descent audit (DOMAIN-06/07). "Which services do we need" is never a question; the descent audit determines which services survive.
2. **Application Design's `services.md` artifact** becomes the descent audit: service definitions with descent justifications — empty when no service survives, and that is a good outcome.
3. **Code Generation's Repository Layer steps** (generation, unit testing, summary) are marked N/A under DOMAIN-08.

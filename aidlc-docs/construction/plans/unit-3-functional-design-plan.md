# Functional Design Plan — unit-3 (kernel isolation, opt-in)

## Unit Context (from unit-of-work.md)

Opt-in container sandboxing of the agent-influence channels (the `terminal` tool + command steps), via the Docker Engine API. Action steps, LangGraph runtime, LLM calls, viz server, and commit stay host-side. Fail-fast when isolation is requested but no runtime is available. Scope: FR-2.1–FR-2.6, NFR-3/4/7.

## FD Steps

- [ ] Analyze unit-3 context and story-map assignments (FR-2.1–FR-2.6)
- [ ] Domain exposition (DOMAIN-01 — six probe dimensions, answered)
- [ ] Resolve FD open questions (below)
- [ ] Generate `aidlc-docs/construction/unit-3/functional-design/business-logic-model.md`
- [ ] Generate `aidlc-docs/construction/unit-3/functional-design/business-rules.md`
- [ ] Generate `aidlc-docs/construction/unit-3/functional-design/domain-entities.md`
- [ ] Validate against DDD rules (descent audit; no protocols; no single-impl interfaces)
- [ ] Security-baseline compliance check (least privilege, image pinning, credential hygiene, audit)
- [ ] Identify PBT properties (PBT-03) for the new pure functions (config serialisation, request/result round-trip)

## Domain Exposition (DOMAIN-01)

### Dimension 1 — Concepts named

- **Source**: FR-2.1 "isolation boundary" around the "agent `terminal` tool" and "command steps"; FR-2.2 "Docker Engine API", "Linux dev image", "bind mounts".
- **Proposed**: the **Sandbox** (the isolation boundary that owns a single sandboxed execution), the **isolation runtime** (Docker Engine API + per-platform adaptation), and the **isolation profile** (what is blocked — network, writable paths, capabilities). The "host-side" set (action steps, LangGraph, LLM, viz, commit) is the trusted complement — not a domain object.

### Dimension 2 — State ownership

- **Source**: FR-2.2 "bind mounts carry workspace + state_dir"; FR-2.5 "profile defaults".
- **Proposed**: the Sandbox owns its own execution context (request → result). `PipelineConfig` owns the opt-in `isolation:` declaration (image, profile). The Docker daemon owns the real container state. The pipeline owns workspace/state_dir (bind-mounted, shared with the sandbox).

### Dimension 3 — Runtime contexts

- **Source**: FR-2.3 "fail fast, refuse to run"; FR-2.1 per-step execution.
- **Proposed**: **load time** — config validation + runtime detection (daemon reachability, image presence), fail-fast. **run time** — per-step container create/exec/stop for the terminal tool and command steps. The host pipeline process spawns containers; the container writes through the bind mounts.

### Dimension 4 — Change-togetherness

- **Source**: FR-2.2 "concrete runtime chosen per platform"; FR-2.4 "daemon detection, mount-path translation, CRLF".
- **Proposed**: the Docker Engine API client + per-platform adaptation are one cohesive implementation (one `Sandbox` type). The profile defaults (FR-2.5) are data, changing independently of the mechanism. A native-Linux backend (if any) is a separate, later change.

### Dimension 5 — Invariants & failure modes

- **Source**: FR-2.3 "no silent fallback to unsandboxed execution"; FR-2.1 "stay host-side".
- **Proposed** invariants: when isolation is requested, the terminal tool + command steps run inside the boundary and host-side steps never enter it. Failure modes: daemon unavailable, image pull failure, mount failure — all loud, none a silent unsandboxed fallback.

### Dimension 6 — Actors

- **Source**: FR-2.1 (agent vs host); FR-2.6 "host-side native git".
- **Proposed**: the **agent** (untrusted — runs inside). The **pipeline author** (trusted — opts in, picks the image/profile). The **Docker daemon** (executes the sandbox). The **host** (trusted — LangGraph, action steps, commit, viz).

## Open Functional Questions

### Question FD-1 (FR-2.5): default isolation profile

FR-2.5 defers "what the sandbox blocks by default (network, file paths, capabilities)" to FD. The default profile is what a user gets with a minimal `isolation` opt-in.

A) **Network-egress blocked + writes restricted to the bind-mounted workspace/state_dir** — most conservative; the sandbox can read its toolchain image and write only into the mounted workspace (recommended)

B) **Network-egress blocked only** — filesystem writes unrestricted within the container (still disposable, but the sandbox can scribble anywhere inside it)

C) **Nothing blocked by default** — the profile is fully opt-in per-restriction

X) Other

[Answer]: 

---

### Question FD-2 (open question): Linux backend — Docker vs native namespace isolation

Requirements.md records this open question. macOS/Windows must be Docker-based; Linux uniquely could isolate natively (bubblewrap/Landlock/seccomp) without a daemon.

A) **Docker-only on all three platforms** — one concrete `Sandbox`, no interface extracted yet (DDD last-responsible-moment: extract only when a native backend actually lands) (recommended)

B) **Docker on macOS/Windows + native namespace isolation on Linux** — no daemon needed on Linux, but two backends force the interface extraction now

X) Other

[Answer]: 

---

### Question FD-3 (FR-2.1): confirm the isolation boundary

A) **`terminal` tool + command steps** inside; action steps, LangGraph runtime, LLM calls, viz server, commit stay host-side (per FR-2.1 as written) (recommended)

B) Some other surface (describe)

X) Other

[Answer]: 

---

### Question FD-4 (FR-2.2 / FR-2.5): opt-in config shape

A) **`isolation:` block** — e.g. `isolation: { image: "ghcr.io/...", profile: default }`; omitting it (or `isolation: false`) keeps today's unsandboxed behavior (recommended)

B) **Boolean flag + separate profile section** — `isolation: true` plus a top-level `sandbox_profile:` key

X) Other

[Answer]: 

---

### Question FD-5 (NFR-7): testability without a running container

NFR-7 requires the backend be testable without Docker, with no tests that silently skip when Docker is absent.

A) **Fake runtime speaking the same `Sandbox` surface** — unit tests drive a stub; one opt-in integration test (marked, real Docker) runs when a daemon is present (recommended)

B) **Fake Docker Engine API HTTP client** — mock at the HTTP layer

X) Other

[Answer]: 

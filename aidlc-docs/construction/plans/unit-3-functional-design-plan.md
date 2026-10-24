# Functional Design Plan - unit-3 (kernel-level sandboxing, always-on)

> **Amended 2026-10-19 (FD-4, user directive):** isolation is **always-on**, not opt-in - the title and context above originally read "opt-in". No usable runtime ⇒ fail fast on every run. The `isolation:` section configures the always-on sandbox; it can never disable it.

## Unit Context (from unit-of-work.md)

**Always-on** sandboxing (amended) of the agent-influence channels (the `terminal` tool + command steps), via the `Sandbox` surface: Docker backend on macOS/Windows, native (bubblewrap/Landlock/seccomp) backend on Linux. Action steps, LangGraph runtime, LLM calls, viz server, and commit stay host-side. Fail-fast whenever no usable runtime is available. Scope: FR-2.1–FR-2.6, NFR-3/4/7.

## FD Steps

- [x] Analyze unit-3 context and story-map assignments (FR-2.1–FR-2.6)
- [x] Domain exposition (DOMAIN-01 - six probe dimensions, answered)
- [x] Resolve FD open questions (below)
- [x] Generate `aidlc-docs/construction/unit-3/functional-design/business-logic-model.md`
- [x] Generate `aidlc-docs/construction/unit-3/functional-design/business-rules.md`
- [x] Generate `aidlc-docs/construction/unit-3/functional-design/domain-entities.md`
- [x] Validate against DDD rules (descent audit; no protocols; no single-impl interfaces)
- [x] Security-baseline compliance check (least privilege, image pinning, credential hygiene, audit)
- [x] Identify PBT properties (PBT-03) for the new pure functions (config serialisation, request/result round-trip)

## Domain Exposition (DOMAIN-01)

### Dimension 1 - Concepts named

- **Source**: FR-2.1 "isolation boundary" around the "agent `terminal` tool" and "command steps"; FR-2.2 "Docker Engine API", "Linux dev image", "bind mounts".
- **Proposed**: the **Sandbox** (the isolation boundary that owns a single sandboxed execution), the **isolation runtime** (Docker Engine API + per-platform adaptation), and the **isolation profile** (what is blocked - network, writable paths, capabilities). The "host-side" set (action steps, LangGraph, LLM, viz, commit) is the trusted complement - not a domain object.

### Dimension 2 - State ownership

- **Source**: FR-2.2 "bind mounts carry workspace + state_dir"; FR-2.5 "profile defaults".
- **Proposed**: the Sandbox owns its own execution context (request → result). `PipelineConfig` owns the opt-in `isolation:` declaration (image, profile). The Docker daemon owns the real container state. The pipeline owns workspace/state_dir (bind-mounted, shared with the sandbox).

### Dimension 3 - Runtime contexts

- **Source**: FR-2.3 "fail fast, refuse to run"; FR-2.1 per-step execution.
- **Proposed**: **load time** - config validation + runtime detection (daemon reachability, image presence), fail-fast. **run time** - per-step container create/exec/stop for the terminal tool and command steps. The host pipeline process spawns containers; the container writes through the bind mounts.

### Dimension 4 - Change-togetherness

- **Source**: FR-2.2 "concrete runtime chosen per platform"; FR-2.4 "daemon detection, mount-path translation, CRLF".
- **Proposed**: the Docker Engine API client + per-platform adaptation are one cohesive implementation (one `Sandbox` type). The profile defaults (FR-2.5) are data, changing independently of the mechanism. A native-Linux backend (if any) is a separate, later change.

### Dimension 5 - Invariants & failure modes

- **Source**: FR-2.3 "no silent fallback to unsandboxed execution"; FR-2.1 "stay host-side".
- **Proposed** invariants: when isolation is requested, the terminal tool + command steps run inside the boundary and host-side steps never enter it. Failure modes: daemon unavailable, image pull failure, mount failure - all loud, none a silent unsandboxed fallback.

### Dimension 6 - Actors

- **Source**: FR-2.1 (agent vs host); FR-2.6 "host-side native git".
- **Proposed**: the **agent** (untrusted - runs inside). The **pipeline author** (trusted - opts in, picks the image/profile). The **Docker daemon** (executes the sandbox). The **host** (trusted - LangGraph, action steps, commit, viz).

## Open Functional Questions

### Question FD-1 (FR-2.5): default isolation profile

FR-2.5 defers "what the sandbox blocks by default (network, file paths, capabilities)" to FD. The default profile is what a user gets with a minimal `isolation` opt-in.

A) **Network-egress blocked + writes restricted to the bind-mounted workspace/state_dir** - most conservative; the sandbox can read its toolchain image and write only into the mounted workspace (recommended)

B) **Network-egress blocked only** - filesystem writes unrestricted within the container (still disposable, but the sandbox can scribble anywhere inside it)

C) **Nothing blocked by default** - the profile is fully opt-in per-restriction

X) Other

[Answer]: A - network-egress blocked + writes restricted to the bind-mounted workspace/state_dir (most conservative default)

---

### Question FD-2 (open question): Linux backend - Docker vs native namespace isolation

Requirements.md records this open question. macOS/Windows must be Docker-based; Linux uniquely could isolate natively (bubblewrap/Landlock/seccomp) without a daemon.

A) **Docker-only on all three platforms** - one concrete `Sandbox`, no interface extracted yet (DDD last-responsible-moment: extract only when a native backend actually lands) (recommended)

B) **Docker on macOS/Windows + native namespace isolation on Linux** - no daemon needed on Linux, but two backends force the interface extraction now

X) Other

[Answer]: B - Docker on macOS/Windows + native namespace isolation on Linux. Two backends ⇒ the shared Sandbox interface is extracted now (second implementation = last responsible moment per DDD). FR-2.2 scope amendment required: the abstraction is the Sandbox surface (not the Docker Engine API per se); the Docker Engine API remains the macOS/Windows backend. See FD-2b follow-up.

### FD-2 constraint (user-raised): Linux-side testability without a Linux box

- **Pure/translation logic** (profile → bwrap argv, profile → Docker create payload, mount-path translation, seccomp/Landlock rule serialisation, backend selection) is platform-independent and unit-tested everywhere - this is the bulk of NFR-7.
- **Native-backend integration tests** (real isolation) run on a **GitHub Actions Linux runner** (opt-in, marked; userns/Landlock available; on ubuntu-24.04 a `sysctl kernel.apparmor_restrict_unprivileged_userns=0` setup step may be needed) and/or an optional **local lima VM**.
- **macOS dev loop** (self-hosted agent) exercises the Docker backend locally; the native backend is validated in CI.
- **Backend selection** (native on Linux when available, fail-fast otherwise) is itself unit-tested via a fake availability probe - no Linux kernel required.
- CI workflow for the Linux integration tests is delivered as part of unit-3 (code-generation / build-and-test plan).

### Question FD-2b (follow-up): native backend toolchain source

FR-2.2 says "image-defined toolchain", which holds for the Docker backend but not obviously for the native one.

A) **Host toolchain inside namespaces** - bwrap read-only bind of the host toolchain (/usr etc.), tmpfs scratch, read-write bind of workspace/state_dir, Landlock + seccomp. No image at all on Linux (recommended)

B) **Image rootfs everywhere** - pull/extract the same Linux dev image on Linux and pivot into its rootfs; preserves image-defined toolchain semantics on all platforms

X) Other

[Answer]: A - host toolchain inside namespaces; no image on Linux (matches the no-daemon motivation).

### Question FD-2c (follow-up): Linux availability failure mode

A) **Native-only on Linux, fail fast** - bwrap/kernel features unusable ⇒ fail fast, refuse to run; explicit backend selection in config for users who want Docker on Linux (recommended)

B) **Native-first, Docker fallback** - prefer native; if unusable and a daemon is present, use Docker; fail fast only when neither is usable

X) Other

[Answer]: A - native-only on Linux, fail fast. (Implies an explicit backend-selection knob in config - feeds FD-4.)

---

### Question FD-3 (FR-2.1): confirm the isolation boundary

A) **`terminal` tool + command steps** inside; action steps, LangGraph runtime, LLM calls, viz server, commit stay host-side (per FR-2.1 as written) (recommended)

B) Some other surface (describe)

X) Other

[Answer]: A confirmed with a refinement (see FD-3b/3c): the `commit` **action** stays host-side (FR-2.6 unchanged); the NEW requirement is that agents must not be able to commit from inside the sandbox unless the pipeline author allows it (FD-3c).

### Question FD-3c (new, from FD-3b): agent-initiated git mutations inside the sandbox

The sandboxed terminal tool + command steps see the mounted workspace including `.git/`. Block agent-initiated repo mutations by default, with an author-controlled allow.

A) **Block all repo-mutating git operations by default** - commit, push, reset, branch/tag create/delete, stash, merge, rebase, worktree add …; reads (status/log/diff) always allowed; one profile knob re-allows mutations per-pipeline. Most thorough - partial blocking invites bypass (recommended)

B) **Block `commit` only** by default (push already dies on the network-off default); other mutations allowed; one knob re-allows commit

X) Other

[Answer]: A - block all repo-mutating git operations by default (commit, push, reset, branch/tag create/delete, stash, merge, rebase, worktree add …); reads always allowed; one profile knob re-allows mutations per-pipeline.

---

### Question FD-4 (FR-2.2 / FR-2.5): config shape

**Superseded by the always-on directive (user, 2026-10-19).** Isolation is mandatory, not opt-in - the original opt-in shapes (A/B below) are void. The `isolation:` section, if any, is *configuration* of the always-on sandbox, never a way to disable it.

~~A) **`isolation:` block** - e.g. `isolation: { image: "ghcr.io/...", profile: default }`; omitting it (or `isolation: false`) keeps today's unsandboxed behavior (recommended)~~

~~B) **Boolean flag + separate profile section** - `isolation: true` plus a top-level `sandbox_profile:` key~~

X) Other

[Answer]: Always-on (see FD-4b).

### Question FD-4b (re-posed for always-on): does the always-on sandbox config section carry opinionated defaults, or must every pipeline declare it?

A) **Optional `isolation:` section with opinionated defaults** - default profile = FD-1 answer (network-off + write-restricted + git-mutations-blocked), default image pinned by the harness, backend auto-detected with an override knob (FD-2c). Minimal pipelines need no section; the sandbox is active regardless. (recommended)

B) **Mandatory `isolation:` section** - every pipeline must declare the section explicitly; fail fast on missing. No silent defaults.

X) Other

[Answer]: A - optional `isolation:` section with opinionated defaults (default profile = FD-1 answer, default image pinned, backend auto-detected with override knob); the sandbox is active regardless of whether the section is present.

---

### Question FD-5 (NFR-7): testability without a running container

NFR-7 requires the backend be testable without Docker, with no tests that silently skip when Docker is absent.

A) **Fake runtime speaking the same `Sandbox` surface** - unit tests drive a stub; one opt-in integration test (marked, real Docker) runs when a daemon is present (recommended)

B) **Fake Docker Engine API HTTP client** - mock at the HTTP layer

X) Other

[Answer]: A - fake at the Sandbox interface level (the extracted interface from FD-2 gives the fake its shape); pure translation logic tested everywhere; real-backend integration tests marked and opt-in (Docker: any machine with a daemon; native namespace: CI Linux runner or lima VM), never silently skipped.

# Plan 023: Sandbox browser rendering: probe finder, Chromium sandbox, image fonts

- Status: Ready (all decisions made, all steps specified; fix 3 shipped. The 2a host-side milestone gate is deliberately outside the ready scope, see "Current state".)
- Repos affected: agent-engine (this repo), yosk-cms (cross-repo)
- Source: QA report verification session. All environment claims reproduced by hand in live sandbox container fd423aa738a2 (dev-dotnet:10.0, dbc882ac8fdf).

## Background (condensed evidence)

The yosk-cms render_check flow dies in the agent-engine sandbox with two stacked
environment failures, neither caused by new code:

1. **Probe finder gap**: `qa/probe.mjs` `findHeadlessShell` only accepts
   `chrome-headless-shell-mac-*` and `chrome-linux` layouts; the installed
   `chromium_headless_shell-1248/chrome-headless-shell-linux-arm64/` layout is
   skipped, so probe dies with "no chromium headless shell found".
2. **Skia crash on the coming-soon page**: Chromium 156 (playwright revision
   1248) aborts with `FATAL:third_party/skia/src/ports/SkFontMgr_FontConfigInterface.cpp:163`
   `Not implemented.` The stub at that line is `SK_ABORT` inside
   `SkFontMgr::countFamilies()` (skia chrome/m156, the exact revision Chromium
   156 pins). Trigger bisected to a single fact: **an unstyled text-entry form
   control** (`<input type="text">`, `<textarea>`, `<select>` with options).
   Its intrinsic width is computed from control-font metrics; with no font
   resolvable in this fontless image, that path asks the font system to
   enumerate families and lands on the stub. An explicit CSS `width`
   (e.g. `width:100%`) bypasses the sizing path and fixes the full page with
   zero fonts present. The coming-soon page's 17 inputs are unstyled because
   its stylesheet `coming-soon.desktop.css` 404s in the sandbox (builder never
   emitted the asset); the home page survives because hello-elementor's
   reset.css (fetched live; container has network) sets `width:100%`.
3. **No font ever resolves in this image**: no fontconfig config, no fonts,
   and fontconfig is statically compiled into the chrome-headless-shell binary
   (`default config` string is in the binary; no fontconfig .so is ever mapped
   per /proc maps). All text renders zero-width (invisible). The QA report's
   stale-libfontconfig-ABI mechanism is therefore wrong; the real mechanism is
   the missing config+fonts plus the hard Skia stub.

## Decisions (Luke, 2026-10-24)

1. Finder-gap fix: agreed.
2. Sandbox enablement AND mount-vector fix: do both.
3. Chromium-bug determination answered inline below; add fontconfig etc. to the
   dev-dotnet image, done inline (exact diff in Fix 3).
4. (Explanatory item; no action.)
5. Verification methodology: agreed; used verbatim as acceptance criteria.

## Current state (2026-10-24)

- **DONE: Fix 3.** `Dockerfile.dotnet` changed, image rebuilt and verified
  locally (bare input renders, text 32 px). Committed to main as `7d8d802`
  (`fix(dev-dotnet): add fontconfig and fonts`). Publishing is CI's job:
  `publish-image.yml` (trigger: push to main touching `Dockerfile.dotnet`)
  builds linux/amd64 + linux/arm64 and pushes `dev-dotnet:10.0` with the
  workflow's `GITHUB_TOKEN` (`packages: write`). Local `docker push` is NOT a
  publish path: the local ghcr credential is the gh OAuth token (no
  `write:packages` scope; registry rejects push with permission_denied), and a
  local build is single-arch and would clobber the CI multi-arch manifest.
- **READY TO IMPLEMENT:** Fix 1, Fix 2a (profile + payload plumbing + unit
  tests), Fix 2b, Fix 2c Phase A, Follow-ups.
- **EXCLUDED (the final gate):** Fix 2a's milestone gate (launch a real
  container with the new profile; `unshare(CLONE_NEWUSER)` returns 0) and
  Fix 2b's milestone gate (renderer `Seccomp: 2`, `NoNewPrivs: 1` under
  `chromiumSandbox: true`). These need docker on the host side: sandboxes have
  no docker socket, and this is the code that creates the containers the
  executing loop's own steps run in, so the loop cannot verify its own launch
  mechanism (a bad profile bricks every subsequent step's container). 2b must
  NOT land until the gate passes, or every probe launch dies at the zygote.

## Is this a Chromium bug?

Yes, narrowly: a hard-coded `SK_ABORT("Not implemented.")` is reachable from
spec-legal content (an `<input>` with `width:auto`) in a legitimate environment
(a Linux system with no fonts installed). Crashing instead of degrading is a
bug; the deeper defect is that the enumeration stub exists on a path that is
reachable when matching fails. It is unreachable on any normal Linux desktop
(fontconfig config + fonts are universal there), which is why it has never
bitten anyone. We are not filing upstream; the fix is environment-side (fonts
in the image) plus a cheap probe preflight (see Follow-ups). Belt and braces:
the width-CSS knowledge stays as diagnostic aid.

## Fix 1: probe finder accepts the linux layout (yosk-cms)

File: `qa/probe.mjs`, `findHeadlessShell` (~line 100). One-line pattern change:

```diff
-            // mac layout:  chrome-headless-shell-mac-arm64/chrome-headless-shell
-            // linux layout: chrome-linux/chrome-headless-shell
+            // layouts: chrome-headless-shell-<platform>-<arch>/chrome-headless-shell
+            // (mac-arm64, mac-x64, linux-arm64, linux-x64) plus chrome-linux/...
             const exe = join(base, sub, 'chrome-headless-shell');
-            if ((sub.startsWith('chrome-headless-shell-mac') || sub === 'chrome-linux') && existsSync(exe)) return exe;
+            if ((sub.startsWith('chrome-headless-shell') || sub === 'chrome-linux') && existsSync(exe)) return exe;
```

Note: `resolveChromium` already honors `CHROME_BIN` first (probe.mjs line 112),
so the finder is only the fallback; this change makes the fallback correct.

Verification: from the sandbox, `node qa/probe.mjs <served-url> qa/invariants.json --out /tmp/result.json`
with no `CHROME_BIN` set must resolve
`qa/.browsers/chromium_headless_shell-1248/chrome-headless-shell-linux-arm64/chrome-headless-shell`
and run.

## Fix 2: turn the Chromium sandbox back on, and close the mount vector

Playwright already passes `--no-sandbox` by default
(`if (options.chromiumSandbox !== true) chromeArguments.push('--no-sandbox')`
in both launchers of playwright-core 1.64), so render_check has been executing
untrusted page JS (including live third-party assets) unsandboxed since day
one. The Chromium sandbox is currently impossible in the container:
`unshare(CLONE_NEWUSER)` returns EPERM at the container security layer
(`max_user_namespaces` is fine; the engine passes no custom seccomp profile, so
Docker's default seccomp is the blocker).

### 2a. Engine: allow the namespace sandbox (agent-engine, this repo)

- Add a seccomp profile to the repo (e.g.
  `src/agentic_dev_loop/engine/seccomp/chromium-userns.json`), based on
  Docker's default profile plus an allowlist for the userns syscalls Chrome's
  namespace sandbox needs. Candidate set: `unshare`, `clone`/`clone3` with
  `CLONE_NEWUSER|CLONE_NEWNS|CLONE_NEWPID|CLONE_NEWNET|CLONE_NEWUTS|CLONE_NEWIPC`.
  Final set to be determined empirically against the live sandbox.
- `docker_create_payload` (isolation.py ~line 450): accept an optional
  `seccomp_profile` and emit
  `--security-opt seccomp=<profile>` when set. Plumb it through the run config
  for the stage(s) that run render_check.
- Milestone gate: with the profile active, `unshare(CLONE_NEWUSER)` in the
  container must return 0.

Execution split: the loop can write the profile JSON, the payload plumbing,
and unit tests for payload assembly (pure string construction, no docker
needed). The milestone gate is host-side work only (see Current state).

### 2b. Probe: request the sandbox (yosk-cms)

File: `qa/probe.mjs` (~line 144):

```diff
-    const browser = await chromium.launch({ executablePath, headless: true });
+    const browser = await chromium.launch({ executablePath, headless: true, chromiumSandbox: true });
```

Landing order matters: 2a (engine profile) must land and ship before 2b, or
launch dies at the zygote with "No usable sandbox!". Consider an opt-out env
(e.g. `PROBE_DISABLE_SANDBOX`) for legacy environments; default stays on.

Milestone gate: in the sandbox, renderer processes must show
`Seccomp: 2` (filter) and `NoNewPrivs: 1` in `/proc/<pid>/status`. This gate is
part of the excluded final gate.

### 2c. Mount vector

The probe already writes nothing into the workspace mount: `RenderCheckRunner`
passes `--out <tmp>/result.json` under `Path.GetTempPath()` (tmpfs), and the
probe only reads from the workspace. Two layers, both in this plan:

- **Phase A (primary containment)**: the Chromium sandbox itself. A sandboxed
  renderer gets seccomp-filtered syscalls and cannot write into the rw
  workspace bind; page-content compromise stays inside the renderer.
- **Phase B (defense in depth)**: a dedicated read-only-workspace mode. Add
  `workspace_ro` support to the engine payload (`-v {workspace}:{workspace}:ro`,
  keeping /tmp tmpfs rw) and run render_check in a dedicated container with the
  workspace mounted read-only. This requires an orchestration change on the
  yosk side (spawn a second container instead of shelling out in the
  construction container) and is the larger half; it can follow Phase A without
  blocking it.

Fallback if 2a proves infeasible (profile cannot be made to work with
`--read-only --cap-drop ALL`): stay unsandboxed but ship Phase B first and
document the residual risk explicitly in both repos.

## Fix 3: fonts and fontconfig in the dev-dotnet image (agent-engine, this repo)

Applied inline (not as a plan work item). Exact change to `Dockerfile.dotnet`:

```diff
 RUN apt-get update && apt-get install -y --no-install-recommends \
         git nodejs npm coreutils ca-certificates curl \
         libicu76 libstdc++6 jq unzip lsof \
+        fontconfig fontconfig-config fonts-liberation \
+    && fc-cache -f \
     && rm -rf /var/lib/apt/lists/*
```

Rationale: `fontconfig-config` provides `/etc/fonts/fonts.conf` (which the
in-binary fontconfig reads by default); `fonts-liberation` provides
Liberation Sans, the Arial-metric-compatible match for the control font
`-webkit-small-control` and for general fallback. This fixes both the
unstyled-control crash and the zero-width invisible text.

Applied and verified 2026-10-24: image rebuilt locally as
`ghcr.io/lukedawilson/agentic-dev-loop/dev-dotnet:10.0`; `fc-list` lists 12
Liberation fonts; decisive repro on the new image: bare `<input type="text">`
renders (previously a deterministic crash) and span text width measures 32 px
(previously 0 px). Fix 3 is PROVEN. Committed to main as `7d8d802`; the
`publish-image.yml` workflow (`GITHUB_TOKEN`, `packages: write`, multi-arch
amd64+arm64) is the publisher for `dev-dotnet:10.0`.

## Fix 5: verification and acceptance criteria

| # | Check | Pass condition | Status |
|---|-------|----------------|--------|
| 1 | Finder | probe resolves the linux-arm64 layout without `CHROME_BIN` | pending |
| 2 | Crash repro | bare `<input type="text">` via playwright still crashes on the OLD image (regression control) | PASS (old image, many times) |
| 3 | Crash fixed | bare `<input type="text">` does NOT crash on the NEW image | PASS (local build) |
| 4 | Text visible | span width measurements > 0 px on the NEW image (all four font families) | PASS (32 px; four-family sweep not re-run on new image) |
| 5 | Sandbox on | `/proc/<pid>/status` shows `Seccomp: 2`, `NoNewPrivs: 1` for renderer processes | pending (excluded gate) |
| 6 | Userns gate | `unshare(CLONE_NEWUSER)` returns 0 in the sandbox with the new profile | pending (excluded gate) |
| 7 | End to end | render_check on the coming-soon page returns PASS/FAIL verdicts (no ExportFailed) and its screenshot contains visible text | pending |

Checks 2-4 use the established playwright `setContent` harness (executablePath:
CHROME_BIN, LD_LIBRARY_PATH: syslibs). Check 7 additionally needs the builder
to serve the page; the missing `coming-soon.desktop.css` asset (below) does not
block the verdict, only the styling.

## Follow-ups (separate tickets, not in this plan)

1. **yosk-cms builder**: `coming-soon.desktop.css` is referenced by the served
   page but was never emitted by the builder (404 in sandbox). That is why
   this page's form controls are unstyled. Real builder bug, needs its own
   ticket.
2. **Probe font preflight (recommended)**: before launching, verify fonts
   resolve (e.g. `fc-list` output non-empty once the image ships fontconfig) and
   fail fast with an actionable message instead of a cryptic FATAL. Cheap,
   prevents recurrence of this whole class.
3. **LD_LIBRARY_PATH**: verify whether the headless shell actually needs
   `qa/.browsers/syslibs/usr/lib/aarch64-linux-gnu` at runtime (`ldd` on the
   binary, unverified today) and, if so, have probe set it automatically.
4. Pinning an older Chromium: rejected; the stub is ancient and the fix is the
   environment.

## Open questions

- Exact seccomp allowlist for Chrome's namespace sandbox under
  `--read-only --cap-drop ALL` (empirical; 2a milestone gate).
- Whether `chromiumSandbox: true` needs an opt-out env for other probe call
  sites (CI runners outside the engine sandbox).
- Phase B orchestration design (where the dedicated ro-workspace container is
  created from the yosk side).

## Cross-repo note

Fixes 1 and 2b land in yosk-cms (`qa/probe.mjs`); fixes 2a and 2c-engine land
in agent-engine (this repo). Fix 3 is done. Landing order: 2a (code, then the
host-side gate), then 1 and 2b together, then Phase B as its own piece.

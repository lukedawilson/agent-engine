# 015 — Container lifecycle: `--rm` cleanup fix

Status: Ready (awaiting dogfood run)

## §1 Decisions

| # | Decision |
|---|---|
| D1 | Switch the exec-container create path from `docker create` + `docker start` to **`docker run -d --rm`** (same hardening flags) so the Docker daemon auto-removes the container the moment it exits — covering the kill-without-close orphan case. |
| D2 | `close()` tolerates the already-removed case: `docker rm -f` on a container the daemon just auto-removed returns "no such container" — treat as success, never raise. |
| D3 | The startup sweep (option b: `docker rm` any *Exited* `*-exec` container before creating a new one) is **deferred**. It only covers "CLI dies but the container keeps running", which has not been observed. Re-open if it ever is. |
| D4 | The existing orphan (`ef9637b2...-exec`, Exited 137) is removed manually as a one-off: `docker rm ef9637b2313e4e4a9b167f74b62dcb67-exec`. |

## §2 Root cause and evidence

The dogfood run at 13:29–13:53 on 2026-10-20 ended with the CLI being SIGKILLed (container exit 137, 24-min life). `run_pipeline` wraps execution in `try/finally sandbox.close()` → `docker rm -f`, so every normal exit path already cleans up. A process killed by SIGKILL has no chance to run `close()` — no code in the dead process can prevent *that* orphan. The fix is therefore on the daemon side: `--rm` makes cleanup automatic the instant the container exits, however it exits.

Coverage boundary (honest): `--rm` fires when the container **exits**. If a CLI dies but its container keeps *running*, `--rm` does not fire — only D3's sweep would catch that. Our observed orphan was the killed-container case, which `--rm` fully closes.

## §3 Design

- `docker_create_payload(...)` becomes a `docker run` payload:
  `docker run -d --rm --name {run_id}-exec --network none --read-only --cap-drop ALL --memory {memory} --cpus {cpus} [--user uid:gid] [--env HOME=/tmp] --tmpfs /tmp --tmpfs /root -v {ws}:{ws} --workdir {ws} {image} sleep infinity`
  (everything unchanged except `create` → `run -d --rm`; `run -d` = create + start in one call, so the backend drops its separate `docker start`).
- `DockerBackend.close()`: `docker rm -f` returncode != 0 is **ignored** (auto-removed container). Keep the rm for the normal path.
- Provision containers already use `docker run --rm` — unaffected.
- No change to naming, audit, or state.

## §4 Tests (TDD red/green/refactor)

- **RED (unit, `tests/test_isolation.py` TestPayloads):** update the create-payload invariants to assert `run`, `--detach`, `--rm` (and that `create` no longer appears); provision-payload invariants unchanged.
- **RED (unit, new):** `close()` on an already-removed container does not raise — fake runner returns rc 1 / "No such container"; close() still succeeds.
- **GREEN:** payload function + backend create/start collapse + close() tolerance.
- **Real-daemon proof:** the 7 docker-marked tests in `tests/test_isolation_integration.py` exercise the real lifecycle against the daemon.
- **Manual end-to-end (dogfood bonus):** after the fix, `kill -9` a running loop mid-dev — the exec container must be auto-removed by the daemon (verify via `docker ps -a`).

## §5 Dogfood execution

This plan is written to be executed **by the loop itself** from the published wheel:

1. `.venv` runs the published `agentic-dev-loop==1.0.0a1` wheel (verified: version, site-packages import, `isolation` + `dryrun` present).
2. Working tree is clean at `4cab12d` → commit gate armed.
3. Launch: `./trigger-agentic-dev-loop.sh --plan planning-docs/015-container-lifecycle-rm-fix.md`.
4. Expected: the dev agent implements D1–D2 TDD, test step passes inside the sandbox, review → qa → commit gate commits the fix.
5. After the loop: review the diff; `docker rm ef96...` (D4); push; `/publish 1.0.0a2` for the next prerelease.

## §6 Out of scope

- Startup sweep (D3 — deferred, re-open on evidence).
- Checkpoint schema floor across wheel versions (separate NFR, raised in the wheel-gotcha review).
- Docker Desktop file-sharing documentation (separate docs item).

# Infrastructure Design - unit-2 (SDK-level hardening)

## Summary

Infrastructure design found **no infrastructure components** in unit-2. The unit hardens in-process subprocess invocation and tool registration within a desktop CLI library. All infrastructure categories are N/A with justification (see plan).

## Component-to-Infrastructure Mapping

| Logical component (FD) | Infrastructure choice | Rationale |
| --- | --- | --- |
| `proc.needs_shell` / `split_command` | None - in-process pure functions | String classification + `shlex.split` |
| `proc.is_pid_token` | None - in-process pure function | Numeric validation |
| `proc.child_env` | None - in-process pure function | Env-dict construction |
| `_run_command` (command step) | Host-side subprocess (child of pipeline process) | stdlib `subprocess`; no service |
| Action helpers (`git`/`lsof`/`ps`/`kill`) | Host-side subprocess, `shutil.which` resolution | Existing host binaries; no new runtime |
| `Registry.add_tool` validation | None - in-process guard | Validates against the SDK's global registry |

## Explicitly Deferred to unit-3

| Item | Why |
| --- | --- |
| Container daemon detection (unix socket vs npipe) | Unit-3 kernel isolation; unit-2 runs subprocesses host-side |
| Mount-path translation, image selection, image-defined toolchain | Unit-3 (FR-2.2) |
| Isolation fail-fast on unavailable runtime | Unit-3 (FR-2.3) |
| Reusing `child_env` inside the sandbox boundary | Unit-3 (FR-2.1) |

## Storage Note

`env_allowlist` is a YAML config field on `PipelineConfig` - config, not storage. No new directories, no new lifecycle.

## Security Note

Unit-2 introduces a host-side process boundary (subprocess invocation) but no new network surface. The hardening (argv-only, pid validation, binary resolution, whitelist child env) applies at that boundary. The security baseline's infrastructure-shaped rules remain N/A for a desktop library; the applicable host-surface rules (SECURITY-05/06/12/15) are discharged in the FD/NFR.

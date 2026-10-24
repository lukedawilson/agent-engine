# NFR Requirements - unit-2 (SDK-level hardening)

## Assessment Summary

NFR assessment identified one real NFR (subprocess environment hygiene); security is the dominant concern and was already mapped in the Functional Design's business-rules (BR-4/BR-5 + security-baseline dispositions). Everything else is N/A per user scoping (desktop CLI library, single pipeline process, no uptime concept - same as unit-1).

## Non-Functional Requirements

| ID | NFR | Detail |
| --- | --- | --- |
| NFR-2.1 | **Environment hygiene (subprocess)** | Command/action subprocesses run in a child environment built from a fixed known-safe whitelist (`PATH` + the minimal vars tests/git need) **plus** the `llm.api_key_env` value (included by default) **plus** an explicit, author-extensible `env_allowlist` (a new optional config key). All other env vars are excluded unless allowlisted. |
| NFR-2.2 | **Input validation (subprocess boundaries)** | Pid tokens from `lsof` output validated numeric (`is_pid_token`); tool names validated as non-empty identifiers with collision rejection. Satisfies SECURITY-05 (input validation). |
| NFR-2.3 | **Fail-safe / fail-closed** | All hardening validations raise loudly at load (tool-name collision) or are positive-only at run (unverifiable pid spared, never killed). No silent overwrite, no silent degrade. Satisfies SECURITY-15 (fail closed). |
| NFR-2.4 | **Testability / PBT** | `hypothesis` already a dev dependency (unit-1). PBT-02 properties (needs_shell, split_command, is_pid_token, tool-name validation, child_env scrubbing) added for the new pure functions. |
| NFR-2.5 | **Backward compatibility** | One **optional, additive** config key (the env allowlist); no required keys, no renamed keys. Existing pipelines keep working unchanged. |

## Category Dispositions

| Category | Disposition | Justification |
| --- | --- | --- |
| Scalability | N/A | Desktop tool, single pipeline process |
| Performance | N/A | Hardening adds one string scan + one `shlex` split + one env-dict build per command step - negligible |
| Availability | N/A | No uptime concept; crash-safe resume via checkpointing unchanged |
| Maintainability | N/A | Covered by binding DDD + PBT extension rules |
| Usability | N/A | CLI UX unchanged; YAML schema gains one optional key only |

## Security Baseline Rule Dispositions (blocking set)

| Rule | Disposition |
| --- | --- |
| SECURITY-01 (encryption) | N/A - no data persistence or transport in scope |
| SECURITY-02/03 (access/app logging) | N/A - library emits no logs; viz/pipeline logging unchanged |
| SECURITY-04 (HTTP headers) | N/A - no HTTP server in scope |
| SECURITY-05 (input validation) | Applicable - NFR-2.2 (`is_pid_token`, tool-name validation) |
| SECURITY-06 (least privilege) | Applicable - NFR-2.1 (whitelist child env, argv-only action calls; LLM key passed to trusted command/action subprocesses per user decision) |
| SECURITY-12 (credential hygiene) | Applicable - no hardcoded credentials (key stays in the env var, never in code/logs); key passed to trusted subprocesses by default |
| SECURITY-15 (fail closed) | Applicable - NFR-2.3 |
| SECURITY-07..11, 13, 14 | N/A - cloud/network/config posture rules; desktop library |

# Business Rules — unit-2 (SDK-level hardening)

## BR-1: Tool surface is the exact capability allowlist (FR-1.1)

| Rule | Detail |
| --- | --- |
| BR-1.1 | `tools:` in `.agent.md` is the complete, authoritative set of *capability* tools |
| BR-1.2 | `FinishTool` (done signal) and `ThinkTool` (reasoning scaffold) are always present as infra — they are not capabilities and cannot be removed via `tools:` |
| BR-1.3 | Empty `tools:` → the agent has no capabilities (can think + finish only) |
| BR-1.4 | No `filter_tools_regex` surface — the allowlist is explicit, not pattern-based |
| BR-1.5 | Unknown tool name in `tools:` → fail fast at load (preserved behavior) |

## BR-2: `task_tracker` instruction removed (FR-1.4)

- `dev.agent.md` drops the "create task tracker entries" step; the dev agent remains `tools: [terminal]`.
- `task_tracker` remains *registered* in the SDK (it is a legitimate extension/agent tool), but no shipped agent instructs its use. No dead instruction survives.

## BR-3: Tool registration is validated before register (FR-1.7)

| Rule | Detail |
| --- | --- |
| BR-3.1 | A tool name must be a non-empty identifier (no leading/trailing whitespace, no empty string) |
| BR-3.2 | A name already present in the SDK global registry (`list_registered_tools()`) is a collision — reject with a loud error naming the extension and the existing owner |
| BR-3.3 | Validation happens at `Registry.add_tool` (load time), before any call to the SDK's `register_tool` — never a silent overwrite |
| BR-3.4 | The SDK's duplicate-name behavior (warn + clobber) is pre-empted by BR-3.2; agent-engine never relies on it |

## BR-4: Command steps use a hybrid shell surface (FR-1.5)

| Rule | Detail |
| --- | --- |
| BR-4.1 | A command with no shell metacharacters runs argv-style (`shell=False`) via `shlex.split` |
| BR-4.2 | A command using shell metacharacters (`&&`, `\|`, `;`, `>`, `<`, `$`, …) runs via the shell (`shell=True`) — backward compatible |
| BR-4.3 | Both paths build a whitelist-based child environment (`child_env`): fixed known-safe whitelist + the `llm.api_key_env` value (included by default) + author-extensible `env_allowlist`; all other env vars excluded (NFR-1 = C) |
| BR-4.4 | Exit-code-is-the-verdict semantics, timeout process-group kill, and `start_new_session=True` are unchanged |

## BR-5: Action steps harden subprocess calls (FR-1.6)

| Rule | Detail |
| --- | --- |
| BR-5.1 | All action subprocess calls use argv lists, `shell=False` (already true — made explicit and locked) |
| BR-5.2 | A pid token from `lsof` output is used only if it is a plain decimal integer (`is_pid_token`); anything else is discarded |
| BR-5.3 | `git`/`lsof`/`ps`/`kill` are resolved via `shutil.which` before invocation |
| BR-5.4 | The action subprocess environment is scrubbed like command steps (BR-4.3) |
| BR-5.5 | Positive-only attribution is preserved: an unverifiable process is spared, never killed |

## BR-6: Fail-fast, never silent (FR-1.8, NFR-2)

- Every validation failure (bad tool name, collision, unknown frontmatter tool) raises a loud error naming the problem at load.
- No path degrades silently: no warn-and-continue for the surfaces this unit hardens.

## BR-7: Backward compatibility (NFR-1)

- Pipeline YAML schema gains exactly one **optional, additive** key (the subprocess env allowlist); no required keys, no renamed keys.
- Existing `.agent.md` files behave identically (FinishTool + ThinkTool were already auto-added today; BR-1 makes that explicit).
- Command steps using shell operators keep working via BR-4.2.

## Security-baseline mapping (host surfaces)

| SECURITY rule | Disposition | Where |
| --- | --- | --- |
| SECURITY-05 input validation | Enforced | `is_pid_token`, tool-name validation (BR-3, BR-5) |
| SECURITY-06 least privilege | Enforced | `child_env` secret scrubbing, argv-only action calls (BR-4.3, BR-5.1) |
| SECURITY-12 credential hygiene | Enforced | api key never enters subprocess env (BR-4.3) |
| SECURITY-15 fail closed | Enforced | loud load-time failures, no silent overwrite (BR-6) |
| SECURITY-01/02/03/04/07/08/09/10/11/13/14 | N/A — library with no data stores, network intermediaries, web endpoints, or auth | — |

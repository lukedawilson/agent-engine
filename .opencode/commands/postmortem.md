---
description: Run a blameless postmortem for an incident — interactive section-by-section drafting with the user, ending in a doc under aidlc-docs/incidents/ plus rule propagation (AGENTS.md, agentic-dev-loop agents, commands). Use after an outage, data loss, destructive-tooling incident, or near-miss.
---

# Postmortem

Blameless by construction: the RCA names mechanisms and process gaps, never
people. Credit discovery honestly — if the user found it, the doc says the
user found it, even when the agent is drafting.

Reference instance: `aidlc-docs/incidents/2026-09-29-framer-ghost-deletion.md`.

## Phase 1 — Facts before framing

1. Reconstruct the timeline from the session record, logs, and diffs. Present
   it to the user for correction **before** drafting anything else.
2. Never invent wall-clock times. If none were recorded, write "all within
   <date>" and say times weren't recorded.
3. Establish the blast radius precisely: what broke, for whom, for how long,
   what was *not* affected (checked, not assumed).

## Phase 2 — Draft in review batches

Draft the sections below, presenting them in two batches for user review —
corrections are incorporated before proceeding:

- Batch 1: TL;DR, Impact, Timeline
- Batch 2: Root-cause analysis, Actions, What went well, Where we got lucky

The user's corrections override the agent's framing, always. If the user says
"I drove the check that found it", the doc says so.

### Sections

1. **TL;DR** — what happened, the mechanism, the recovery, the net outcome.
   Five sentences max.
2. **Impact** — blast radius: duration, affected systems/users, published
   state, data loss (or its confirmed absence), collateral, trust cost.
3. **Timeline** — ordered events including the wrong turns (they're the
   learning). Detection moment and mitigation moment clearly marked.
4. **Root-cause analysis** — chain-of-whys from the observable failure back
   to the process gap that allowed it. Keep asking why until the answer is a
   *process* answer, not a *technical* one. State the meta root cause.
5. **Actions** — grouped as **Prevent** / **Detect** / **Process**, each with
   an owner and date — or explicitly marked unowned. Already-queued work is
   linked, not duplicated.
6. **What went well** — only things that are repeatable virtues (good gates,
   fast detection, clean rollback). If the user's skepticism was the safety
   net, that's noted here — and it implies a Process action, because
   "vigilant user" is not a control.
7. **Where we got lucky** — the near-misses: things that saved us but cannot
   be relied on (a client who didn't notice, a log that happened to survive,
   damage found before interleaved edits). Luck is not virtue; each item
   should map to an Action that removes the dependence on it.

## Phase 3 — Appendices (when the incident touched an undocumented system)

- **Validated model** — every fact about the external system that was
  established by probe during the incident/repair, in a
  `Fact | Established by (probe) | Date` table. This is usually the most
  durable artifact of the whole exercise.
- **Repair scripts** — the console/runbook scripts that fixed it. If the
  verbatim text is lost, reconstruct from the record and mark as
  reconstructed.

## Phase 4 — Propagate and file

1. File the doc at `aidlc-docs/incidents/YYYY-MM-DD-<slug>.md`.
2. Propagate the Process actions: repo `AGENTS.md`, agentic-dev-loop agents where
   appropriate, new slash commands if a workflow is missing. Ask before
   touching each, unless the user already directed it.
3. Record any deferred product/tech work the incident surfaced in the
   appropriate queue (planning doc or todo) — don't let it evaporate.
4. Close by telling the user exactly what was written where, and what is
   still uncommitted.

## Rules

- Blameless: mechanisms and process gaps, never people.
- Honest credit: whoever actually detected/diagnosed/fixed is who the doc
  credits.
- Evidence over narrative: every claim in Impact and Timeline is something
  that was observed, or it says "unverified".
- The doc is not done until the user has approved every section.

---
description: Summarise an epic, unit, or story. Usage: /ticket-details [epic-id|unit-id|story-id]. Without argument summarises the current entity.
---

Summarise the specified epic, unit, or story. If no argument is given, resolve the current entity from `aidlc-docs/aidlc-state.md`.

**Resolving what to summarise (`$ARGUMENTS`):**

| Argument pattern | Type | Example |
|---|---|---|
| `Epic N`, `E1`, `1`, `epic 3` | Epic | `Epic 2`, `E4`, `3` |
| `U1`, `Unit 2`, `unit 3` | Unit | `U2`, `Unit 4`, `unit 1` |
| `US-XX`, `story US-XX` | Story | `US-03`, `US-10` |
| *(empty)* | Current entity | from `aidlc-docs/aidlc-state.md` |

Parse `$ARGUMENTS` to determine the type. If ambiguous, treat it as an epic (numeric-only matches epics first, fallback to unit).

**Current entity resolution (no `$ARGUMENTS`):**
1. Read `aidlc-docs/aidlc-state.md`.
2. Find the first story under `🟢 CONSTRUCTION PHASE` whose status is NOT `✅ Complete` — this is the current story. Its parent unit and epic are the "current" ones.
3. Summarise the **current unit** (the unit containing that story), not the story itself.
4. If all stories are complete, summarise all units.

**Data sources:**
- Stories & epics: `aidlc-docs/inception/user-stories/stories.md`
- Units: `aidlc-docs/inception/application-design/unit-of-work.md`
- Story-to-unit map: `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- Current state: `aidlc-docs/aidlc-state.md`

---

## Epic Summary

Parse all stories (`### US-XX` blocks) under the `## Epic N: Name` heading to compute status.

Cross-reference with `unit-of-work-story-map.md` to determine which units contain the epic's stories.

Output:

```
Epic 1: Onboarding — Status: To Do

Stories (2 total):
  • US-01: Authenticate — 0/0 tasks → To Do
  • US-02: Enter Business Information — 0/1 tasks → To Do

Units: 2 (Onboarding)
Story completion: 0/2 done (0%). Tasks: 0/1 done (0%).
Next story to implement: US-01 (Authenticate).
```

Status calculation: same rules as `/epic-status`. Story with 0 tasks or 0% done → To Do; partial → In Progress; all done → Done.

---

## Unit Summary

Cross-reference `unit-of-work.md` with `aidlc-state.md` to determine stage progress. Parse each story from `stories.md` to get task counts and status.

Output:

```
Unit 2: Onboarding — Status: To Do

Purpose: User authentication via OIDC, business input form, session state.

Stories (2 total):
  • US-01: Authenticate — 0/0 tasks → To Do
  • US-02: Enter Business Information — 0/1 tasks → To Do

Story completion: 0/2 done (0%). Tasks: 0/1 done (0%).

Construction stages (0/5 done):
  • Functional Design — To Do
  • NFR Requirements — To Do
  • NFR Design — To Do
  • Infrastructure Design — To Do
  • Code Generation — To Do

Backend: AuthController, OIDC, SessionStore, ReportJob
Frontend: InputForm.ts
Dependencies: Foundation (U1), OIDC SDK, UI framework, design system
Tests: Auth flows, SessionStore concurrency, InputForm validation
```

Story status calculation: same rules as for epic stories — 0 tasks or 0% done → To Do; partial → In Progress; all done → Done.

---

## Story Summary

Parse the story block (`### US-XX`) from `stories.md` and cross-reference with the construction table in `aidlc-state.md`. Determine construction stage progress by checking for the existence of each stage's design doc (`aidlc-docs/unit-{N}/{story-id}-functional-design.md`, etc.) and whether code generation has run (PR merged).

Output:

```
US-03: Run Website Analysis — Status: To Do

Epic: 2 (Analysis)  |  Unit: 3 (Analysis)

Persona: Alex (Analyst), Sarah (Business Owner)

Acceptance Criteria:
  • Analysis crawls the provided website URL and evaluates all defined factors
  • Analysis progress is visible (loading indicator per factor)
  • Analysis completes within one minute per website
  • Unreachable website shows clear error (no crash)
  • Results cached for the session (no re-run on back-navigation)

Subtasks — Construction stages (0/5 done):
  ⬜ Functional Design
  ⬜ NFR Requirements
  ⬜ NFR Design
  ⬜ Infrastructure Design
  ⬜ Code Generation

Subtasks — Design tasks: 0/1 done (0%)
  [ ] Design: Design system components — analysis progress dashboard

```

Include the first few acceptance criteria bullet points (up to 5).
If the story has 0 design tasks, note "No design tasks defined."
For construction stages, infer progress from the existence of design docs and completed code generation. Show ✅ for done stages, ⬜ for pending.

---

**After all summary types**, finish with a one-line recommendation: what to do next (e.g. "Ready to start construction." or "Next stage: Functional Design.").

If any required file is missing, report which file and stop.

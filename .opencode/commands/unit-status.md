---
description: View unit construction progress as an ASCII-rendered ticket board. Usage: /unit-status [unit-id|path]. Columns: To Do, In Progress, Done.
---

Render a unit-level ASCII ticket board showing construction progress.

**Resolving what to display (`$ARGUMENTS`):**
- If a **path** is given (contains `/`), read unit-of-work from that file.
- If a **unit id** is given (e.g. `U1`, `U4`), show detailed status for only that unit.
- If **no argument**, resolve the current unit: read `aidlc-docs/aidlc-state.md`, find the first unit under `🟢 CONSTRUCTION PHASE` that is NOT fully complete (5/5 stages) and show that unit. If all units are done, show all units.

**Data sources:**
- Unit definitions & stories: `aidlc-docs/inception/application-design/unit-of-work.md`
- Construction progress: `aidlc-docs/aidlc-state.md` under `## Stage Progress > 🟢 CONSTRUCTION PHASE`
- The construction stages for each unit follow the pattern: `Unit N: Name - StageName`. There are 5 stages per unit: Functional Design, NFR Requirements, NFR Design, Infrastructure Design, Code Generation. `Build and Test` is a global final step tracked separately.

**Rules for status per unit:**
- A unit with 0/5 stages completed → **To Do**
- A unit with some but not all 5 stages completed → **In Progress**
- A unit with all 5 stages completed → **Done**

**When showing a single unit**, expand to show each construction stage with its checkbox state.

Example format (single unit):

```
Unit: U1 - Foundation (current)

┌──────────────────────────────┬─────────────┐
│ Stage                        │ Status      │
├──────────────────────────────┼─────────────┤
│ Functional Design            │ [ ] To Do   │
│ NFR Requirements             │ [ ] To Do   │
│ NFR Design                   │ [ ] To Do   │
│ Infrastructure Design        │ [ ] To Do   │
│ Code Generation              │ [ ] To Do   │
├──────────────────────────────┼─────────────┤
│ 0/5 complete                 │ To Do       │
└──────────────────────────────┴─────────────┘

Linked stories: (none - foundation unit)
```

Example format (all units):

```
┌─────────┬────────────────────┬──────────────────────────────────┬──────────┐
│ Unit    │ Stories            │ Progress                         │ Status   │
├─────────┼────────────────────┼──────────────────────────────────┼──────────┤
│ U1      │ -                  │ 5/5 done                         │ Done     │
│ U2      │ US-01, US-02       │ 2/5 done                         │ In Prog  │
│ U3      │ US-03, US-06, US-07│ 0/5 done                         │ To Do    │
│ U4      │ US-04, US-08, US-09│ 0/5 done                         │ To Do    │
│ U5      │ US-05, US-10       │ 0/5 done                         │ To Do    │
│ U6      │ US-11              │ 0/5 done                         │ To Do    │
├─────────┼────────────────────┼──────────────────────────────────┼──────────┤
│         │                    │ Build & Test: pending            │          │
└─────────┴────────────────────┴──────────────────────────────────┴──────────┘
```

**After the table**, show:
- If single unit: which unit, its linked stories, current progress fraction, next stage to complete.
- If all units: units complete count (X/6), current/next unit to work on, Build and Test status.

If any required file is missing, report that and stop.

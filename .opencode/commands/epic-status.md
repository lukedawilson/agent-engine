---
description: View epics as an ASCII-rendered ticket board with story roll-up. Usage: /epic-status [epic-id]. Columns: To Do, In Progress, Done.
---

Render an epic-level ASCII ticket board showing story completion rolled up per epic.

**Resolving what to display (`$ARGUMENTS`):**
- If an **epic id** is given (e.g. `Epic 1`, `Epic 2`, or just `1`, `3`), show detailed status for only that epic, including each child story with its task progress.
- If **no argument**, show all epics in a summary board.

**Data sources:**
- Stories: `aidlc-docs/inception/user-stories/stories.md`

**Rules for status per epic:**
- Parse all stories (`### US-XX` blocks) under each `## Epic N: Name` heading.
- For each story, count all `- [ ]` / `- [x]` task checkboxes.
- A story with zero checkboxes or 0% done → counts toward **To Do**.
- A story with some but not all checkboxes done → counts toward **In Progress**.
- A story with all checkboxes done → counts toward **Done**.
- An epic with 0% of its stories done → **To Do**.
- An epic with some but not all stories done → **In Progress**.
- An epic with all stories done → **Done**.

**When showing all epics**, output a summary table:

```
+-------------------+-----------------+-----------------+-------------+-------------+----------+
| Epic              | Stories         | To Do           | In Progress | Done        | Status   |
+-------------------+-----------------+-----------------+-------------+-------------+----------+
| Epic 1: Onboarding| US-01, US-02    | 2               | 0           | 0           | To Do    |
| Epic 2: Analysis  | US-03…US-05     | 3               | 0           | 0           | To Do    |
| Epic 3: Reporting | US-06…US-08     | 3               | 0           | 0           | To Do    |
| Epic 4: Export    | US-09…US-11     | 3               | 0           | 0           | To Do    |
+-------------------+-----------------+-----------------+-------------+-------------+----------+
| 4 epics           | 11 stories      | 11              | 0           | 0           |          |
+-------------------+-----------------+-----------------+-------------+-------------+----------+
```

**When showing a single epic**, expand to show each story with its task progress:

```
Epic 2: Analysis

+---------+-----------------------------------+---------------+---------------+----------+
| Story   | Description                       | Tasks         | Progress      | Status   |
+---------+-----------------------------------+---------------+---------------+----------+
| US-03   | Run website analysis              | 0/1 done      | 0%            | To Do    |
| US-04   | Compute and view analysis score   | 0/1 done      | 0%            | To Do    |
| US-05   | LLM-assisted factor drill-down    | 0/1 done      | 0%            | To Do    |
+---------+-----------------------------------+---------------+---------------+----------+
|         |                                   | 0/3 tasks     |               | To Do    |
+---------+-----------------------------------+---------------+---------------+----------+
```

**After the table**, show:
- If all epics: epics complete (X/4), total task progress (X/Y tasks done, Z%).
- If single epic: epic status, story-by-story breakdown, next story to start.

If the stories file is missing, report that and stop.

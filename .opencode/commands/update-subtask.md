---
description: Mark a subtask on a user story as done or not done. Usage: /update-subtask <story-id> "<task-match>" <done|undone>
---

Toggle a subtask checkbox on a user story in `aidlc-docs/inception/user-stories/stories.md`.

**Arguments:**
- `$1` — story ID (e.g. `US-01`, `US-03`). Must match a `### US-XX` heading exactly.
- `$2` — a substring that uniquely identifies the task checkbox line (e.g. `"Login button"`). Match is case-insensitive. If the substring matches multiple lines, report the ambiguity and ask the user to narrow it.
- `$3` — the target state: `done` or `undone`.

**Steps:**
1. Read `stories.md`.
2. Locate the `### $1` heading block.
3. Find all `- [ ]` and `- [x]` lines within that block.
4. Find the line containing `$2` (case-insensitive substring match).
   - If zero matches, report "No task matching '$2' found under $1" and list available tasks.
   - If multiple matches, report each match with its line content and ask the user to narrow the match.
5. Toggle the checkbox:
   - If `$3` is `done` and the line currently has `- [ ]`, change to `- [x]`.
   - If `$3` is `done` and the line already has `- [x]`, report "Already done — no change."
   - If `$3` is `undone` and the line currently has `- [x]`, change to `- [ ]`.
   - If `$3` is `undone` and the line already has `- [ ]`, report "Already undone — no change."
6. Write the updated file.
7. Report: the story, the matched task line, the old and new checkbox state.

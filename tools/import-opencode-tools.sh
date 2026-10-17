#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_LOCAL="$REPO_ROOT/.claude-local"

echo "=== Importing OpenCode commands and skills → $CLAUDE_LOCAL ==="

rm -rf "$CLAUDE_LOCAL/commands" "$CLAUDE_LOCAL/skills"
mkdir -p "$CLAUDE_LOCAL/commands" "$CLAUDE_LOCAL/skills"

# — commands —
exported_commands=0
for cmd in "$REPO_ROOT/.opencode/commands"/*.md; do
  [ -e "$cmd" ] || continue
  name="$(basename "$cmd")"

  # Transform OpenCode-specific syntax to Claude Code equivalents:
  #   !`cmd`          → Run `cmd`
  #   $ARGUMENTS      → $ARGUMENTS   (same in both tools)
  #   /command-name   → /command-name (same in both)
  sed -e 's/^!`\(.*\)`$/Run `\1`/' \
      "$cmd" > "$CLAUDE_LOCAL/commands/$name"

  echo "  command: $name"
  ((exported_commands++))
done
echo "  → $exported_commands commands imported"

# — skills —
imported_skills=0
for skill_dir in "$REPO_ROOT/.opencode/skills"/*; do
  [ -d "$skill_dir" ] || continue
  skill_name="$(basename "$skill_dir")"
  mkdir -p "$CLAUDE_LOCAL/skills/$skill_name"

  # Copy all skill files, stripping OpenCode-specific `metadata:` frontmatter
  # block from SKILL.md (Claude does not use it).
  for src_file in "$skill_dir"/*; do
    [ -e "$src_file" ] || continue
    fname="$(basename "$src_file")"
    if [ "$fname" = "SKILL.md" ]; then
      python3 -c '
import sys, re
text = sys.stdin.read()
# Strip YAML "metadata:" block from frontmatter (between --- delimiters)
# Only operates inside the first frontmatter block.
parts = text.split("---", 2)
if len(parts) >= 3:
    fm = parts[1]
    # Remove lines starting with "metadata:" and all its indented children
    lines = fm.split("\n")
    filtered = []
    skip = False
    for line in lines:
        if skip:
            if line and (line[0] == " " or line[0] == "\t" or line.startswith("  ")):
                continue
            skip = False
        if line.startswith("metadata:"):
            skip = True
            continue
        filtered.append(line)
    parts[1] = "\n".join(filtered)
    sys.stdout.write("---".join(parts))
else:
    sys.stdout.write(text)
' < "$src_file" > "$CLAUDE_LOCAL/skills/$skill_name/$fname"

      echo "  skill: $skill_name (SKILL.md transformed)"
    else
      cp -R "$src_file" "$CLAUDE_LOCAL/skills/$skill_name/$fname"
    fi
  done
  ((imported_skills++))
done
echo "  → $imported_skills skills imported"

echo "=== Done ==="
echo "Claude Code will pick up commands and skills from: $CLAUDE_LOCAL"

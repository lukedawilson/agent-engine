#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

PATCH_DIR=".aidlc/aidlc-patches"
TARGET_PREFIX=".aidlc/aidlc-rules/aws-aidlc-rule-details"

echo "AI-DLC Patches - applying sequentially..."
echo

applied=0
failed=0

for patch in "$PATCH_DIR"/*.patch; do
    [ -f "$patch" ] || continue
    name=$(basename "$patch")
    echo -n "  $name ... "

    if patch -p1 --dry-run --silent < "$patch"; then
        patch -p1 --quiet < "$patch"
        echo "OK"
        ((applied++))
    else
        echo "SKIPPED (already applied or conflict)"
        ((failed++))
    fi
done

echo
echo "Done: $applied applied, $failed skipped."

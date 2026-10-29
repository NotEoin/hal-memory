#!/usr/bin/env bash
# Fails when a tracked text file contains a non-ASCII character, and prints each offending line.
# Used by CI and by hand before a commit; the repo's text is ASCII-only so diffs, grep and
# terminals stay predictable.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
# -z keeps odd file names intact; -I skips binary files.
if git ls-files -z | xargs -0 grep -nIP '[^\x00-\x7F]' --; then
    echo "ascii-check: non-ASCII characters found" >&2
    exit 1
fi
echo "ascii-check: ok"

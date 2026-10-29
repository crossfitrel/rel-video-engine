#!/usr/bin/env bash
# מעלה קבצי תוצאה לענף bench-results בלי לגעת בעץ העבודה (ענף נקי, רק results/).
set -u
D=$(mktemp -d); cd "$D"
git init -q && git remote add origin "$(git -C "$GITHUB_WORKSPACE" remote get-url origin)"
git fetch -q --depth 1 origin bench-results 2>/dev/null && git checkout -q FETCH_HEAD -B bench-results || git checkout -q --orphan bench-results
mkdir -p results
for f in "$@"; do [ -f "$f" ] && cp "$f" "results/${GITHUB_RUN_ID}-$(basename "$f")"; done
git add results && git -c user.name=rel-bench -c user.email=noreply@anthropic.com commit -qm "bench ${GITHUB_RUN_ID}" && git push -q origin HEAD:bench-results

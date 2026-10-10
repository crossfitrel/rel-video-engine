#!/usr/bin/env bash
# שכבת תאימות: קונפיגים ישנים מחזיקים נתיבי מק מוחלטים (broll-catalog-config, paths.json...).
# במקום לשבור אותם — מצביעים את אותם נתיבים לשורשי הענן. מתועד ב-CLOUD.md; קוד חדש משתמש ב-env.sh בלבד.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/env.sh"
MAC_PARENT="/Users/hayon/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי"
mkdir -p "$MAC_PARENT" 2>/dev/null || { echo "[mac_compat] אין הרשאה ל-/Users — מדלג"; exit 0; }
ln -sfn "$REL_HOME" "$MAC_PARENT/Social Video Editing System"
ln -sfn "$REL_WORK_ROOT" "/Users/hayon/rel-video-work"
echo "[mac_compat] ✓"

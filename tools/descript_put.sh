#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# ============================================================================
# descript_put.sh — R.E.L Social Video Editing System
# ----------------------------------------------------------------------------
# העלאה ישירה ורובסטית של קובץ וידאו מקומי ל-Descript, בלי תלות במאנדיי.
#
# למה: ההעלאה של קבצי גלם למאנדיי נכשלת כל הזמן (קבצים כבדים / API לא יציב).
# במקום זה — הקובץ נשאר מקומי, ו-Descript תומך ב-DIRECT FILE UPLOAD:
#   1. הסוכן קורא ל-import_media (MCP) עם content_type + file_size
#      → מקבל בחזרה upload_urls = { "<key>": { upload_url, asset_id, artifact_id } }
#   2. הסקריפט הזה עושה PUT של הקובץ המקומי אל upload_url (זה השלב היחיד שדורש אינטרנט)
#   3. הסוכן קורא ל-wait_for_job וממשיך בזרימת העריכה הרגילה.
#
# זה מחליף את "get_assets → public_url של מאנדיי → import_media(url)".
# העלאה אחת אמינה, עם retry, במקום שתי קפיצות שבירות.
#
# שימוש:
#   bash descript_put.sh <local_file> "<upload_url>"            # foreground (ברירת מחדל)
#   bash descript_put.sh --bg <local_file> "<upload_url>"       # רקע (nohup) — לקבצים כבדים מאוד
#
# פלט: שורת JSON אחת עם status/http_code/bytes. exit 0 = הצלחה, אחרת = כשל.
# לקח 1080p (זיכרון): רקע + בדיקה אחת — בלי ניטור תכוף שמתנגש בתהליך ההעלאה.
# ============================================================================
set -uo pipefail

BG=0
if [[ "${1:-}" == "--bg" ]]; then BG=1; shift; fi

FILE="${1:?usage: descript_put.sh [--bg] <local_file> <upload_url>}"
URL="${2:?usage: descript_put.sh [--bg] <local_file> <upload_url>}"

if [[ ! -f "$FILE" ]]; then
  echo "{\"status\":\"error\",\"reason\":\"file_not_found\",\"file\":\"$FILE\"}"
  exit 2
fi

# גודל הקובץ (macOS stat -f%z, לינוקס stat -c%s)
BYTES=$(stat -f%z "$FILE" 2>/dev/null || stat -c%s "$FILE" 2>/dev/null || echo 0)

do_put() {
  # -T = PUT של הקובץ ; Content-Type חובה לפי Descript ; retry על שגיאות זמניות
  curl -sS -f -X PUT \
    -H "Content-Type: application/octet-stream" \
    --retry 5 --retry-delay 5 --retry-all-errors \
    --connect-timeout 30 --max-time 7200 \
    -w '%{http_code}' -o /dev/null \
    -T "$FILE" "$URL"
}

if [[ "$BG" == "1" ]]; then
  LOG="${FILE%.dummy}.descript_put.log"
  # רקע: nohup, ולוג ליד הקובץ. בדיקה אחת בסוף (לא ניטור תכוף).
  nohup bash -c "code=\$($(declare -f do_put); do_put); echo \"{\\\"status\\\":\\\"done\\\",\\\"http_code\\\":\\\$code,\\\"bytes\\\":$BYTES}\" > '$LOG'" >/dev/null 2>&1 &
  echo "{\"status\":\"started_bg\",\"pid\":$!,\"bytes\":$BYTES,\"log\":\"$LOG\"}"
  exit 0
fi

HTTP=$(do_put); RC=$?
if [[ "$RC" -eq 0 && "$HTTP" =~ ^2 ]]; then
  echo "{\"status\":\"ok\",\"http_code\":$HTTP,\"bytes\":$BYTES,\"file\":\"$(basename "$FILE")\"}"
  exit 0
else
  echo "{\"status\":\"error\",\"http_code\":${HTTP:-0},\"curl_rc\":$RC,\"bytes\":$BYTES,\"file\":\"$(basename "$FILE")\"}"
  exit 1
fi

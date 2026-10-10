#!/bin/zsh
# אפליקציית הרוויו של R.E.L — דאבל-קליק ומתחילים (פורט 5112)
# v9.26: השרת בבעלות launchd (com.rel.review-app) ורץ על ~/.rel-whisper (flask).
# הקובץ הזה לא מרים שרת שני — הוא מעיר את launchd, ורק אם אין LaunchAgent מריץ ישירות.
cd "$(dirname "$0")"
PY="$HOME/.rel-whisper/bin/python"
URL="http://127.0.0.1:5112"
if curl -s -m 2 "$URL/health" >/dev/null; then open "$URL"; exit 0; fi
if launchctl list com.rel.review-app >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/com.rel.review-app"
  for i in {1..20}; do curl -s -m 1 "$URL/health" >/dev/null && break; sleep 0.5; done
  open "$URL"; exit 0
fi
[ -x "$PY" ] || { echo "חסר $PY — אפליקציית הרוויו לא תעלה עם python3 המערכתי (אין flask)"; exit 1; }
"$PY" -c "import flask" 2>/dev/null || "$PY" -m pip install --quiet flask
( sleep 2 && open "$URL" ) &
exec "$PY" server.py

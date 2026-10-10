#!/bin/bash
# ▶ מפעיל את אפליקציית הכתוביות המקומית של R.E.L
# דאבל-קליק → השרת עולה והדפדפן נפתח אוטומטית.
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=5111
PY="/Users/hayon/.rel-whisper/bin/python"

# אם השרת כבר רץ — רק פותחים דפדפן ויוצאים
if curl -s "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  open "http://127.0.0.1:$PORT"
  exit 0
fi

cd "$DIR"
( sleep 3; open "http://127.0.0.1:$PORT" ) &
echo "מפעיל את אפליקציית הכתוביות של R.E.L…  (לסגירה: סגרו חלון זה)"
exec "$PY" server.py

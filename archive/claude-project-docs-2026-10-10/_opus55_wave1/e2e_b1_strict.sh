#!/bin/zsh
# גל 5 — B1 חוסם במסלול ה-CLI שהגימור מריץ (--strict): 3 סרטונים תקינים + הזרקת כשל על עותק.
cd "$(dirname "$0")/.."
P=~/.rel-whisper/bin/python
OUT=_opus55_wave1/e2e_b1_strict.txt
: > $OUT
for n in ממומן-ת1-תושבים ממומן-ת3-סטודנטים בריאות-לקום-מכיסא; do
  $P tools/broll_vision_qa.py check --workdir ~/rel-video-work/$n --strict > /tmp/b1_$$.txt 2>&1; rc=$?
  echo "OK-CASE $n rc=$rc :: $(head -1 /tmp/b1_$$.txt)" >> $OUT
done
# הזרקה: עותק של בריאות-לקום-מכיסא, הבירול הראשון ב-items_applied מוחלף בקליפ אחר מהמאגר
T=$(mktemp -d /tmp/b1inj.XXXX); S=~/rel-video-work/בריאות-לקום-מכיסא
for f in FINAL.mp4 EXPORT.mp4 EXPORT_TIGHT.mp4 project_manifest.json broll_plan.json FINAL_PROVENANCE.json CAPTION_VISION.json; do
  [ -e "$S/$f" ] && cp -c "$S/$f" "$T/$f" 2>/dev/null || { [ -e "$S/$f" ] && cp "$S/$f" "$T/$f"; }
done
$P - "$T" <<'E'
import json, sys, random
from pathlib import Path
sys.path.insert(0, "tools")
import broll_vision_qa as B
T = Path(sys.argv[1])
m = json.loads((T / "project_manifest.json").read_text())
it = m["finish_prefs"]["broll"]["items_applied"][0]
_c, cat = B._catalog()
other = next(i for i in cat.values() if Path(i["path"]).exists() and Path(i["path"]).name != Path(it.get("path") or it["file"]).name and "מדרגה" not in i["path"])
it["path"], it["file"] = other["path"], Path(other["path"]).name
(T / "project_manifest.json").write_text(json.dumps(m, ensure_ascii=False))
(T / "broll_plan.json").write_text(json.dumps({"plan": m["finish_prefs"]["broll"]["items_applied"]}, ensure_ascii=False))
print("injected", other["file"])
E
$P tools/broll_vision_qa.py check --workdir "$T" --strict > /tmp/b1_$$.txt 2>&1; rc=$?
echo "INJECTED-CASE rc=$rc :: $(head -1 /tmp/b1_$$.txt)" >> $OUT
echo DONE >> $OUT

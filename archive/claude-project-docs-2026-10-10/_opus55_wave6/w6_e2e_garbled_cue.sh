#!/bin/zsh
# E2E על עותק (/tmp) של FINAL אירוע אמיתי: 3 cues עם מילה אחרת בקובץ המילים (הכשל החלקי —
# צריבה מקובץ מילים שונה במקטע). לפני v9.34: 3/70 < 25% ⇒ לא נחסם. אחרי: garbled_cue ≥3 ⇒ rc=1.
S="$HOME/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System"
P=~/.rel-whisper/bin/python
SRC=~/rel-video-work/דרג-לי-את-הפודיום-עלית-גברים
T=/tmp/w6_e2e_garbled_cue; rm -rf $T; mkdir -p $T
for f in FINAL.mp4 words_final.json project_manifest.json FINAL_PROVENANCE.json; do [ -f "$SRC/$f" ] && cp -p "$SRC/$f" $T/; done
echo "== מקור (עותק נקי):"
$P "$S/tools/caption_vision.py" --workdir $T --strict; echo "rc=$?"
$P - $T <<'EOF'
import json, sys
p = sys.argv[1] + "/words_final.json"
d = json.load(open(p, encoding="utf-8"))
words = d if isinstance(d, list) else d.get("words")
repl = {10: "מזרון", 25: "קטלבל", 40: "סקוואט"}          # 3 מילים ארוכות מספיק, פזורות
for i, w in repl.items():
    words[i]["word"] = w
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
print("הוזרקו 3 מילים שונות בקובץ המילים:", {i: words[i]["word"] for i in repl})
EOF
echo "== אחרי הזרקה:"
$P "$S/tools/caption_vision.py" --workdir $T --strict; echo "rc=$?"
$P -c "import json;d=json.load(open('$T/CAPTION_VISION.json'));print('counts',d['counts'],'blocking_hits',d['blocking_hits'])"

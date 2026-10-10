#!/bin/zsh
# הזרקת כשל לשלושת התיקונים של גל 6: שבירת הקוד → הבדיקות חייבות להיכשל → שחזור + sha זהה.
S="$HOME/Library/Mobile Documents/com~apple~CloudDocs/קרוספיט אריאל/01 - שיווק/תוכן שיווקי/Social Video Editing System"
cd "$S" || exit 1
P=~/.rel-whisper/bin/python
inject() {  # file, python-replace-old, new, label
  local f="$1" label="$4"
  cp -p "$f" /tmp/w6_fi_backup
  local before=$(shasum -a 256 "$f" | cut -c1-12)
  $P - "$f" "$2" "$3" <<'EOF'
import sys
f, old, new = sys.argv[1:4]
s = open(f, encoding="utf-8").read()
assert s.count(old) == 1, ("pattern", old)
open(f, "w", encoding="utf-8").write(s.replace(old, new))
EOF
  local out=$($P -m unittest tests.test_vision_wave6_v934 2>&1 | grep -E "^(FAILED|OK)|^FAIL:|^ERROR:")
  cp -p /tmp/w6_fi_backup "$f"
  local after=$(shasum -a 256 "$f" | cut -c1-12)
  echo "── $label"; echo "$out"; echo "   sha $before → $after"
}
inject tools/caption_vision.py 'm.get("g1", 1.0) < g1max' 'm.get("g1", 1.0) < -1' "garbled_cue כבוי"
inject tools/caption_vision.py 'verified = [f for f, n in zip(hit, ne) if n >= 2]' 'verified = hit' "אימות עיניים כבוי"
inject tools/thumbnail/cover_vision.py 'res["flags"].append("garbled_word_title")' 'pass' "ייחוס מילה בכותרת כבוי"
echo "── אחרי שחזור:"; $P -m unittest tests.test_vision_wave6_v934 2>&1 | grep -E "^(FAILED|OK)|^Ran"

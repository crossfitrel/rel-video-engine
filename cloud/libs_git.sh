#!/usr/bin/env bash
# libs_git — ספריות ומצב של מערכת העריכה דרך ענף `libs` בריפו הפרטי crossfitrel/rel-video-cloud.
# L175: הקוד רץ מהריפו הציבורי rel-video-engine; הגישה לריפו הפרטי עם secrets.LIBS_TOKEN (ראו video-worker.yml).
# בלי טוקן ובלי סודות: הגישה היא דרך ה-git proxy של סשן הענן (כמו הקוד עצמו).
# נבחר ב-11.10.26 אחרי שהתברר שמשימות מתוזמנות של claude.ai רצות בסביבת cloud_default
# שלא קוראת משתני סביבה של claude.ai/code — טוקן Drive לא יכול להגיע אליהן.
#
#   pull | push | pull-project NAME | push-project NAME | archive-final NAME PATH
#
# מבנה הענף:
#   lib/<נתיב יחסי ל-REL_HOME>        בירולים, מיכאל לוי, brand-assets, תוצרי-אנימציה/פתיחים-קבועים
#   lib/_tools-assets/<נתיב>          נפרס לשורש REL_HOME (פונטים/sfx/מודלים של הכלים)
#   state/<STATE_FILES>               קבצי מצב שמשתנים בריצה
#   state/פרויקטים/<שם>               תיקיות פרויקט פעילות (בלי תוצרי ביניים)
# קובץ מעל 90MB נשמר כחלקים X.relsplit.000, .001 … (מגבלת 100MB של GitHub) ומורכב בפריסה; sha256 נבדק.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/env.sh"
REPO_URL="${REL_LIBS_URL:-https://github.com/crossfitrel/rel-video-cloud}"
BR="${REL_LIBS_BRANCH:-libs}"
CL="${REL_LIBS_CLONE:-$HOME/rel-libs}"
SPLIT=90m; SPLIT_BYTES=$((90*1024*1024))
STATE_FILES=(tools/music-rotation.json tools/learn-state.json tools/illustration-ledger.json tools/hook_fx_verdicts.json
  tools/visual_hook_registry.json tools/motion/harel_verdicts.json tools/broll-tags-override.json tools/he-lexicon.json
  tools/asr-glossary.json tools/music-intro-dip.json "בירולים/catalog.json" "בירולים/usage.json")
PROJ_EXCL=(--exclude 'cue_*.png' --exclude 'FINAL_prev_*' --exclude 'clip_*.mp4' --exclude '_mg_snaps/' --exclude '*.tmp' --exclude 'EXPORT+*.mp4'
  --exclude 'MIXED*.mp4' --exclude 'MG_LAYER.mov' --exclude '_insert_base.mp4' --exclude 'REVIEW_PROXY.mp4' --exclude 'INPUT.hlg.mp4' --exclude 'raw/' --exclude '*.wav'
  --exclude '.DS_Store' --exclude '__pycache__/')
log(){ echo "[libs_git] $*"; }
G(){ git -C "$CL" -c user.name="REL cloud" -c user.email="noreply@anthropic.com" "$@"; }

clone(){
  if [[ -d "$CL/.git" ]]; then G fetch -q --depth 1 origin "$BR" && G reset -q --hard "origin/$BR"
  else git clone -q --depth 1 --single-branch --branch "$BR" "$REPO_URL" "$CL"; fi
}

# פורס עץ מהענף ליעד: rsync לכל מה שלא חלק, ואז הרכבה + אימות של קבצים מפוצלים
deploy(){ # src dst
  local src="$1" dst="$2"; [[ -d "$src" ]] || return 0; mkdir -p "$dst"
  rsync -a --exclude '*.relsplit.*' --exclude '*.relsplit.sha256' "$src/" "$dst/"
  while IFS= read -r -d '' first; do
    local base="${first%.relsplit.000}"; local rel="${base#$src/}"; local out="$dst/$rel"
    mkdir -p "$(dirname "$out")"; cat "$base".relsplit.[0-9][0-9][0-9] > "$out.tmp"
    if [[ -f "$base.relsplit.sha256" ]]; then
      [[ "$(sha256sum "$out.tmp" | cut -d' ' -f1)" == "$(cat "$base.relsplit.sha256")" ]] || { log "❌ sha256 לא תואם: $rel"; rm -f "$out.tmp"; return 4; }
    fi
    mv "$out.tmp" "$out"
  done < <(find "$src" -name '*.relsplit.000' -print0)
}

# מכניס עץ לענף: קבצים גדולים מפוצלים, השאר כמו שהם
stage_tree(){ # src dst [rsync opts...]
  local src="$1" dst="$2"; shift 2; mkdir -p "$dst"
  rsync -a --delete "$@" --exclude '*.relsplit.*' "$src/" "$dst/"
  find "$dst" -type f -name '*.relsplit.*' -delete 2>/dev/null || true
  while IFS= read -r -d '' f; do
    sha256sum "$f" | cut -d' ' -f1 > "$f.relsplit.sha256"
    split -b "$SPLIT" -d -a 3 "$f" "$f.relsplit."; rm -f "$f"
  done < <(find "$dst" -type f -size +"$SPLIT_BYTES"c ! -name '*.relsplit.*' -print0)
}

commit_push(){ # msg stage_fn [args...]
  # L151 (1.11.26): בשיבוט עומק 1 אין בסיס משותף, ו-rebase על push מקביל הופך כל קובץ ששונה ל-add/add conflict.
  # ה-rebase נכשל בשקט, ה-push "הצליח" עם הקומיט של הכותב האחר, והשינויים שלנו נעלמו (verify תפס).
  # במקום rebase: fetch → reset --hard ל-origin → בימוי מחדש מהדיסק → commit → push. עד 6 ניסיונות.
  local msg="$1"; shift
  for i in 1 2 3 4 5 6; do
    "$@"
    G add -A; if G diff --cached --quiet; then log "אין שינוי"; return 0; fi
    G commit -qm "$msg"
    if G push -q origin "HEAD:$BR"; then log "push ✓ ($(G rev-parse --short HEAD))"; return 0; fi
    log "push נדחה (כותב מקביל) — מביים מחדש על הקצה של origin, ניסיון $i"
    sleep $(( (RANDOM % 5) + i * 3 ))
    G fetch -q --depth 1 origin "$BR" && G reset -q --hard "origin/$BR"
  done
  log "❌ push נכשל"; return 5
}
stage_state(){
  for f in "${STATE_FILES[@]}"; do [[ -f "$REL_HOME/$f" ]] && { mkdir -p "$(dirname "$CL/state/$f")"; cp "$REL_HOME/$f" "$CL/state/$f"; }; done
  [[ -d "$REL_WORK_ROOT/.index" ]] && stage_tree "$REL_WORK_ROOT/.index" "$CL/state/work-index" || true
}
stage_project(){ stage_tree "$REL_WORK_ROOT/$1" "$CL/state/פרויקטים/$1" "${PROJ_EXCL[@]}"; }
stage_ledger(){ mkdir -p "$CL/state/מסירות"; grep -qF "$1" "$CL/state/מסירות/ledger.txt" 2>/dev/null || echo "$1" >> "$CL/state/מסירות/ledger.txt"; }

case "${1:-}" in
  pull)
    clone
    for d in "$CL"/lib/*/; do d="${d%/}"; n="$(basename "$d")"
      [[ "$n" == "_tools-assets" ]] && deploy "$d" "$REL_HOME" || deploy "$d" "$REL_HOME/$n"; done
    for f in "${STATE_FILES[@]}"; do [[ -f "$CL/state/$f" ]] && { mkdir -p "$(dirname "$REL_HOME/$f")"; cp "$CL/state/$f" "$REL_HOME/$f"; }; done
    [[ -d "$CL/state/work-index" ]] && deploy "$CL/state/work-index" "$REL_WORK_ROOT/.index"
    log "pull ✓ ($(G rev-parse --short HEAD)) · בירולים $(find "$REL_HOME/בירולים" -type f -name '*.mp4' | wc -l) · מוזיקה $(find "$REL_HOME/brand-assets" -type f -name '*.mp3' | wc -l)" ;;
  push)
    clone
    commit_push "state: push $(date -u +%FT%TZ)" stage_state; log "push ✓" ;;
  verify-project)
    # אימות שמירה: משיכה טרייה מהשרת של תיקיית הפרויקט בלבד (sparse + partial clone).
    # שיבוט מלא של הענף (בירולים, פתיחים, ג'יגות) מילא את דיסק ה-runner ב-30.10.26 ⇒ rc=128 בכל ג'וב.
    n="$2"; out="$3"; vc="$(mktemp -d)/v"
    git clone -q --depth 1 --filter=blob:none --no-checkout --single-branch --branch "$BR" "$REPO_URL" "$vc"
    # worker._sha_saved משווה רק json — מושכים רק אותם (KB במקום GB)
    git -C "$vc" sparse-checkout set --no-cone "/state/פרויקטים/$n/**/*.json" "/state/פרויקטים/$n/**/*.json.relsplit.*"
    git -C "$vc" checkout -q "$BR"
    [[ -d "$vc/state/פרויקטים/$n" ]] || { log "אין פרויקט $n בענף"; rm -rf "$vc"; exit 6; }
    deploy "$vc/state/פרויקטים/$n" "$out/$n"; rm -rf "$(dirname "$vc")"
    log "verify-project $n ✓ ($(du -sh "$out/$n" | cut -f1))" ;;
  pull-project)
    n="$2"; clone; [[ -d "$CL/state/פרויקטים/$n" ]] || { log "אין פרויקט $n בענף"; exit 6; }
    deploy "$CL/state/פרויקטים/$n" "$REL_WORK_ROOT/$n"; log "pull-project $n ✓" ;;
  push-project)
    n="$2"; clone
    commit_push "project: $n $(date -u +%FT%TZ)" stage_project "$n"
    # אימות: מה שבענף (אחרי הרכבה) זהה בשמות וגדלים למה שהיה אמור להיכנס
    tmp="$(mktemp -d)"; ref="$(mktemp -d)"; deploy "$CL/state/פרויקטים/$n" "$tmp"
    rsync -a "${PROJ_EXCL[@]}" "$REL_WORK_ROOT/$n/" "$ref/"
    diff <(cd "$tmp" && find . -type f -printf '%P %s\n' | sort) <(cd "$ref" && find . -type f -printf '%P %s\n' | sort) >/dev/null \
      || { log "❌ אימות push-project נכשל"; rm -rf "$tmp" "$ref"; exit 7; }
    rm -rf "$ref"
    rm -rf "$tmp"; log "push-project $n ✓ (מאומת)" ;;
  archive-final)
    # ה-FINAL המתוזמן כבר יושב ב-Monday ("סרטון מוכן", file_mm402fp7) — זה הארכיון. כאן רק רישום.
    n="$2"; src="$3"; clone
    line="$(date -u +%FT%TZ) $n $(sha256sum "$src" | cut -d' ' -f1) $(stat -c%s "$src")"
    commit_push "archive-final: $n" stage_ledger "$line"; log "archive-final $n ✓ (רישום; הקובץ ב-Monday)" ;;
  *) echo "usage: $0 pull|push|pull-project N|push-project N|verify-project N OUTDIR|archive-final N PATH"; exit 2 ;;
esac

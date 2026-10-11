#!/usr/bin/env bash
# state_sync — Drive של hayonhq ↔ סשן ענן.  pull | push | push-project NAME | pull-project NAME | archive-final NAME PATH
#  ספריות/   — בירולים, מיכאל לוי, brand-assets (מוזיקה+פונטים), tools-assets (פונטים/sfx/דמו של הכלים) — read-mostly
#  מצב/      — קבצי מצב שמשתנים בריצה (רוטציית מוזיקה, usage בירולים, לקחים, אינדקס) + תיקיות פרויקט פעילות
#  מסירות/   — ארכיון FINAL שנמסרו
# כל העתקה נבדקת ב-rclone check (md5) — העתקה בלי אימות לא נחשבת.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/env.sh"
# בלי טוקן Drive (המצב הרגיל במשימות מתוזמנות) — ענף libs בריפו הפרטי. ראו cloud/libs_git.sh
[[ -z "${RCLONE_CONFIG_HAYONHQ_TOKEN:-}" || "${REL_LIBS_BACKEND:-}" == git ]] && exec bash "$HERE/libs_git.sh" "$@"
D="$REL_DRIVE_REMOTE:$REL_DRIVE_ROOT"
RC=(rclone --drive-chunk-size 64M --transfers 8 --checkers 16 --exclude .DS_Store --exclude '__pycache__/**' --log-level ERROR)
STATE_FILES=(tools/music-rotation.json tools/learn-state.json tools/illustration-ledger.json tools/hook_fx_verdicts.json
  tools/visual_hook_registry.json tools/motion/harel_verdicts.json tools/broll-tags-override.json tools/he-lexicon.json
  tools/asr-glossary.json tools/music-intro-dip.json "בירולים/catalog.json" "בירולים/usage.json")
# תוצרי ביניים שלא שורדים בין סשנים (נבנים מחדש) — לא נדחפים
PROJ_EXCL=(--exclude 'cue_*.png' --exclude 'FINAL_prev_*' --exclude 'clip_*.mp4' --exclude '_mg_snaps/**' --exclude '*.tmp' --exclude 'EXPORT+*.mp4'
  --exclude 'MIXED*.mp4' --exclude 'MG_LAYER.mov' --exclude '_insert_base.mp4' --exclude 'REVIEW_PROXY.mp4' --exclude 'INPUT.hlg.mp4' --exclude 'raw/**' --exclude '*.wav')
verify(){ rclone check "$1" "$2" --one-way "${@:3}" --log-level ERROR; }
case "${1:-}" in
  pull)
    for d in "בירולים" "בירולים - מיכאל לוי 28.5" "brand-assets"; do
      "${RC[@]}" copy "$D/ספריות/$d" "$REL_HOME/$d" --exclude '_catalog_thumbs/**'; done
    "${RC[@]}" copy "$D/ספריות/tools-assets" "$REL_HOME"          # פונטים/sfx/מודלים של הכלים, באותם נתיבים
    # פתיחים קבועים (fixed_intro.py קורא תוצרי-אנימציה/פתיחים-קבועים/catalog.json)
    "${RC[@]}" copy "$D/מסירות/תוצרי-אנימציה/פתיחים-קבועים" "$REL_HOME/תוצרי-אנימציה/פתיחים-קבועים" 2>/dev/null || true
    for f in "${STATE_FILES[@]}"; do "${RC[@]}" copyto "$D/מצב/$f" "$REL_HOME/$f" 2>/dev/null || true; done
    "${RC[@]}" copy "$D/מצב/work-index" "$REL_WORK_ROOT/.index" 2>/dev/null || true
    echo "[state_sync] pull ✓" ;;
  push)
    for f in "${STATE_FILES[@]}"; do [[ -f "$REL_HOME/$f" ]] && "${RC[@]}" copyto "$REL_HOME/$f" "$D/מצב/$f"; done
    [[ -d "$REL_WORK_ROOT/.index" ]] && "${RC[@]}" copy "$REL_WORK_ROOT/.index" "$D/מצב/work-index"
    echo "[state_sync] push ✓" ;;
  pull-project)
    n="$2"; "${RC[@]}" copy "$D/מצב/פרויקטים/$n" "$REL_WORK_ROOT/$n"; echo "[state_sync] pull-project $n ✓" ;;
  push-project)
    n="$2"; "${RC[@]}" copy "$REL_WORK_ROOT/$n" "$D/מצב/פרויקטים/$n" "${PROJ_EXCL[@]}"
    verify "$REL_WORK_ROOT/$n" "$D/מצב/פרויקטים/$n" "${PROJ_EXCL[@]}"; echo "[state_sync] push-project $n ✓ (md5)" ;;
  archive-final)
    n="$2"; src="$3"; dst="$D/מסירות/ענן/$(date +%Y-%m)/$n"
    "${RC[@]}" copy "$src" "$dst"; rclone check "$(dirname "$src")" "$dst" --one-way --include "$(basename "$src")" --log-level ERROR
    echo "[state_sync] archive-final $n ✓ (md5)" ;;
  *) echo "usage: $0 pull|push|pull-project N|push-project N|archive-final N PATH"; exit 2 ;;
esac

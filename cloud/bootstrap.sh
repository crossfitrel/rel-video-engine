#!/usr/bin/env bash
# bootstrap — מכין סשן ענן נקי להרצת מערכת עריכת הסושיאל. אידמפוטנטי.
#   bash cloud/bootstrap.sh            # הכל
#   bash cloud/bootstrap.sh --no-drive # בלי משיכה מ-Drive (בדיקות קוד בלבד)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/env.sh"
T0=$(date +%s); log(){ echo "[bootstrap +$(( $(date +%s)-T0 ))s] $*"; }
NO_DRIVE=0; [[ "${1:-}" == "--no-drive" ]] && NO_DRIVE=1

# 1. מערכת: ffmpeg (עם libass/harfbuzz), rclone, פונטים
need_apt=()
command -v ffmpeg >/dev/null || need_apt+=(ffmpeg)
command -v fc-cache >/dev/null || need_apt+=(fontconfig)
command -v rsync >/dev/null || need_apt+=(rsync)       # libs_git (ענף הספריות)
if ((${#need_apt[@]})); then log "apt: ${need_apt[*]}"; apt-get update -qq && apt-get install -y -qq "${need_apt[@]}" >/dev/null; fi
FF="$(ffmpeg -hide_banner -filters 2>/dev/null || true)"; grep -qE ' (subtitles|ass) ' <<<"$FF" && log "ffmpeg: libass ✓" || log "ffmpeg: אין libass (הכתוביות ב-PIL — לא חוסם)"
if ! command -v rclone >/dev/null; then
  log "rclone"; tmp=$(mktemp -d); (cd "$tmp" && curl -fsSLO https://downloads.rclone.org/rclone-current-linux-amd64.zip \
    && python3 -m zipfile -e rclone-current-linux-amd64.zip . && install -m755 rclone-*-linux-amd64/rclone /usr/local/bin/rclone); rm -rf "$tmp"
fi

# 2. venv ~/.rel-whisper — אותן גרסאות כמו במק (pip freeze 10.10.26)
if [[ ! -x "$REL_PY" ]]; then log "venv"; python3 -m venv "$HOME/.rel-whisper"; fi
"$REL_PY" -m pip install -q --upgrade pip >/dev/null
"$REL_PY" -m pip install -q -r "$HERE/requirements-cloud.txt"
log "python deps ✓ ($("$REL_PY" --version))"

# 3. מודל ASR — ivrit-ai turbo ct2 (זהה למק; VAD מובנה ב-faster-whisper)
"$REL_PY" - <<'PY'
from huggingface_hub import snapshot_download
p = snapshot_download("ivrit-ai/whisper-large-v3-turbo-ct2")
print("[bootstrap] model:", p)
PY

# 3b. puppeteer-core לשכבת ה-MG (node_modules לא בריפו)
( cd "$REL_HOME/tools/illustration" && [[ -d node_modules/puppeteer-core ]] || npm ci --silent ) && log "puppeteer ✓ (CHROME_PATH=${CHROME_PATH:-?})"

# 4. תאימות לנתיבי מק היסטוריים בקונפיגים (רשת ביטחון, לא מנגנון ראשי)
bash "$HERE/mac_compat.sh"

# 5. ספריות + מצב — ענף libs בריפו הפרטי (בלי טוקן); Drive רק אם יש RCLONE_CONFIG_HAYONHQ_TOKEN
mkdir -p "$REL_WORK_ROOT"
if (( NO_DRIVE )); then log "Drive: דילוג (--no-drive)";
else
  bash "$HERE/state_sync.sh" pull || { log "⚠️ משיכת ספריות/מצב נכשלה"; exit 3; }   # ענף libs (ברירת מחדל) או Drive כשיש טוקן
fi

# 6. פונטים למערכת (fontconfig) — מהספריות שנמשכו
mkdir -p "$HOME/.fonts"
find "$REL_HOME/brand-assets" "$REL_HOME/tools/thumbnail/fonts" -maxdepth 2 -type f \( -iname '*.ttf' -o -iname '*.otf' \) -exec cp -n {} "$HOME/.fonts/" \; 2>/dev/null || true
fc-cache -f >/dev/null 2>&1 || true
log "fonts: $(ls "$HOME/.fonts" 2>/dev/null | wc -l)"
log "מוכן. REL_HOME=$REL_HOME WORK=$REL_WORK_ROOT"

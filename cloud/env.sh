# מקור אמת אחד לנתיבים בענן. source cloud/env.sh (bootstrap עושה את זה לבד).
# אין נתיבי מק בקוד הענן: כל נתיב נגזר מכאן. נתיבי מק היסטוריים בקונפיגים ישנים
# מנותבים לכאן דרך שכבת התאימות (cloud/mac_compat.sh) — רק כרשת ביטחון.
export REL_HOME="${REL_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)}"   # שורש הריפו = SYSDIR
export REL_WORK_ROOT="${REL_WORK_ROOT:-$HOME/rel-video-work}"                         # ביניים + פרויקטים
export REL_PY="${REL_PY:-$HOME/.rel-whisper/bin/python}"                               # venv אחד לכל הכלים
export REL_ASR_BACKEND="${REL_ASR_BACKEND:-ct2}"                                       # אין MLX בענן
export REL_DRIVE_REMOTE="${REL_DRIVE_REMOTE:-hayonhq}"                                 # rclone remote (Drive של hayonhq)
export REL_DRIVE_ROOT="${REL_DRIVE_ROOT:-REL Video Cloud}"
export REL_RUNTIME=cloud
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
# טוקן Drive מגיע רק ממשתני סביבה של סביבת הענן (לא מקובץ בריפו):
#   RCLONE_CONFIG_HAYONHQ_TYPE=drive  RCLONE_CONFIG_HAYONHQ_SCOPE=drive  RCLONE_CONFIG_HAYONHQ_TOKEN='{...}'
export RCLONE_CONFIG_HAYONHQ_TYPE="${RCLONE_CONFIG_HAYONHQ_TYPE:-drive}"
export RCLONE_CONFIG_HAYONHQ_SCOPE="${RCLONE_CONFIG_HAYONHQ_SCOPE:-drive}"

#!/bin/bash
set -e
cd "/sessions/magical-confident-darwin/mnt/Social Video Editing System/_carnival_work"
ROOT="קרנבל הקיץ יולי אוגוסט 2026"
declare -A MAP=(
  ["v1"]="הכרזה + אתגר ראשון קפיצות בחבל"
  ["v2"]="אתגר שני  - ברפיז"
  ["v3"]="אתגר שלישי - תלייה על המתח"
  ["v4"]="אתגר רביעי -  לימבו"
)
for key in v1 v2 v3 v4; do
  folder="${MAP[$key]}"
  partsdir="_build/${key}_parts"
  rm -rf "$partsdir"; mkdir -p "$partsdir"
  listfile="_build/${key}_list.txt"; : > "$listfile"
  i=0
  while IFS= read -r clip; do
    i=$((i+1))
    out=$(printf "%s/%03d.mp4" "$partsdir" "$i")
    # detect audio
    has_a=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$clip" 2>/dev/null | head -1)
    if [ -n "$has_a" ]; then
      ffmpeg -y -loglevel error -i "$clip" \
        -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30" \
        -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
        -c:a aac -ar 48000 -ac 2 -b:a 128k "$out"
    else
      ffmpeg -y -loglevel error -i "$clip" -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
        -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30" \
        -map 0:v:0 -map 1:a:0 -shortest \
        -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p \
        -c:a aac -ar 48000 -ac 2 -b:a 128k "$out"
    fi
    echo "file '$PWD/$out'" >> "$listfile"
  done < <(find "$ROOT/$folder" -maxdepth 1 -name "*.mov" ! -name "._*" | sort)
  # concat
  ffmpeg -y -loglevel error -f concat -safe 0 -i "$listfile" -c copy "_out/${key}_assembled.mp4"
  dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "_out/${key}_assembled.mp4")
  sz=$(stat -c%s "_out/${key}_assembled.mp4")
  echo "DONE $key dur=$dur size=$sz" >> _build/progress.log
done
echo "ALL_DONE" >> _build/progress.log

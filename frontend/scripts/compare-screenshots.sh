#!/usr/bin/env bash
# Compare two directories of same-named PNG screenshots (needs ImageMagick: compare + identify).
#   scripts/compare-screenshots.sh <base_dir> <head_dir> <diff_out_dir>
# Prints a Markdown table (also appended to $GITHUB_STEP_SUMMARY). Exit code is 0 unless VISUAL_FAIL_ABOVE_PCT is
# set and some page differs by more than that percentage of pixels (or is missing / a different size).
#   VISUAL_FUZZ            per-pixel colour tolerance (default 3%): absorbs sRGB-vs-oklch rounding and AA noise
#   VISUAL_REVIEW_ABOVE_PCT pages above this are flagged for review (default 0.5)
set -uo pipefail

BASE="${1:?base dir}"; HEAD="${2:?head dir}"; OUT="${3:?diff out dir}"
FUZZ="${VISUAL_FUZZ:-3%}"; REVIEW="${VISUAL_REVIEW_ABOVE_PCT:-0.5}"; FAIL="${VISUAL_FAIL_ABOVE_PCT:-}"
mkdir -p "$OUT"

rows=(); flagged=0; failed=0; total=0
shopt -s nullglob
files=("$BASE"/*.png)
[ ${#files[@]} -gt 0 ] || { echo "No screenshots found in $BASE" >&2; exit 2; }

for b in "${files[@]}"; do
  name=$(basename "$b"); h="$HEAD/$name"; total=$((total+1))
  if [ ! -f "$h" ]; then
    rows+=("| $name | - | - | - | - | ❌ missing in head |"); flagged=$((flagged+1)); failed=$((failed+1)); continue
  fi
  bs=$(identify -format '%wx%h' "$b"); hs=$(identify -format '%wx%h' "$h")
  if [ "$bs" != "$hs" ]; then
    rows+=("| $name | $bs | $hs | - | - | ⚠️ page size changed |"); flagged=$((flagged+1)); failed=$((failed+1)); continue
  fi
  w=${bs%x*}; ht=${bs#*x}
  # `compare` exits 1 when images differ and prints the metric on stderr; both are expected here.
  raw=$(compare -metric AE -fuzz "$FUZZ" "$b" "$h" "$OUT/diff-$name" 2>&1 || true)
  px=$(awk -v v="${raw%% *}" 'BEGIN{printf "%.0f", v+0}')
  pct=$(awk -v p="$px" -v w="$w" -v h="$ht" 'BEGIN{printf "%.3f", 100*p/(w*h)}')
  if [ "$px" -eq 0 ]; then
    result="✅ identical"; rm -f "$OUT/diff-$name"
  elif awk -v p="$pct" -v r="$REVIEW" 'BEGIN{exit !(p<=r)}'; then
    result="🟡 minor"
  else
    result="🔴 review"; flagged=$((flagged+1))
  fi
  if [ -n "$FAIL" ] && awk -v p="$pct" -v f="$FAIL" 'BEGIN{exit !(p>f)}'; then failed=$((failed+1)); fi
  rows+=("| $name | $bs | $hs | $px | $pct | $result |")
done

{
  echo "### Visual comparison: base vs branch (fuzz $FUZZ, review above ${REVIEW}% of pixels)"
  echo
  echo "| page | base size | head size | differing px | % | result |"
  echo "|---|---|---|---|---|---|"
  printf '%s\n' "${rows[@]}"
  echo
  echo "**$total compared, $flagged flagged for review.** Diff images (changed pixels in red) are in the \`visual-comparison\` artifact under \`diff/\`."
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"

[ -n "$FAIL" ] && [ "$failed" -gt 0 ] && exit 1
exit 0

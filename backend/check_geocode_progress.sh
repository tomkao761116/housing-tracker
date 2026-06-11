#!/bin/bash
# 監控地理編碼批次任務進度，回報新完成的縣市
# Pure bash — no Python needed

LOG_FILE="/tmp/geocode_v8_20260527.log"
STATE_FILE="/tmp/geocode_v8_last_done_city"

[ ! -f "$LOG_FILE" ] && exit 0

done_cities=()
while IFS= read -r city; do
    done_cities+=("$city")
done < <(grep -oP '(?<=--- DONE ).*(?= ---)' "$LOG_FILE")

[ ${#done_cities[@]} -eq 0 ] && exit 0

last_idx=0
[ -f "$STATE_FILE" ] && last_idx=$(cat "$STATE_FILE")

new_count=$(( ${#done_cities[@]} - last_idx ))
[ "$new_count" -le 0 ] && exit 0

total_coords=$(grep -oP '✅ 已解析:\s*\K[\d,]+' "$LOG_FILE" | tail -1 | tr -d ',')
total_null=$(grep -oP '❌ 仍為 NULL:\s*\K[\d,]+' "$LOG_FILE" | tail -1 | tr -d ',')

total=$(( total_coords + total_null ))
if [ "$total" -gt 0 ]; then
    pct=$(awk "BEGIN {printf \"%.1f\", ($total_coords / $total) * 100}")
else
    pct="0.0"
fi

msg="📍 **地理編碼進度更新**\n"

i=$last_idx
while [ $i -lt ${#done_cities[@]} ]; do
    msg="${msg}✅ ${done_cities[$i]}\n"
    i=$((i + 1))
done

fmt_num() { echo "$1" | sed ':a;s/\B[0-9]\{3\}\>/,&/;ta'; }

msg="${msg}\n✅ 已有座標: $(fmt_num $total_coords) / $(fmt_num $total) (${pct}%)\n"

completed_list=$(IFS=', '; echo "${done_cities[*]}")
msg="${msg}已完成縣市 (${#done_cities[@]}/18): ${completed_list}"

echo -e "$msg"

echo "${#done_cities[@]}" > "$STATE_FILE"

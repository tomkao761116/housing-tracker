#!/bin/bash
# 監控地理編碼批次任務進度，回報新完成的縣市
# Pure bash — no Python needed

LOG_FILE="/tmp/geocode_v8_20260527.log"
STATE_FILE="/tmp/geocode_v8_last_done_city"

# Log 不存在就靜默退出
[ ! -f "$LOG_FILE" ] && exit 0

# 找出所有 "--- DONE xxx ---" 行
done_cities=()
while IFS= read -r city; do
    done_cities+=("$city")
done < <(grep -oP '(?<=--- DONE ).*(?= ---)' "$LOG_FILE")

[ ${#done_cities[@]} -eq 0 ] && exit 0

# 讀取上次回報到哪個
last_idx=0
[ -f "$STATE_FILE" ] && last_idx=$(cat "$STATE_FILE")

new_count=$(( ${#done_cities[@]} - last_idx ))
[ "$new_count" -le 0 ] && exit 0

# 從 log 最後一輪統計數字解析
total_coords=$(grep -oP '✅ 已解析:\s*\K[\d,]+' "$LOG_FILE" | tail -1 | tr -d ',')
total_null=$(grep -oP '❌ 仍為 NULL:\s*\K[\d,]+' "$LOG_FILE" | tail -1 | tr -d ',')

total=$(( total_coords + total_null ))
if [ "$total" -gt 0 ]; then
    pct=$(awk "BEGIN {printf \"%.1f\", ($total_coords / $total) * 100}")
else
    pct="0.0"
fi

# 組裝訊息
msg="📍 **地理編碼進度更新**\n"

i=$last_idx
while [ $i -lt ${#done_cities[@]} ]; do
    msg="${msg}✅ ${done_cities[$i]}\n"
    i=$((i + 1))
done

msg="${msg}\n✅ 已有座標: $(echo $total_coords | sed 's/\(...\)$/,\1/g' | sed 's/,$//') / $(echo $total | sed 's/\(...\)$/,\1/g' | sed 's/,$//') (${pct}%)\n"

completed_list=$(IFS=', '; echo "${done_cities[*]}")
msg="${msg}已完成縣市 (${#done_cities[@]}/18): ${completed_list}"

echo -e "$msg"

# 更新狀態
echo "${#done_cities[@]}" > "$STATE_FILE"

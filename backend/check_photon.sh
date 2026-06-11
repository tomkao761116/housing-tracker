#!/bin/bash
# 檢查 Photon API 是否恢復，若恢復則啟動 v4 geocoding

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 檢查 Photon API 狀態..."

# 測試連線
HTTP_CODE=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "https://photon.komoot.io/api/?q=Taipei&limit=1")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Photon API 已恢復！準備啟動 v4..."
    
    # 檢查 v4 是否已在運行
    if pgrep -f "batch_geocode_v4.py" > /dev/null; then
        echo "⚠️  v4 已在運行中 (PID: $(pgrep -f batch_geocode_v4.py))"
        exit 0
    fi
    
    # 啟動 v4
    cd /opt/data/home/housing-tracker/backend
    nohup python3 batch_geocode_v4.py >> /tmp/geocode_v4_run.log 2>&1 &
    echo "🚀 v4 已啟動 (PID: $!)"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Photon 恢復，v4 已自動啟動" >> /tmp/photon_monitor.log
else
    echo "❌ Photon API 仍無法連線 (HTTP $HTTP_CODE)"
fi

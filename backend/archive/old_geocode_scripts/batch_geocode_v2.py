#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次 Geocoding v2 — 差異更新（Photon API + donma 對照表 + 流式處理）

核心策略：
1. 中文地址 → donma 官方對照表 → Photon API geocode
2. **雙連線設計**：讀取 cursor 與寫入 DB 使用獨立連線，避免 commit 關閉 cursor
3. Server-side cursor 流式讀取唯一地址（不一次性載入記憶體）
4. 每 BATCH_SIZE 筆 geocode 完立即寫入 DB + commit，避免 geo_cache 膨脹
5. Commit 間加入短暫延遲，讓 PostgreSQL WAL/Checkpoint 有時間消化
6. 過濾地號/建號等非門牌地址，避免無效 API 呼叫
7. 請求間隔 2.5 秒，降低 Photon 公開 API 觸發限流的風險

I/O 安全設計：
- 雙連線：read_conn (server-side cursor) / write_conn (batch UPDATE + commit)
- Server-side cursor (yield_per)：只保留當前批次在記憶體
- 小批次 commit（500 筆）：控制 WAL 產生速率
- synchronous_commit OFF（寫入連線）：減少每次 commit 的 fsync 開銷
- commit 後 sleep 0.5s：避免 checkpoint 集中觸發

Usage:
    python batch_geocode_v2.py              # 正式執行
    python batch_geocode_v2.py --dry-run    # 只預覽前 20 筆，不寫入 DB
    python batch_geocode_v2.py --test N     # 測試前 N 個唯一地址
"""
import sys
import time
import json
import urllib.request
import urllib.parse
import psycopg2

# 強制 stdout 不 buffer（方便背景執行時看 log）
sys.stdout.reconfigure(line_buffering=True)

# 匯入地址轉換模組（donma 對照表 + Regex 解析）
from utils.chinese_to_english import chinese_to_english, is_land_parcel

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

DRY_RUN = '--dry-run' in sys.argv
TEST_LIMIT = None
for i, arg in enumerate(sys.argv):
    if arg == '--test' and i + 1 < len(sys.argv):
        TEST_LIMIT = int(sys.argv[i + 1])

BATCH_SIZE = 500       # 每 N 筆 geocode 完就寫入 DB
REQUEST_DELAY = 2.5    # Photon 請求間隔（秒）
COMMIT_PAUSE = 0.5     # commit 後暫停（秒），讓 WAL/Checkpoint 消化


def query_photon(query: str) -> tuple | None:
    """查詢 Photon API，回傳 (lat, lon) 或 None"""
    url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=1"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            features = data.get('features', [])
            if features:
                coords = features[0]['geometry']['coordinates']  # [lon, lat]
                return (float(coords[1]), float(coords[0]))
    except Exception:
        pass
    return None


def geocode_address(address: str) -> tuple | None:
    """
    Geocode 一個地址，回傳 (lat, lon) 或 None
    
    策略：
    1. 先用 chinese_to_english 轉為 Photon 格式（donma 對照表優先）
    2. 若失敗，再用原始中文地址嘗試
    """
    # 策略 1: donma 轉換後的英文地址
    english_addr = chinese_to_english(address)
    if english_addr and english_addr != "Taiwan":
        result = query_photon(english_addr)
        if result:
            return result
    
    # 策略 2: 原始中文地址
    result = query_photon(f"{address}, Taiwan")
    if result:
        return result
    
    return None


def main():
    print("=" * 60)
    print("批次 Geocoding v2 — 差異更新（Photon + donma）")
    print("=" * 60)
    if DRY_RUN:
        print("⚠️  DRY-RUN 模式：只預覽前 20 筆，不寫入 DB")
    if TEST_LIMIT:
        print(f"🧪 TEST 模式：只測試前 {TEST_LIMIT} 個唯一地址")
    print()

    # ============================================
    # 雙連線設計：讀取與寫入分離
    # ============================================
    # read_conn: server-side cursor 流式讀取
    #   - autocommit=False：named cursor 必須在 transaction 內（psycopg2 自動開）
    #   - 只讀不寫，所以 transaction 一直開著沒問題
    read_conn = psycopg2.connect(DB_URL)
    read_conn.autocommit = False
    
    # write_conn: 批次寫入（synchronous_commit=OFF 減少 fsync 開銷）
    write_conn = psycopg2.connect(DB_URL)
    write_conn.autocommit = False
    write_cur = write_conn.cursor()
    write_cur.execute("SET synchronous_commit = OFF")
    write_conn.commit()
    
    stats_cur = read_conn.cursor()

    # ============================================
    # Step 1: 統計目前狀態
    # ============================================
    stats_cur.execute("SELECT COUNT(*) FROM trades")
    total = stats_cur.fetchone()[0]

    stats_cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")
    has_coords = stats_cur.fetchone()[0]

    needs_geo = total - has_coords
    print(f"Step 1: 統計")
    print(f"  總筆數: {total:,}")
    print(f"  已有座標: {has_coords:,}")
    print(f"  需 Geocoding: {needs_geo:,}")
    print()

    if needs_geo == 0:
        print("✅ 全部已完成！")
        stats_cur.close()
        read_conn.close()
        write_cur.close()
        write_conn.close()
        return

    # ============================================
    # Step 2: Server-side cursor 流式讀取唯一地址
    # ============================================
    print("Step 2: 建立 Server-side cursor（流式讀取）...")
    
    server_cursor_name = 'geocode_stream'
    unique_query = """
        SELECT t.city, t.district, t.address, COUNT(*) as trade_count
        FROM trades t
        WHERE (t.lat IS NULL OR t.lon IS NULL)
        AND t.address IS NOT NULL
        AND LENGTH(t.address) >= 5
        AND t.address NOT LIKE '%%地號%%'
        AND t.address NOT LIKE '%%建號%%'
        GROUP BY t.city, t.district, t.address
        ORDER BY trade_count DESC
    """
    
    if TEST_LIMIT:
        unique_query += f" LIMIT {TEST_LIMIT}"

    # 命名 cursor 必須在 autocommit=True 下才能持久化
    server_cur = read_conn.cursor(server_cursor_name)
    server_cur.itersize = BATCH_SIZE
    server_cur.execute(unique_query)
    
    print(f"  ✓ Server-side cursor '{server_cursor_name}' 已建立")
    print(f"  預估時間: ~{BATCH_SIZE * REQUEST_DELAY / 3600:.1f}h / 批次")
    print()

    if DRY_RUN and not TEST_LIMIT:
        print("DRY-RUN: 只測試前 20 筆\n")

    # ============================================
    # Step 3: 流式 geocode + 批次寫入
    # ============================================
    print("Step 3: 開始 Geocoding（流式處理，每批立即寫入 DB）...")
    print()

    geo_success = 0
    geo_failed = 0
    skipped_land = 0
    total_updated = 0
    batch_num = 0
    global_idx = 0
    start_time = time.time()

    dry_run_count = 0
    dry_run_limit = 20 if DRY_RUN else 0

    while True:
        batch = server_cur.fetchmany(BATCH_SIZE)
        if not batch:
            break
        
        if DRY_RUN and not TEST_LIMIT and dry_run_count >= dry_run_limit:
            break

        batch_results = []
        
        for city, district, address, trade_count in batch:
            global_idx += 1
            
            display_addr = address[:40].replace('\n', ' ')
            print(f"[{global_idx}] {trade_count}x | {display_addr}...", end=" → ")

            if is_land_parcel(address):
                skipped_land += 1
                print("⊘ 地號/建號（跳過）")
                continue

            result = geocode_address(address)

            if result:
                lat, lon = result
                batch_results.append((city or '', district or '', address, lat, lon))
                geo_success += 1
                print(f"✓ ({lat:.4f}, {lon:.4f})")
            else:
                geo_failed += 1
                print("✗ 找不到")

            time.sleep(REQUEST_DELAY)
            
            if DRY_RUN:
                dry_run_count += 1
                if dry_run_count >= dry_run_limit:
                    break

        # ── 批次寫入 DB（使用獨立 write_conn，不影響 read cursor）──
        if batch_results and not DRY_RUN:
            for (u_city, u_district, u_addr, u_lat, u_lon) in batch_results:
                write_cur.execute("""
                    UPDATE trades SET lat = %s, lon = %s
                    WHERE address = %s
                    AND city = %s
                    AND district = %s
                    AND (lat IS NULL OR lon IS NULL)
                """, (u_lat, u_lon, u_addr, u_city, u_district))
                total_updated += write_cur.rowcount
            
            write_conn.commit()
            batch_num += 1
            elapsed = time.time() - start_time
            
            print(f"  💾 Batch #{batch_num}: {len(batch_results)} 組地址, "
                  f"累計更新 {total_updated:,} 筆 | "
                  f"成功 {geo_success} / 失敗 {geo_failed} | "
                  f"耗時 {elapsed/60:.1f}min")
            
            # Commit 後短暫暫停，讓 WAL/Checkpoint 消化
            time.sleep(COMMIT_PAUSE)
        elif batch_results and DRY_RUN:
            print(f"  ⚠️  DRY-RUN: 跳過寫入 {len(batch_results)} 筆")

    server_cur.close()

    total_time = time.time() - start_time

    print()
    print("=" * 60)
    print(f"Geocoding 完成:")
    print(f"  成功: {geo_success}")
    print(f"  失敗: {geo_failed}")
    print(f"  跳過（地號/建號）: {skipped_land}")
    print(f"  DB 更新: {total_updated:,} 筆交易")
    print(f"  耗時: {total_time/60:.1f} 分鐘")
    if total_time > 0:
        print(f"  平均速度: {(geo_success + geo_failed) / total_time:.2f} 筆/秒")
    print("=" * 60)
    print()

    # ============================================
    # Step 4: 最終統計
    # ============================================
    stats_cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")
    final_coords = stats_cur.fetchone()[0]
    
    print("最終結果:")
    print(f"  已有座標: {final_coords:,}/{total:,} ({final_coords/total*100:.1f}%)")
    print(f"  本次新增: {final_coords - has_coords:,} 筆")
    print("=" * 60)

    # 清理
    stats_cur.close()
    read_conn.close()
    write_cur.close()
    write_conn.close()
    print("\n✅ 批次處理完成！")


if __name__ == "__main__":
    main()

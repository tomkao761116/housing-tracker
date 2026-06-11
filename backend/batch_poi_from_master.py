"""
批次填充 trade_amenities — 從 poi_master 表
策略: Bounding Box JOIN + ROW_NUMBER + 批次插入
- 完全離線，不需要外部 API
- 每批 5000 筆交易，用 bbox 預篩後 JOIN poi_master
- 預估總時間: ~90 分鐘 (309萬筆 x 6分類)
"""
import sys
import time
import psycopg2
from psycopg2.extras import execute_values

# 強制行緩衝
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

DB_URL = "dbname=housing_tracker user=hermes host=localhost"

# (target_category, poi_master.category, search_radius_deg, top_n)
DIMENSIONS = [
    ("transit",   "transit",   0.009,  5),  # ~1000m
    ("education", "education", 0.014,  5),  # ~1500m
    ("medical",   "medical",   0.011,  5),  # ~1200m
    ("shopping",  "shopping",  0.007,  5),  # ~800m
    ("leisure",   "leisure",   0.009,  5),  # ~1000m
    ("dining",    "dining",    0.007,  5),  # ~800m
]

BATCH_SIZE = 5000


def main():
    print("🚀 開始批次填充 trade_amenities...")
    
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()
    
    # 統計資訊
    cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")
    total_trades = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM poi_master")
    total_pois = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trade_amenities")
    existing = cur.fetchone()[0]
    
    print(f"   Trades (有座標): {total_trades:,}")
    print(f"   POI master:      {total_pois:,}")
    print(f"   現有 amenity:    {existing:,}")
    
    print("\n🔧 使用現有空間索引 (poi_master.geom GIST)")
    
    start_time = time.time()
    total_inserted = 0
    
    for dim_idx, (target_cat, poi_cat, radius_deg, top_n) in enumerate(DIMENSIONS):
        print(f"\n{'='*60}")
        print(f"📍 [{dim_idx+1}/{len(DIMENSIONS)}] 處理: {target_cat} (半徑 ~{radius_deg*111:.0f}km)")
        
        cur.execute("SELECT COUNT(*) FROM poi_master WHERE category = %s", (poi_cat,))
        poi_count = cur.fetchone()[0]
        print(f"   POI 數量: {poi_count:,}")
        
        if poi_count == 0:
            print(f"   ⚠️  此分類無 POI 資料，跳過")
            continue
        
        dim_start = time.time()
        dim_total = 0
        
        # 分批處理
        cur.execute("""
            SELECT MIN(id), MAX(id) FROM trades
            WHERE lat IS NOT NULL AND lon IS NOT NULL
        """)
        min_id, max_id = cur.fetchone()
        print(f"   ID 範圍: {min_id:,} ~ {max_id:,}")
        
        current_id = min_id
        
        while current_id <= max_id:
            cur.execute("""
                SELECT id FROM trades
                WHERE lat IS NOT NULL AND lon IS NOT NULL
                  AND id >= %s AND id < %s
                  AND NOT EXISTS (
                      SELECT 1 FROM trade_amenities ta 
                      WHERE ta.trade_id = trades.id AND ta.category = %s
                  )
                ORDER BY id
                LIMIT %s
            """, (current_id, current_id + BATCH_SIZE, target_cat, BATCH_SIZE))
            
            trade_ids = [row[0] for row in cur.fetchall()]
            
            if not trade_ids:
                current_id += BATCH_SIZE
                continue
            
            # 直接從 SQL 插入（不經 Python，避免 execute_values 問題）
            cur.execute("""
                WITH batch AS (
                    SELECT id, lat, lon FROM trades WHERE id = ANY(%s::int[])
                ),
                candidates AS (
                    SELECT 
                        b.id AS trade_id,
                        pm.name AS amenity_name,
                        pm.lat AS poi_lat,
                        pm.lon AS poi_lon,
                        ROUND(ST_Distance(
                            ST_SetSRID(ST_MakePoint(b.lon, b.lat), 4326)::geography,
                            pm.geom::geography
                        ))::integer AS distance,
                        ROW_NUMBER() OVER (
                            PARTITION BY b.id 
                            ORDER BY ST_Distance(
                                ST_SetSRID(ST_MakePoint(b.lon, b.lat), 4326)::geography,
                                pm.geom::geography
                            )
                        ) AS rn
                    FROM batch b
                    JOIN poi_master pm ON pm.category = %s
                        AND ABS(pm.lat - b.lat) < %s
                        AND ABS(pm.lon - b.lon) < %s
                )
                INSERT INTO trade_amenities 
                    (trade_id, category, amenity_name, distance, lat, lon, created_at, updated_at)
                SELECT trade_id, %s, COALESCE(amenity_name, %s), distance, poi_lat, poi_lon, NOW(), NOW()
                FROM candidates
                WHERE rn <= %s
                  AND amenity_name IS NOT NULL
                  AND distance IS NOT NULL
                ON CONFLICT (trade_id, category, amenity_name) DO NOTHING
            """, (trade_ids, poi_cat, radius_deg, radius_deg, target_cat, target_cat, top_n))
            
            inserted = cur.rowcount
            conn.commit()
            
            if inserted > 0:
                dim_total += inserted
                elapsed = time.time() - dim_start
                rate = dim_total / elapsed if elapsed > 0 else 0
                print(f"   ✓ 批次 {current_id:,}: +{inserted} (累計 {dim_total:,}, {rate:.1f} 筆/秒)")
            
            current_id += BATCH_SIZE
        
        total_inserted += dim_total
        print(f"   ✅ {target_cat} 完成: {dim_total:,} 筆 ({time.time()-dim_start:.1f} 秒)")
    
    # 最終統計
    cur.execute("SELECT COUNT(DISTINCT trade_id) FROM trade_amenities")
    covered = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM trade_amenities")
    total_rows = cur.fetchone()[0]
    
    total_elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"✅ 全部完成！")
    print(f"   覆蓋交易數:     {covered:,}")
    print(f"   總 POI 關聯數:  {total_rows:,}")
    print(f"   本次新增:       {total_inserted:,}")
    print(f"   耗時:           {total_elapsed/60:.1f} 分鐘")
    print(f"{'='*60}")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

"""
POI 生活圈評分 — PostGIS 原生空間查詢（高效能版）
策略：直接用 poi_master + PostGIS ST_DWithin 批次計算
不需要外部 API，利用 GIST 空間索引加速

評分公式（沿用既有邏輯）：
  count_score = 100 * log2(1 + min(count/max_count, 1) * 7) / log2(8)
  dist_score  = mean(exp(-dist / (radius_m * 0.4))) * 100  (top 5)
  combined    = round(0.6 * count_score + 0.4 * dist_score)

權重：transit 0.20, education 0.15, medical 0.15, shopping 0.20, leisure 0.15, dining 0.15
"""
import time
import sys
from sqlalchemy import create_engine, text

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

DIMENSIONS = [
    {"key": "transit",   "category": "transit",   "radius_m": 1000, "max_count": 8,  "weight": 0.20},
    {"key": "education", "category": "education", "radius_m": 1500, "max_count": 6,  "weight": 0.15},
    {"key": "medical",   "category": "medical",   "radius_m": 1200, "max_count": 5,  "weight": 0.15},
    {"key": "shopping",  "category": "shopping",  "radius_m": 800,  "max_count": 8,  "weight": 0.20},
    {"key": "leisure",   "category": "leisure",   "radius_m": 1000, "max_count": 5,  "weight": 0.15},
    {"key": "dining",    "category": "dining",    "radius_m": 600,  "max_count": 10, "weight": 0.15},
]


def main():
    engine = create_engine(DB_URL, pool_size=1, pool_pre_ping=True)

    with engine.connect() as conn:
        # Step 0: Check current state
        print("=== 目前狀態 ===")
        r = conn.execute(text("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")).fetchone()
        total_with_coords = r[0]
        print(f"有座標的交易: {total_with_coords:,}")

        r = conn.execute(text("SELECT COUNT(score_overall) FROM trades")).fetchone()
        already_scored = r[0]
        print(f"已有評分的交易: {already_scored:,}")

        needs_scoring = total_with_coords - already_scored
        print(f"需要評分: {needs_scoring:,}")
        print()

        if needs_scoring <= 0:
            print("所有有座標的交易都已有評分！")
            return

        # Step 1: Create trades.geom if not exists
        print("Step 1: 建立 trades.geom 空間欄位...")
        try:
            conn.execute(text("""
                ALTER TABLE trades ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);
            """))
            conn.commit()
        except Exception as e:
            print(f"  geom 欄位錯誤: {e}")
            return

        print("  填充 geom 資料...")
        t0 = time.time()
        conn.execute(text("""
            UPDATE trades SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
            WHERE geom IS NULL AND lat IS NOT NULL AND lon IS NOT NULL;
        """))
        conn.commit()
        print(f"  完成 ({time.time()-t0:.1f}s)")

        print("  建立 GIST 索引...")
        t0 = time.time()
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_trades_geom ON trades USING GIST(geom);
        """))
        conn.commit()
        print(f"  完成 ({time.time()-t0:.1f}s)")

        # Ensure poi_master has geom index
        print("\nStep 2: 確認 poi_master.geom...")
        try:
            conn.execute(text("""
                SELECT f_geometry_column FROM geometry_columns WHERE f_table_name='poi_master' LIMIT 1;
            """)).fetchone()
            print("  poi_master.geom 已存在")
        except Exception:
            print("  建立 poi_master.geom...")
            conn.execute(text("""
                ALTER TABLE poi_master ADD COLUMN IF NOT EXISTS geom GEOMETRY(Point, 4326);
                UPDATE poi_master SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
                WHERE geom IS NULL AND lat IS NOT NULL AND lon IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_poi_master_geom ON poi_master USING GIST(geom);
            """))
            conn.commit()

        # Step 3: Compute scores per dimension
        print("\nStep 3: 批次計算各維度評分...")

        for dim in DIMENSIONS:
            key = dim["key"]
            cat = dim["category"]
            radius_m = dim["radius_m"]
            max_count = dim["max_count"]
            # Convert meters to approximate degrees for ST_DWithin
            radius_deg = radius_m / 111320

            print(f"\n  處理 {key} (半徑 {radius_m}m, max {max_count})...")
            t_dim = time.time()

            # Phase A: Count nearby POIs per trade
            sql_count = (
                "WITH nearby AS ("
                "    SELECT t.id, COUNT(p.id)::int AS cnt"
                "    FROM trades t"
                f"    JOIN poi_master p ON p.category = '{cat}'"
                f"        AND ST_DWithin(t.geom, p.geom, {radius_deg})"
                f"    WHERE t.score_{key} IS NULL"
                "      AND t.geom IS NOT NULL"
                "      AND p.geom IS NOT NULL"
                "    GROUP BY t.id"
                ") "
                f"UPDATE trades t2"
                f"SET score_{key} = ROUND("
                f"        100 * LOG(2, 1 + LEAST(n.cnt::double precision/{max_count}, 1) * 7) / LOG(2, 8)"
                "    , 1)"
                "FROM nearby n"
                "WHERE t2.id = n.id;"
            )
            result = conn.execute(text(sql_count))
            conn.commit()
            updated = result.rowcount
            print(f"    更新 {updated:,} 筆 ({time.time()-t_dim:.1f}s)")

        # Step 4: Compute overall weighted score
        print("\nStep 4: 計算加權總分...")
        t0 = time.time()
        conn.execute(text("""
            UPDATE trades
            SET score_overall = ROUND(
                    COALESCE(score_transit, 0) * 0.20
                  + COALESCE(score_education, 0) * 0.15
                  + COALESCE(score_medical, 0) * 0.15
                  + COALESCE(score_shopping, 0) * 0.20
                  + COALESCE(score_leisure, 0) * 0.15
                  + COALESCE(score_dining, 0) * 0.15
                , 1),
                score_updated_at = NOW()
            WHERE score_overall IS NULL
              AND (score_transit IS NOT NULL OR score_education IS NOT NULL 
                   OR score_medical IS NOT NULL OR score_shopping IS NOT NULL
                   OR score_leisure IS NOT NULL OR score_dining IS NOT NULL);
        """))
        conn.commit()
        print(f"  完成 ({time.time()-t0:.1f}s)")

        # Step 5: Verify results
        print("\n=== 結果驗證 ===")
        r = conn.execute(text("SELECT COUNT(score_overall) FROM trades")).fetchone()
        print(f"有總分的交易: {r[0]:,}")

        for dim in DIMENSIONS:
            key = dim["key"]
            r = conn.execute(text(f"SELECT COUNT(score_{key}) FROM trades")).fetchone()
            print(f"  {key}: {r[0]:,}")

        r = conn.execute(text("""
            SELECT MIN(score_overall), MAX(score_overall), AVG(score_overall)
            FROM trades WHERE score_overall IS NOT NULL
        """)).fetchone()
        print(f"\n總分範圍: {r[0]} ~ {r[1]}, 平均: {r[2]:.1f}")


if __name__ == "__main__":
    main()

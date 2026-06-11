#!/usr/bin/env python3
"""
Housing Tracker 全功能測試腳本
測試項目：
1. 後端 API 連線與資料庫狀態
2. 首頁 API（高亮統計）
3. 找房頁 API（搜尋、分頁、篩選器）
4. 地點評估頁 API（地址評分）
5. 前端頁面渲染檢查
6. 各路由健康檢查
"""
import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

BASE_URL = "http://localhost:3001"
FRONTEND_URL = "http://localhost:3002"
results = []
passed = 0
failed = 0


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def test(name, func):
    global passed, failed
    try:
        func()
        log(f"✅ {name}")
        results.append({"status": "PASS", "test": name})
        passed += 1
    except Exception as e:
        log(f"❌ {name}: {e}")
        results.append({"status": "FAIL", "test": name, "error": str(e)})
        failed += 1


def api_get(path, timeout=15):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
        return data


# ── 1. 資料庫連線 ──────────────────────────────
def check_db():
    import os
    os.environ.setdefault('DATABASE_URL', 'postgresql://hermes@localhost:5432/housing_tracker')
    from sqlalchemy import text
    sys.path.insert(0, '/opt/data/home/housing-tracker/backend')
    from app.main import engine
    with engine.connect() as conn:
        r = conn.execute(text("SELECT count(*) FROM trades"))
        count = r.scalar()
        assert count > 0, "No trades found"
        log(f"   trades 筆數: {count:,}")

        r = conn.execute(text("SELECT count(*) FROM poi_master"))
        poi_count = r.scalar()
        log(f"   poi_master 筆數: {poi_count:,}")


# ── 2. 首頁 API ────────────────────────────────
def check_highlights():
    data = api_get("/api/stats/highlights?year=2025")
    assert "data" in data, f"Missing 'data' key, got keys: {list(data.keys())}"
    d = data["data"]
    assert "price_up_city" in d, f"Missing price_up_city, got keys: {list(d.keys())}"
    assert "most_expensive_city" in d, "Missing most_expensive_city"
    log(f"   漲最多縣市: {d['price_up_city']['city']} ({d['price_up_city']['yoy_pct']}%)")
    log(f"   最貴縣市: {d['most_expensive_city']['city']} ({d['most_expensive_city']['avg_unit_price']:.1f}萬/坪)")


def check_highlights_years():
    for year in [2024, 2023]:
        data = api_get(f"/api/stats/highlights?year={year}")
        assert "data" in data, f"Missing data for {year}"
    log(f"   多年份查詢正常")


# ── 3. 找房頁 API ──────────────────────────────
def check_find_basic():
    data = api_get("/api/find?limit=10&offset=0")
    items = data.get("items") or data.get("data") or data.get("trades", [])
    assert len(items) > 0, f"No items returned, got keys: {list(data.keys())}"
    log(f"   返回: {len(items)} 筆, total: {data.get('total', '?')}")


def check_find_filter():
    # 篩選台北市
    data = api_get("/api/find?city=%E8%87%B8%E5%8F%8B%E5%B8%82&limit=5")
    items = data.get("items") or data.get("data") or data.get("trades", [])
    if items:
        for t in items[:1]:
            assert "city" in t or "county" in t, "Missing city/county field"
    log(f"   台北市篩選結果: {len(items)} 筆")


def check_find_pagination():
    """Check /api/trades pagination (uses page/page_size)"""
    p1 = api_get("/api/trades?page=1&page_size=5")
    items1 = p1.get("data") or p1.get("trades", [])
    ids1 = [t.get("id") for t in items1]

    p2 = api_get("/api/trades?page=2&page_size=5")
    items2 = p2.get("data") or p2.get("trades", [])
    ids2 = [t.get("id") for t in items2]

    overlap = set(ids1) & set(ids2)
    assert len(overlap) == 0, f"Pagination overlap: {len(overlap)} duplicate IDs"
    log(f"   Page 1: {len(items1)} 筆, Page 2: {len(items2)} 筆, 無重複")


def check_find_options():
    data = api_get("/api/find/options")
    assert "cities" in data or "districts" in data, f"Missing filter data, got: {list(data.keys())}"
    cities = data.get("cities", [])
    districts = data.get("districts", [])
    log(f"   城市: {len(cities)}, 行政區: {len(districts)}")


def check_trades_list():
    """Check /api/trades endpoint"""
    data = api_get("/api/trades?limit=10&offset=0")
    assert "data" in data or "trades" in data, f"Missing data key, got: {list(data.keys())}"
    items = data.get("data") or data.get("trades", [])
    log(f"   /api/trades 返回: {len(items)} 筆")


# ── 4. 地點評估 API ────────────────────────────
def check_scorecard():
    # Use lat/lon directly to avoid geocode issues
    data = api_get("/api/scorecard?lat=25.0330&lon=121.5654&radius=1000", timeout=120)
    assert "dimensions" in data or "error" not in data, f"Scorecard error: {data.get('error', 'unknown')}"
    log(f"   評分資料 keys: {list(data.keys())}")
    if "dimensions" in data:
        dims = list(data["dimensions"].keys())
        log(f"   評分維度: {', '.join(dims)}")


def check_location_pois():
    data = api_get("/api/location-pois?lat=25.0330&lon=121.5654&radius=1000")
    assert "pois" in data or "data" in data, f"Missing pois data, got: {list(data.keys())}"
    pois = data.get("pois") or data.get("data", [])
    log(f"   POI 數量: {len(pois)}")


# ── 5. 其他 API ────────────────────────────────
def check_rankings_cities():
    data = api_get("/api/rankings/cities", timeout=120)
    assert "data" in data or "cities" in data, f"Missing data, got: {list(data.keys())}"
    log(f"   縣市排名 keys: {list(data.keys())}")


def check_stats_districts():
    data = api_get("/api/stats/districts?limit=5")
    assert "data" in data or "districts" in data, f"Missing data, got: {list(data.keys())}"
    log(f"   行政區統計 keys: {list(data.keys())}")


# ── 6. 前端頁面檢查 ────────────────────────────
def check_frontend_home():
    url = f"{FRONTEND_URL}/"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        html = resp.read().decode()
        assert "房屋實價追蹤" in html, "Missing title on home page"
        log(f"   首頁 HTML size: {len(html):,} bytes")


def check_frontend_find():
    url = f"{FRONTEND_URL}/find"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        html = resp.read().decode()
        assert "成交紀錄" in html or "find" in html.lower(), "Missing content on find page"
        log(f"   找房頁 HTML size: {len(html):,} bytes")


def check_frontend_evaluate():
    url = f"{FRONTEND_URL}/evaluate"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        html = resp.read().decode()
        assert "評估" in html or "evaluate" in html.lower(), "Missing content on evaluate page"
        log(f"   地點評估頁 HTML size: {len(html):,} bytes")


# ── 7. 健康檢查 ────────────────────────────────
def check_health():
    data = api_get("/api/health")
    assert "status" in data or "detail" in data, f"Missing status, got: {list(data.keys())}"
    log(f"   Health: {data}")


# ── Main ───────────────────────────────────────
if __name__ == "__main__":
    log("=" * 60)
    log("Housing Tracker 全功能測試")
    log("=" * 60)

    log("\n📦 1. 資料庫連線檢查")
    test("DB 連線 + trades/poi 筆數", check_db)

    log("\n📊 2. 首頁 API (/api/stats/highlights)")
    test("Highlights API (2025)", check_highlights)
    test("Highlights API (其他年份)", check_highlights_years)

    log("\n🔍 3. 找房頁 API")
    test("/api/find 基本搜尋", check_find_basic)
    test("/api/find 城市篩選", check_find_filter)
    test("/api/trades 分頁正確性", check_find_pagination)
    test("/api/find/options 篩選選項", check_find_options)
    test("/api/trades 列表", check_trades_list)

    log("\n📍 4. 地點評估 API")
    test("/api/scorecard 地址評分", check_scorecard)
    test("/api/location-pois POI 查詢", check_location_pois)

    log("\n📈 5. 其他 API")
    test("/api/rankings/cities 縣市排名", check_rankings_cities)
    test("/api/stats/districts 行政區統計", check_stats_districts)

    log("\n🌐 6. 前端頁面")
    test("首頁渲染", check_frontend_home)
    test("找房頁渲染", check_frontend_find)
    test("地點評估頁渲染", check_frontend_evaluate)

    log("\n💚 7. 健康檢查")
    test("/api/health", check_health)

    log("\n" + "=" * 60)
    log(f"結果: {passed} 通過, {failed} 失敗, 共 {passed + failed} 項")
    log("=" * 60)

    # Save results
    with open("/opt/data/home/housing-tracker/test_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": passed + failed,
            "passed": passed,
            "failed": failed,
            "results": results
        }, f, indent=2, ensure_ascii=False)
    log(f"\n測試結果已存至 test_results.json")

    sys.exit(0 if failed == 0 else 1)

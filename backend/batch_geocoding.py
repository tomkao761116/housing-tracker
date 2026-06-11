#!/usr/bin/env python3
"""
Batch geocoding for trades with NULL or wrong coordinates.
Uses photon.komoot.io API (free, no key needed).

Strategy:
1. Fetch trades with NULL coords that have street addresses (not pure land)
2. Fetch trades sharing known wrong coordinates
3. Geocode via Photon API with rate limiting (30 req/s)
4. Update DB in batches
5. Delete wrong trade_amenities for corrected records
"""
import asyncio
import aiohttp
import psycopg2
import psycopg2.extras
import time
import re
from datetime import datetime

# ── Config ──
PHOTON_URL = "https://photon.komoot.io/api"
RATE_LIMIT_DELAY = 0.035  # ~28 req/s, under 30 limit
MAX_RETRIES = 3
BATCH_SIZE = 500  # DB update batch size

# Known wrong coordinate clusters to fix
WRONG_COORDS = [
    (24.5647667, 120.8205167),   # 56,531 records
    (24.1586239, 120.644867),    # 16,834
    (22.6828017, 120.487928),    # 16,404
    (23.4591664, 120.2930004),   # 14,798
    (23.4811089, 120.4535412),   # 14,378
]

# Admin area bounding boxes for validation (loose bounds)
ADMIN_BOUNDS = {
    "基隆市": (25.0, 25.3, 121.5, 121.9),
    "新北市": (24.9, 25.3, 121.0, 121.7),
    "臺北市": (25.0, 25.3, 121.4, 121.6),
    "桃園市": (24.8, 25.1, 121.0, 121.7),
    "新竹縣": (24.6, 24.9, 120.9, 121.2),
    "新竹市": (24.7, 24.8, 120.9, 121.0),
    "苗栗縣": (24.3, 24.7, 120.7, 121.1),
    "臺中市": (24.0, 24.5, 120.5, 121.0),
    "彰化縣": (23.7, 24.1, 120.3, 120.7),
    "南投縣": (23.7, 24.0, 120.6, 121.0),
    "雲林縣": (23.4, 23.8, 120.2, 120.5),
    "嘉義縣": (23.2, 23.6, 120.2, 120.6),
    "嘉義市": (23.4, 23.5, 120.4, 120.5),
    "屏東縣": (22.3, 22.8, 120.3, 120.8),
    "臺南市": (22.8, 23.3, 120.0, 120.4),
    "高雄市": (22.4, 22.9, 120.1, 120.5),
    "宜蘭縣": (24.7, 25.1, 121.6, 121.9),
    "花蓮縣": (23.6, 24.3, 121.3, 121.7),
    "臺東縣": (22.4, 23.5, 121.0, 121.5),
}


def clean_address(addr_raw, city=None, district=None):
    """Clean and normalize address for Photon API."""
    if not addr_raw:
        return None
    
    addr = addr_raw.strip()
    
    # Skip pure land plot addresses (段+地號 format)
    if re.match(r'^.*段.*地號', addr):
        return None
    
    # Convert full-width digits to half-width
    fullwidth_digits = '０１２３４５６７８９'
    halfwidth_digits = '0123456789'
    for fw, hw in zip(fullwidth_digits, halfwidth_digits):
        addr = addr.replace(fw, hw)
    
    # Convert full-width punctuation
    addr = addr.replace('．', '.').replace('，', ',').replace('、', ',')
    addr = addr.replace('－', '-').replace('～', '~')
    
    # If address already starts with county/city, use as-is
    # Otherwise prepend city + district for context
    if city and district:
        # Clean city name - remove duplicates
        city_clean = city.replace('縣', '').replace('市', '')
        dist_clean = district.replace('區', '').replace('鄉', '').replace('鎮', '').replace('市', '')
        
        # Check if address already contains the city prefix
        if not addr.startswith(city) and not addr.startswith(city_clean):
            # Build contextual prefix
            prefix = f"{city} {district}"
            addr = f"{prefix} {addr}"
    
    return addr if len(addr) > 5 else None


async def geocode_single(session, address, retry_delay=1.0):
    """Geocode a single address via Photon API."""
    for attempt in range(MAX_RETRIES):
        try:
            async with session.get(PHOTON_URL, params={
                'q': address,
                'limit': 1,
                'lang': 'zh'
            }, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    features = data.get('features', [])
                    if features:
                        props = features[0].get('properties', {})
                        geom = features[0].get('geometry', {})
                        coords = geom.get('coordinates', [])
                        if len(coords) == 2:
                            lon, lat = coords[0], coords[1]
                            return {
                                'lat': lat,
                                'lon': lon,
                                'city': props.get('city'),
                                'state': props.get('state'),
                                'country': props.get('country'),
                            }
                elif resp.status == 429:
                    # Rate limited - wait and retry
                    wait_time = retry_delay * (attempt + 1)
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    await asyncio.sleep(retry_delay * (attempt + 1))
        except (asyncio.TimeoutError, aiohttp.ClientError):
            await asyncio.sleep(retry_delay * (attempt + 1))
    
    return None


def validate_coords(lat, lon, city):
    """Validate that returned coordinates are within reasonable bounds for the city."""
    if not lat or not lon:
        return False
    
    # Basic Taiwan bounds check
    if not (21.8 <= lat <= 25.4 and 120.0 <= lon <= 122.0):
        return False
    
    # City-specific bounds check
    if city in ADMIN_BOUNDS:
        min_lat, max_lat, min_lon, max_lon = ADMIN_BOUNDS[city]
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            return False
    
    return True


async def geocode_batch(session, trades, city_map):
    """Geocode a batch of trades. Returns list of (id, lat, lon)."""
    results = []
    for trade_id, address, city in trades:
        cleaned = clean_address(address, city=city)
        if not cleaned:
            continue
        
        result = await geocode_single(session, cleaned)
        if result and validate_coords(result['lat'], result['lon'], city):
            results.append((trade_id, result['lat'], result['lon']))
        
        # Rate limiting
        await asyncio.sleep(RATE_LIMIT_DELAY)
    
    return results


def fetch_trades_to_geocode():
    """Fetch all trades that need geocoding."""
    conn = psycopg2.connect(dbname="housing_tracker", user="hermes", host="localhost")
    cur = conn.cursor()
    
    all_trades = []
    
    # 1. NULL coordinates with potential street addresses (exclude pure land plots)
    cur.execute("""
        SELECT id, address, city FROM trades 
        WHERE (lat IS NULL OR lon IS NULL)
        AND address IS NOT NULL
        AND address NOT LIKE '%段%%地號%'
        ORDER BY id;
    """)
    null_coord_trades = cur.fetchall()
    print(f"NULL座標(非土地): {len(null_coord_trades):,} 筆")
    all_trades.extend(null_coord_trades)
    
    # 2. Trades with known wrong coordinates
    for wrong_lat, wrong_lon in WRONG_COORDS:
        cur.execute("""
            SELECT id, address, city FROM trades 
            WHERE lat = %s AND lon = %s
            AND address IS NOT NULL
            AND address NOT LIKE '%段%%地號%'
            ORDER BY id;
        """, (wrong_lat, wrong_lon))
        wrong_trades = cur.fetchall()
        if wrong_trades:
            print(f"錯誤座標 ({wrong_lat}, {wrong_lon}): {len(wrong_trades):,} 筆")
            all_trades.extend(wrong_trades)
    
    cur.close()
    conn.close()
    
    return all_trades


def update_db(trade_results, total_processed):
    """Update database with geocoding results in batches."""
    conn = psycopg2.connect(dbname="housing_tracker", user="hermes", host="localhost")
    
    # First, delete wrong trade_amenities for these records
    if trade_results:
        ids = [r[0] for r in trade_results]
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM trade_amenities 
            WHERE trade_id = ANY(%s);
        """, (ids,))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        print(f"  刪除舊 POI 關聯: {deleted:,} 筆")
    
    # Update coordinates in batches
    cur = conn.cursor()
    for i in range(0, len(trade_results), BATCH_SIZE):
        batch = trade_results[i:i + BATCH_SIZE]
        for trade_id, lat, lon in batch:
            cur.execute("""
                UPDATE trades SET lat = %s, lon = %s, updated_at = NOW()
                WHERE id = %s;
            """, (lat, lon, trade_id))
        conn.commit()
        processed = min(i + BATCH_SIZE, len(trade_results))
        print(f"  已更新座標: {processed:,}/{len(trade_results):,} (總進度: {total_processed + processed:,})")
    
    cur.close()
    conn.close()


async def main():
    start_time = time.time()
    print(f"{'='*60}")
    print(f"批次地理編碼作業 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Fetch trades
    trades = fetch_trades_to_geocode()
    if not trades:
        print("沒有需要處理的交易紀錄")
        return
    
    print(f"\n總計需處理: {len(trades):,} 筆\n")
    
    # Process in chunks
    chunk_size = 200  # Process 200 at a time, save to DB
    total_success = 0
    total_fail = 0
    
    async with aiohttp.ClientSession() as session:
        for chunk_start in range(0, len(trades), chunk_size):
            chunk = trades[chunk_start:chunk_start + chunk_size]
            chunk_num = chunk_start // chunk_size + 1
            total_chunks = (len(trades) + chunk_size - 1) // chunk_size
            
            print(f"[{chunk_num}/{total_chunks}] 處理批次 {chunk_start+1}-{min(chunk_start+chunk_size, len(trades))}...")
            
            results = await geocode_batch(session, chunk)
            
            success = len(results)
            fail = len(chunk) - success
            total_success += success
            total_fail += fail
            
            elapsed = time.time() - start_time
            rate = (total_success + total_fail) / elapsed if elapsed > 0 else 0
            
            print(f"  ✓ 成功: {success}, 失敗: {fail} | 累計成功: {total_success:,} | 速度: {rate:.0f} 筆/秒")
            
            # Save to DB
            if results:
                update_db(results, total_success - success)
    
    total_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"✅ 地理編碼完成!")
    print(f"   成功: {total_success:,} 筆")
    print(f"   失敗: {total_fail:,} 筆")
    print(f"   耗時: {total_time/60:.1f} 分鐘")
    print(f"   平均速度: {total_success/total_time:.0f} 筆/秒")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())

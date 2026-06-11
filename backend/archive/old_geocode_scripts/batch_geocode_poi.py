#!/usr/bin/env python3
"""
批次 Geocoding — 差異更新版本 v2
只處理缺乏座標的紀錄，已完成的跳過不重跑

改進：
1. 中文地址 → 英文地址轉換（提高 Nominatim 解析率）
2. 批次 UPDATE（每 batch_size 筆一次 commit），減少 PostgreSQL I/O
3. Server-side cursor，避免一次性載入全部記錄到記憶體
4. 暫停 POI 查詢（後續再做）

Usage:
    python batch_geocode_poi.py          # 全跑 (geocoding only)
    python batch_geocode_poi.py --dry-run  # 只預覽，不寫入 DB
"""
import sys
import time
import json
import urllib.request
import urllib.parse
import psycopg2
from contextlib import contextmanager

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

DRY_RUN = '--dry-run' in sys.argv

# 批次大小：每 N 筆 commit 一次
BATCH_SIZE = 500

# Nominatim rate limit: 最多 1 請求/秒
REQUEST_DELAY = 1.2


# ============================================
# 中文地址 → 英文地址轉換
# ============================================

# 縣市英譯對照表（Nominatim 認得的格式）
COUNTY_ENGLISH = {
    "臺北市": "Taipei City",
    "新北市": "New Taipei City",
    "桃園市": "Taoyuan City",
    "臺中市": "Taichung City",
    "台中市": "Taichung City",
    "臺南市": "Tainan City",
    "台南市": "Tainan City",
    "高雄市": "Kaohsiung City",
    "基隆市": "Keelung City",
    "新竹市": "Hsinchu City",
    "嘉義市": "Chiayi City",
    "宜蘭縣": "Yilan County",
    "花蓮縣": "Hualien County",
    "臺東縣": "Taitung County",
    "澎湖縣": "Penghu County",
    "金門縣": "Kinmen County",
    "連江縣": "Matsu County",
    "新竹縣": "Hsinchu County",
    "苗栗縣": "Miaoli County",
    "彰化縣": "Changhua County",
    "南投縣": "Nantou County",
    "雲林縣": "Yunlin County",
    "嘉義縣": "Chiayi County",
    "屏東縣": "Pingtung County",
}

# 鄉鎮市區英譯對照表（常見行政區）
DISTRICT_ENGLISH = {
    # 臺北市
    "松山區": "Songshan District", "信義區": "Xinyi District",
    "大安區": "Da'an District", "中山區": "Zhongshan District",
    "中正區": "Zhongzheng District", "萬華區": "Wanhua District",
    "大同區": "Datong District", "北投區": "Beitou District",
    "內湖區": "Neihu District", "南港區": "Nangang District",
    "士林區": "Shilin District", "文山區": "Wenshan District",
    # 新北市
    "板橋區": "Banqiao District", "新莊區": "Xinzhuang District",
    "中和區": "Zhonghe District", "永和區": "Yonghe District",
    "土城區": "Tucheng District", "三重區": "Sanchong District",
    "新店區": "Xindian District", "汐止區": "Xizhi District",
    "蘆洲區": "Luzhou District", "五股區": "Wugu District",
    "林口區": "Linkou District", "泰山區": "Taishan District",
    "林口區": "Linkou District", "瑞芳區": "Ruifang District",
    "平溪區": "Pingxi District", "雙溪區": "Shuangxi District",
    "貢寮區": "Gongliao District", "石門區": "Shimen District",
    "三芝區": "Sanzhi District", "淡水區": "Tamsui District",
    "八里區": "Bali District", "萬里區": "Wanli District",
    "金山區": "Jinshan District", "深坑區": "Shenkeng District",
    "石碇區": "Shiding District", "坪林區": "Pinglin District",
    "烏來區": "Wulai District", "永和市": "Yonghe District",
    "中和市": "Zhonghe District", "板橋市": "Banqiao District",
    "新莊市": "Xinzhuang District", "三重市": "Sanchong District",
    "鶯歌區": "Yingge District", "樹林區": "Shulin District",
    # 桃園市
    "桃園區": "Taoyuan District", "中壢區": "Zhongli District",
    "平鎮區": "Pingzhen District", "八德區": "Bade District",
    "楊梅區": "Yangmei District", "龜山區": "Guishan District",
    "龍潭區": "Longtan District", "大溪區": "Daxi District",
    "新屋區": "Xinwu District", "觀音區": "Guanyin District",
    # 臺中市
    "西屯區": "West Tunghsiao District", "南屯區": "South Tunghsiao District",
    "北屯區": "North Tunghsiao District", "中區": "Central District",
    "東區": "East District", "南區": "South District",
    "西區": "West District", "北區": "North District",
    "太平區": "Taiping District", "大里區": "Dali District",
    "霧峰區": "Wufeng District", "豐原區": "Fengyuan District",
    "后里區": "Houli District", "神岡區": "Shengang District",
    "潭子區": "Tanzi District", "大雅區": "Daya District",
    "新社區": "Xinshe District", "石岡區": "Shigang District",
    "東勢區": "Dongshi District", "和平區": "Heping District",
    "da'安区": "Da'an District", "員林區": "Yuanlin District",
    # 臺南市
    "中西區": "Central-Western District", "東區": "East District",
    "南區": "South District", "北區": "North District",
    "安平區": "Anping District", "安南區": "Annan District",
    "永康區": "Yongkang District", "歸仁區": "Guiren District",
    "新化區": "Xinhua District", "左鎮區": "Zuozhen District",
    "玉井區": "Yujing District", "楠西區": "Nanxi District",
    "南化區": "Nanhua District", "仁德區": "Rende District",
    "關廟區": "Guanmiao District", "龍崎區": "Longqi District",
    "官田區": "Guantian District", "麻豆區": "Madou District",
    "佳里區": "Jiali District", "西港區": "Xigang District",
    "七股區": "Qigu District", "將軍區": "Jiangjun District",
    "學甲區": "Xuejia District", "北門區": "Beimen District",
    "新營區": "Xinying District", "後壁區": "Houbi District",
    "白河區": "Bohe District", "東山區": "Dongshan District",
    "六甲區": "Liujia District", "下營區": "Xiaying District",
    "柳營區": "Liuying District", "鹽水區": "Yanshui District",
    "善化區": "Shanhua District", "大內區": "Danei District",
    "山上區": "Shangshan District", "新市區": "Xinshe District",
    # 高雄市
    "新興區": "Xinxing District", "前金區": "Qianjin District",
    "苓雅區": "Lingya District", "鳳山區": "Fengshan District",
    "三民區": "Sanmin District", "左營區": "Zuoying District",
    "鼓山區": "Gushan District", "鹽埕區": "Yancheng District",
    "前鎮區": "Qianzhen District", "小港區": "Xiaogang District",
    "旗津區": "Qijin District", "前鎮區": "Qianzhen District",
    "鳥松區": "Niaosong District", "大社區": "Dashe District",
    "岡山區": "Gangshan District", "路竹區": "Luzhu District",
    "阿蓮區": "Alian District", "田寮區": "Tianliao District",
    "燕巢區": "Yanchao District", "橋頭區": "Qiaotou District",
    "梓官區": "Ziguan District", "彌陀區": "Mituo District",
    "永安區": "Yongan District", "長治區": "Changzhi District",
    "堯灣區": "Yaowan District", "林園區": "Linyuan District",
    "鳥松區": "Niaosong District", "大樹區": "Dashu District",
    "旗山區": "Qishan District", "美濃區": "Meinong District",
    "六龜區": "Liugui District", "內門區": "Neimen District",
    "杉林區": "Shanlin District", "甲仙區": "Jiaxian District",
    "桃源區": "Taoyuan District", "那瑪夏區": "Namasia District",
    "茂林區": "Maolin District",
    # 基隆市
    "仁愛區": "Ren'ai District", "信義區": "Xinyi District",
    "中正區": "Zhongzheng District", "中山區": "Zhongshan District",
    "安樂區": "Anle District", "暖暖區": "Nuannuan District",
    "七堵區": "Qidu District",
    # 新竹市
    "東區": "East District", "西區": "West District", "北區": "North District",
    # 嘉義市
    "東區": "East District", "西區": "West District",
    # 其他縣市的鄉鎮（精選常見）
    "頭份市": "Toufen Township", "頭份鎮": "Toufen Township",
    "屏東市": "Pingtung City",
    "金峰鄉": "Jinfeng Township",
    "霧臺鄉": "Wutai Township",
}

# 通用詞彙替換
COMMON_REPLACEMENTS = [
    ("段", "Section"),
    ("巷", "Lane"),
    ("弄", "Alley"),
    ("號", ""),
    ("地號", "Lot No."),
    ("建號", "Building No."),
]


def normalize_chinese_num(addr: str) -> str:
    """將中文數字轉換為阿拉伯數字"""
    num_map = {
        "零": "0", "一": "1", "二": "2", "三": "3", "四": "4",
        "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
        "十": "10", "百": "100", "千": "1000", "萬": "10000",
        "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
        "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    }
    result = []
    for ch in addr:
        result.append(num_map.get(ch, ch))
    return "".join(result)


def build_full_address(address: str, city: str = "", district: str = "") -> str:
    """建構完整地址（避免重複）"""
    addr = address.strip()
    # 移除全形空格
    addr = addr.replace(" ", "").replace("\t", "").replace("\n", "")
    
    # 如果 address 已經包含 city 和 district，直接回傳
    if city and city in addr:
        return addr
    
    # 在前面補上缺失的行政區
    parts = []
    if city and city not in addr:
        parts.append(city)
    if district and district not in addr:
        parts.append(district)
    parts.append(addr)
    
    return "".join(parts)


def translate_address(address: str, city: str = "", district: str = "") -> str:
    """將中文地址轉換為 Nominatim 可識別的英文地址"""
    if not address:
        return ""
    
    full_cn = build_full_address(address, city, district)
    addr = normalize_chinese_num(full_cn)
    
    # 提取並替換縣市
    county_en = ""
    remaining = addr
    for cn, en in COUNTY_ENGLISH.items():
        if remaining.startswith(cn):
            remaining = remaining[len(cn):]
            county_en = en
            break
    
    # 提取並替換鄉鎮市區
    district_en = ""
    for cn, en in DISTRICT_ENGLISH.items():
        if remaining.startswith(cn):
            remaining = remaining[len(cn):]
            district_en = en
            break
    
    # 替換通用詞彙
    for cn, en in COMMON_REPLACEMENTS:
        remaining = remaining.replace(cn, en)
    
    # 構建英文地址: 街道, 鄉鎮, 縣市, Taiwan
    parts = []
    if remaining.strip():
        parts.append(remaining.strip())
    if district_en:
        parts.append(district_en)
    if county_en:
        parts.append(county_en)
    parts.append("Taiwan")
    
    return ", ".join([p for p in parts if p])


def geocode_address(address: str, city: str = "", district: str = "") -> tuple | None:
    """Geocode 一個地址，回傳 (lat, lon) 或 None
    
    策略（依序嘗試）：
    1. 完整英文地址
    2. 完整中文地址（Nominatim 對台灣中文地址支援不錯）
    3. 簡化英文（只留街路+縣市）
    4. 僅縣市+鄉鎮（粗粒度 fallback）
    """
    # 策略 1: 完整英文地址
    en_addr = translate_address(address, city, district)
    if en_addr:
        result = query_nominatim(en_addr)
        if result:
            return result
    
    # 策略 2: 完整中文地址 + Taiwan
    full_cn = build_full_address(address, city, district)
    if full_cn:
        cn_query = f"{full_cn}, Taiwan"
        result = query_nominatim(cn_query)
        if result:
            return result
    
    # 策略 3: 僅縣市+鄉鎮（粗粒度）
    if city and district:
        simple_en = f"{DISTRICT_ENGLISH.get(district, district)}, {COUNTY_ENGLISH.get(city, city)}, Taiwan"
        result = query_nominatim(simple_en)
        if result:
            return result
    
    return None


def query_nominatim(query: str) -> tuple | None:
    """查詢 Nominatim API，回傳 (lat, lon) 或 None"""
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(query)}&limit=1&countrycodes=tw"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "HousingTracker/1.0 (housing-tracker@example.com)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data:
                return (float(data[0]["lat"]), float(data[0]["lon"]))
    except Exception:
        pass
    return None


def main():
    print("=" * 60)
    print("批次 Geocoding v2 — 差異更新")
    print("=" * 60)
    if DRY_RUN:
        print("⚠️  DRY-RUN 模式：只預覽，不寫入 DB")
    print()

    conn = psycopg2.connect(DB_URL)
    # 不要用 autocommit — 我們自己控制批次 commit
    conn.autocommit = False

    # 先用普通 cursor 做統計
    stats_cur = conn.cursor()
    
    # ============================================
    # Step 1: 統計目前狀態
    # ============================================
    stats_cur.execute("SELECT COUNT(*) FROM trades")
    total = stats_cur.fetchone()[0]

    stats_cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")
    has_coords = stats_cur.fetchone()[0]

    needs_geo = total - has_coords
    print(f"總筆數: {total:,}")
    print(f"已有座標: {has_coords:,}")
    print(f"需 Geocoding: {needs_geo:,}")
    print()

    if needs_geo == 0:
        print("✅ 全部已完成！")
        stats_cur.close()
        conn.close()
        return

    # ============================================
    # Step 2: 批次 Geocoding
    # ============================================
    print(f"開始 Geocoding（批次大小: {BATCH_SIZE}，延遲: {REQUEST_DELAY}s/筆）")
    print(f"預估時間: {needs_geo * REQUEST_DELAY / 3600:.1f} 小時")
    print()

    # Server-side cursor: 不會一次性載入全部
    cur = conn.cursor(name="geocode_cursor")
    cur.execute("""
        SELECT t.id, t.address, t.city, t.district 
        FROM trades t 
        WHERE t.lat IS NULL OR t.lon IS NULL
        ORDER BY t.trade_date DESC NULLS LAST
    """)

    geo_success = 0
    geo_failed = 0
    geo_skipped_empty = 0
    batch_updates = []  # (id, lat, lon)
    start_time = time.time()

    while True:
        rows = cur.fetchmany(BATCH_SIZE)
        if not rows:
            break

        for tid, addr, city, district in rows:
            elapsed = time.time() - start_time
            eta_hours = (needs_geo - geo_success - geo_failed - geo_skipped_empty) * REQUEST_DELAY / 3600
            
            # 顯示進度
            progress = geo_success + geo_failed + geo_skipped_empty
            pct = progress / needs_geo * 100 if needs_geo > 0 else 0
            print(f"[{progress}/{needs_geo}] ({pct:.1f}%) ETA: {eta_hours:.1f}h | Trade #{tid}: {addr[:30]}...", end=" → ")

            # 空地址跳過
            if not addr or len(addr.strip()) < 5:
                geo_skipped_empty += 1
                print("⊘ 空地址跳過")
                continue

            result = geocode_address(addr, city or "", district or "")

            if result:
                lat, lon = result
                batch_updates.append((lat, lon, tid))
                geo_success += 1
                print(f"✓ ({lat:.4f}, {lon:.4f})")
            else:
                geo_failed += 1
                print("✗ 找不到")

            time.sleep(REQUEST_DELAY)

        # 批次 commit
        if batch_updates:
            if not DRY_RUN:
                update_sql = "UPDATE trades SET lat = %s, lon = %s WHERE id = %s"
                for lat, lon, tid in batch_updates:
                    cur.execute(update_sql, (lat, lon, tid))
                conn.commit()
            else:
                print(f"  [DRY-RUN] 跳過 commit {len(batch_updates)} 筆")
            batch_updates.clear()

    # 最後一批
    if batch_updates:
        if not DRY_RUN:
            update_sql = "UPDATE trades SET lat = %s, lon = %s WHERE id = %s"
            for lat, lon, tid in batch_updates:
                cur.execute(update_sql, (lat, lon, tid))
            conn.commit()
        batch_updates.clear()

    total_time = time.time() - start_time

    print()
    print("=" * 60)
    print(f"Geocoding 完成:")
    print(f"  成功: {geo_success:,}")
    print(f"  失敗: {geo_failed:,}")
    print(f"  跳過（空地址）: {geo_skipped_empty:,}")
    print(f"  耗時: {total_time/60:.1f} 分鐘")
    print(f"  平均速度: {(geo_success + geo_failed) / total_time:.2f} 筆/秒")
    print("=" * 60)

    # 最終統計（用普通 cursor）
    stats_cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL")
    final_coords = stats_cur.fetchone()[0]
    print(f"\n已有座標: {final_coords:,}/{total:,} ({final_coords/total*100:.1f}%)")

    cur.close()
    stats_cur.close()
    conn.close()
    print("\n✅ 批次處理完成！")


if __name__ == "__main__":
    main()

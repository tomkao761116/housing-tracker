"""統計與趨勢 API — 使用物化視圖加速"""
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.main import get_db

router = APIRouter()


def normalize_unit_price(val):
    """Convert raw unit_price_tping to 萬/坪 (old data may be in 元/坪)"""
    if val is None:
        return None
    return round(val / 10000, 1) if val > 10000 else round(val, 1)


@router.get("/districts")
def district_stats(
    city: str = Query(None),
    year: int = Query(2025, ge=2011, le=2026),
    db: Session = Depends(get_db)
):
    """各區統計（交易量、平均單價、平均總價）— 使用物化視圖"""
    conditions = [f"year = {year}"]
    params = {}
    if city:
        conditions.append("city = :city")
        params["city"] = city

    where = ' AND '.join(conditions)

    # Aggregate from mv_yearly_stats (pre-computed per year/city/district)
    sql = f"""
        SELECT 
            district,
            sum(cnt)::int as cnt,
            round(avg(avg_unit_price)::numeric, 1) as avg_unit_price,
            round(avg(avg_total_price)::numeric, 0) as avg_total_price
        FROM mv_yearly_stats
        WHERE {where}
        GROUP BY district
        ORDER BY avg_unit_price DESC
    """
    results = db.execute(text(sql), params)
    data = []
    for r in results:
        data.append({
            "district": r[0],
            "count": r[1],
            "avg_unit_price": r[2],
            "avg_total_price": r[3],
        })
    return {"city": city, "year": year, "data": data}


@router.get("/districts/lightweight")
def district_stats_lightweight(
    city: str = Query(None),
    year: int = Query(2025, ge=2011, le=2026),
    db: Session = Depends(get_db)
):
    """輕量版各區統計 — 首頁儀表板用，使用物化視圖"""
    conditions = [f"year = {year}"]
    params = {}
    if city:
        conditions.append("city = :city")
        params["city"] = city

    where = ' AND '.join(conditions)

    sql = f"""
        SELECT 
            district,
            sum(cnt)::int as cnt,
            round(avg(avg_unit_price)::numeric, 1) as avg_unit_price,
            round(avg(avg_total_price)::numeric, 0) as avg_total_price
        FROM mv_yearly_stats
        WHERE {where}
        GROUP BY district
        ORDER BY avg_unit_price DESC
    """
    results = db.execute(text(sql), params)
    data = []
    for r in results:
        data.append({
            "district": r[0],
            "count": r[1],
            "avg_unit_price": r[2],
            "avg_total_price": r[3],
        })
    return {"city": city, "year": year, "data": data}


@router.get("/trends/monthly")
def monthly_trend(
    city: str = Query(None),
    district: str = Query(None),
    start_year: int = Query(2023, ge=2000),
    end_year: int = Query(2025, le=2030),
    db: Session = Depends(get_db)
):
    """月度趨勢 — 使用物化視圖"""
    if end_year - start_year > 4:
        end_year = start_year + 4

    conditions = [f"month >= '{start_year}-01' AND month < '{end_year+1}-01'"]
    params = {}
    if city:
        conditions.append("city = :city")
        params["city"] = city
    if district:
        conditions.append("district = :district")
        params["district"] = district

    where = ' AND '.join(conditions)

    sql = f"""
        SELECT 
            month,
            sum(cnt)::int as count,
            round(avg(avg_unit_price)::numeric, 1) as avg_unit_price,
            round(avg(avg_total_price)::numeric, 0) as avg_total_price
        FROM mv_monthly_stats
        WHERE {where}
        GROUP BY month
        ORDER BY month
    """
    results = db.execute(text(sql), params)
    return {
        "city": city,
        "district": district,
        "data": [
            {"month": r[0], "count": r[1], "avg_unit_price": r[2], "avg_total_price": r[3]}
            for r in results
        ],
    }


@router.get("/building_types")
def building_type_distribution(
    city: str = Query(None),
    year: int = Query(2025),
    db: Session = Depends(get_db)
):
    """建物型態分佈 — 使用物化視圖"""
    conditions = [f"year = {year}"]
    params = {}
    if city:
        conditions.append("city = :city")
        params["city"] = city

    where = ' AND '.join(conditions)

    sql = f"""
        SELECT 
            btype as type,
            sum(cnt)::int as count,
            round(avg(avg_unit_price)::numeric, 1) as avg_unit_price
        FROM mv_building_type_stats
        WHERE {where}
        GROUP BY btype
        ORDER BY count DESC
        LIMIT 10
    """
    results = db.execute(text(sql), params)
    return {
        "city": city,
        "year": year,
        "data": [
            {"type": r[0], "count": r[1], "avg_unit_price": r[2]}
            for r in results
        ],
    }


@router.get("/price_distribution")
def price_distribution(
    city: str = Query(None),
    district: str = Query(None),
    year: int = Query(2025),
    db: Session = Depends(get_db)
):
    """總價區間分佈 — 使用物化視圖"""
    conditions = [f"year = {year}"]
    params = {}
    if city:
        conditions.append("city = :city")
        params["city"] = city

    where = ' AND '.join(conditions)

    sql = f"""
        SELECT 
            label,
            count(*)::int as cnt
        FROM mv_price_dist_stats
        WHERE {where}
        GROUP BY label
        ORDER BY 
            CASE label
                WHEN '<300萬' THEN 1
                WHEN '300-500萬' THEN 2
                WHEN '500-800萬' THEN 3
                WHEN '800萬-1000萬' THEN 4
                WHEN '1000-1500萬' THEN 5
                WHEN '1500-2000萬' THEN 6
                WHEN '>2000萬' THEN 7
            END
    """
    results = db.execute(text(sql), params).fetchall()
    total = sum(r[1] for r in results) or 1
    
    labels_order = ["<300萬", "300-500萬", "500-800萬", "800萬-1000萬", "1000-1500萬", "1500-2000萬", ">2000萬"]
    result_dict = {r[0]: r[1] for r in results}
    
    return {
        "city": city,
        "district": district,
        "year": year,
        "data": [
            {"label": lbl, "value": round(result_dict.get(lbl, 0) / total * 100)}
            for lbl in labels_order
        ],
    }


@router.get("/building_age_distribution")
def building_age_distribution(
    city: str = Query(None),
    district: str = Query(None),
    year: int = Query(2025),
    db: Session = Depends(get_db)
):
    """屋齡分佈統計 — 僅統計房屋交易"""
    start_date = f"{year}-01-01"
    end_date = f"{year+1}-01-01"
    conditions = [f"trade_date >= '{start_date}'", f"trade_date < '{end_date}'", "building_area IS NOT NULL"]
    params = {}
    if city:
        conditions.append("city = :city")
        params["city"] = city
    if district:
        conditions.append("district = :district")
        params["district"] = district

    where = ' AND '.join(conditions)

    sql = f"""
        WITH ages AS (
            SELECT 
                CASE 
                    WHEN length(build_complete_date) >= 3 THEN
                        EXTRACT(YEAR FROM NOW()) - (1911 + CAST(SUBSTRING(build_complete_date, 1, 3) AS INT))
                    WHEN length(build_complete_date) >= 2 THEN
                        EXTRACT(YEAR FROM NOW()) - (1911 + CAST(SUBSTRING(build_complete_date, 1, 2) AS INT) + 100)
                    ELSE NULL
                END as age
            FROM trades WHERE {where} AND build_complete_date IS NOT NULL
        )
        SELECT 
            count(*)::int as total_with_age,
            sum(CASE WHEN age >= 0 AND age < 5 THEN 1 ELSE 0 END)::int as c1,
            sum(CASE WHEN age >= 5 AND age < 11 THEN 1 ELSE 0 END)::int as c2,
            sum(CASE WHEN age >= 11 AND age < 16 THEN 1 ELSE 0 END)::int as c3,
            sum(CASE WHEN age >= 16 AND age < 21 THEN 1 ELSE 0 END)::int as c4,
            sum(CASE WHEN age >= 21 AND age < 31 THEN 1 ELSE 0 END)::int as c5,
            sum(CASE WHEN age >= 31 THEN 1 ELSE 0 END)::int as c6,
            round(avg(age)::numeric, 1) as avg_age
        FROM ages WHERE age IS NOT NULL
    """
    row = db.execute(text(sql), params).fetchone()
    total = row[0] or 0
    counts = list(row[1:7])
    avg_age = row[7]
    labels = ["5年以內", "6-10年", "11-15年", "16-20年", "21-30年", "30年以上"]

    return {
        "city": city, "district": district, "year": year,
        "total_trades": total,
        "avg_building_age": avg_age,
        "data": [
            {"label": labels[i], "count": counts[i], "percentage": round(counts[i] / total * 100, 1) if total > 0 else 0}
            for i in range(6)
        ],
    }


@router.get("/cities/overview")
def cities_overview(
    year: int = Query(2025, ge=2011, le=2026),
    db: Session = Depends(get_db)
):
    """全台各縣市總覽 — 使用物化視圖"""
    sql = f"""
        SELECT 
            city,
            sum(cnt)::int as cnt,
            round(avg(avg_unit_price)::numeric, 1) as avg_unit_price,
            round(avg(avg_total_price)::numeric, 0) as avg_total_price
        FROM mv_yearly_stats
        WHERE year = {year}
        GROUP BY city
        ORDER BY cnt DESC
    """
    results = db.execute(text(sql))
    data = [
        {"city": r[0], "count": r[1], "avg_unit_price": r[2], "avg_total_price": r[3]}
        for r in results
    ]
    return {"year": year, "data": data}


@router.get("/highlights")
def highlights(
    year: int = Query(2025, ge=2011, le=2026),
    db: Session = Depends(get_db)
):
    """首頁亮點卡片：年增/年減最多、最便宜 的縣市與行政區"""
    prev_year = year - 1

    # City-level YoY change (weighted by transaction count)
    city_yoy_sql = f"""
        WITH cur AS (
            SELECT city, round(sum(avg_unit_price * cnt) / sum(cnt)::numeric, 1) as avg_unit_price
            FROM mv_yearly_stats WHERE year = {year}
            GROUP BY city
        ),
        prv AS (
            SELECT city, round(sum(avg_unit_price * cnt) / sum(cnt)::numeric, 1) as avg_unit_price
            FROM mv_yearly_stats WHERE year = {prev_year}
            GROUP BY city
        )
        SELECT c.city, c.avg_unit_price, p.avg_unit_price as prev_price,
               round(((c.avg_unit_price - p.avg_unit_price) / p.avg_unit_price * 100)::numeric, 1) as yoy_pct
        FROM cur c JOIN prv p ON c.city = p.city
        WHERE p.avg_unit_price > 0
    """
    city_yoy_rows = db.execute(text(city_yoy_sql)).fetchall()

    # District-level YoY change (weighted by transaction count, min 3 transactions)
    dist_yoy_sql = f"""
        WITH cur AS (
            SELECT district, city, round(sum(avg_unit_price * cnt) / sum(cnt)::numeric, 1) as avg_unit_price, sum(cnt)::int as total_cnt
            FROM mv_yearly_stats WHERE year = {year}
            GROUP BY district, city
            HAVING sum(cnt) >= 3
        ),
        prv AS (
            SELECT district, city, round(sum(avg_unit_price * cnt) / sum(cnt)::numeric, 1) as avg_unit_price, sum(cnt)::int as total_cnt
            FROM mv_yearly_stats WHERE year = {prev_year}
            GROUP BY district, city
            HAVING sum(cnt) >= 3
        )
        SELECT c.district, c.city, c.avg_unit_price, p.avg_unit_price as prev_price,
               round(((c.avg_unit_price - p.avg_unit_price) / p.avg_unit_price * 100)::numeric, 1) as yoy_pct,
               c.total_cnt as cur_cnt, p.total_cnt as prev_cnt
        FROM cur c JOIN prv p ON c.district = p.district AND c.city = p.city
        WHERE p.avg_unit_price > 0
    """
    dist_yoy_rows = db.execute(text(dist_yoy_sql)).fetchall()

    # Cheapest city & district (current year, weighted)
    cheapest_city_sql = f"""
        SELECT city, round(sum(avg_unit_price * cnt) / sum(cnt)::numeric, 1) as avg_unit_price
        FROM mv_yearly_stats WHERE year = {year}
        GROUP BY city
        ORDER BY avg_unit_price ASC
        LIMIT 1
    """
    cheapest_city_row = db.execute(text(cheapest_city_sql)).fetchone()

    cheapest_dist_sql = f"""
        SELECT district, city, round(sum(avg_unit_price * cnt) / sum(cnt)::numeric, 1) as avg_unit_price
        FROM mv_yearly_stats WHERE year = {year}
        GROUP BY district, city
        HAVING sum(cnt) >= 3
        ORDER BY avg_unit_price ASC
        LIMIT 1
    """
    cheapest_dist_row = db.execute(text(cheapest_dist_sql)).fetchone()

    # Process results
    city_yoy = [{"city": r[0], "avg_unit_price": r[1], "prev_price": r[2], "yoy_pct": r[3]} for r in city_yoy_rows if r[3] is not None]
    dist_yoy = [{
        "district": r[0], "city": r[1], "avg_unit_price": r[2], "prev_price": r[3], "yoy_pct": r[4],
        "cur_cnt": r[5], "prev_cnt": r[6]
    } for r in dist_yoy_rows if r[4] is not None]

    result = {}

    if city_yoy:
        city_yoy.sort(key=lambda x: x["yoy_pct"])
        result["price_up_city"] = city_yoy[-1]   # highest increase
        result["price_down_city"] = city_yoy[0]   # lowest (most negative)

    if dist_yoy:
        dist_yoy.sort(key=lambda x: x["yoy_pct"])
        result["price_up_district"] = dist_yoy[-1]
        result["price_down_district"] = dist_yoy[0]

    if cheapest_city_row:
        result["cheapest_city"] = {"city": cheapest_city_row[0], "avg_unit_price": cheapest_city_row[1]}

    if cheapest_dist_row:
        result["cheapest_district"] = {"district": cheapest_dist_row[0], "city": cheapest_dist_row[1], "avg_unit_price": cheapest_dist_row[2]}

    return {"year": year, "prev_year": prev_year, "data": result}

import psycopg2
conn = psycopg2.connect('postgresql://hermes@localhost:5432/housing_tracker')
cur = conn.cursor()

# Find groups where same lat/lon but DIFFERENT road names (true geocoding failure)
print("=== Districts where ALL trades share ONE coord (likely district-center fallback) ===")
cur.execute("""
    SELECT city, district, COUNT(DISTINCT lat) as unique_lats, COUNT(*) as total
    FROM trades
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    GROUP BY city, district
    HAVING COUNT(DISTINCT lat) <= 3
    ORDER BY total DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]}/{r[1]}: {r[2]} unique lats, {r[3]} total trades")

print("\n=== Sample addresses from single-coord districts ===")
cur.execute("""
    SELECT id, city, district, address, lat, lon
    FROM trades
    WHERE city = '臺中市' AND district = '西屯區'
    LIMIT 5
""")
for r in cur.fetchall():
    print(f"  id={r[0]}, addr={r[3][:60]}, ({r[4]}, {r[5]})")

# Count how many trades have truly bad addresses (missing city prefix etc.)
print("\n=== Address quality check ===")
cur.execute("""
    SELECT 
        CASE 
            WHEN address LIKE '%市%' AND address LIKE '%區%' THEN 'good'
            WHEN address LIKE '%區%' THEN 'missing_city'
            WHEN address LIKE '%市%' THEN 'missing_district'
            ELSE 'minimal'
        END as quality,
        COUNT(*) as cnt
    FROM trades
    GROUP BY quality
    ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

conn.close()

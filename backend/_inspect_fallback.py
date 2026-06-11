import psycopg2
conn = psycopg2.connect('postgresql://hermes@localhost:5432/housing_tracker')
cur = conn.cursor()

print("=== Unique coord pairs per district (top offenders) ===")
cur.execute("""
    SELECT city, district, lat, lon, COUNT(*) as cnt
    FROM trades
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    GROUP BY city, district, lat, lon
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""")
total_fallback = 0
for r in cur.fetchall():
    print(f"  {r[0]}/{r[1]}: ({r[2]}, {r[3]}) x{r[4]}")
    total_fallback += r[4]
print(f"\nTotal trades with duplicate coords: {total_fallback}")

print("\n=== Trades with UNIQUE coords (properly geocoded) ===")
cur.execute("""
    SELECT city, district, COUNT(*) as cnt
    FROM trades
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    GROUP BY city, district, lat, lon
    HAVING COUNT(*) = 1
""")
unique_count = sum(r[2] for r in cur.fetchall())
print(f"Trades with unique coords: {unique_count}")

# Check if any of the "duplicate" groups are actually very close (random offset pattern)
print("\n=== Are duplicate-coord trades really at same spot? ===")
cur.execute("""
    SELECT t.city, t.district, t.address, t.lat, t.lon
    FROM trades t
    JOIN (
        SELECT city, district, lat, lon
        FROM trades
        GROUP BY city, district, lat, lon
        HAVING COUNT(*) > 5
    ) dup ON t.city = dup.city AND t.district = dup.district AND t.lat = dup.lat AND t.lon = dup.lon
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  {r[0]}/{r[1]}: addr={str(r[2])[:55]}, ({r[3]}, {r[4]})")

conn.close()

import psycopg2
conn = psycopg2.connect('postgresql://hermes@localhost:5432/housing_tracker')
cur = conn.cursor()

print("=== Column names ===")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'trades' ORDER BY ordinal_position;")
for r in cur.fetchall(): print(r[0])

print("\n=== Check for geocode-related columns ===")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'trades' 
      AND (column_name LIKE '%geocode%' OR column_name LIKE '%source%' OR column_name LIKE '%fallback%')
""")
rows = cur.fetchall()
if rows:
    for r in rows: print(r)
else:
    print("(none)")

print("\n=== Sample records with lat/lon ===")
cur.execute("""
    SELECT id, city, district, address, lat, lon 
    FROM trades 
    WHERE lat IS NOT NULL AND lon IS NOT NULL 
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"id={r[0]}, {r[1]}/{r[2]}, addr={str(r[3])[:50]}, lat={r[4]}, lon={r[5]}")

print("\n=== Records with NULL lat/lon ===")
cur.execute("SELECT COUNT(*) FROM trades WHERE lat IS NULL OR lon IS NULL;")
print(f"NULL coords: {cur.fetchone()[0]}")

print("\n=== Total records ===")
cur.execute("SELECT COUNT(*) FROM trades;")
print(f"Total: {cur.fetchone()[0]}")

print("\n=== Fallback detection: find trades whose coords match district center pattern ===")
# Look for trades where lat/lon are very close together (random offset from center)
cur.execute("""
    SELECT city, district, lat, lon, COUNT(*) as cnt
    FROM trades
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    GROUP BY city, district, lat, lon
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
    LIMIT 20
""")
for r in cur.fetchall():
    print(f"{r[0]}/{r[1]}: lat={r[2]}, lon={r[3]}, count={r[4]}")

print("\n=== Check for geocode_source or similar field values ===")
cur.execute("""
    SELECT DISTINCT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'trades'
""")
all_cols = [r[0] for r in cur.fetchall()]
print(f"All columns: {all_cols}")

conn.close()

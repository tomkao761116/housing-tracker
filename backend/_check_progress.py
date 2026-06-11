import psycopg2
conn = psycopg2.connect('postgresql://hermes@localhost:5432/housing_tracker')
cur = conn.cursor()

# Check current state: how many still have duplicate coords?
cur.execute("""
    SELECT city, district, lat, lon, COUNT(*) as cnt
    FROM trades
    WHERE lat IS NOT NULL AND lon IS NOT NULL
    GROUP BY city, district, lat, lon
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""")
dup_groups = cur.fetchall()
total_dup = sum(g[4] for g in dup_groups)
print(f"Still have {len(dup_groups)} duplicate-coord groups, {total_dup} total trades")
for g in dup_groups[:15]:
    print(f"  {g[0]}/{g[1]}: ({g[2]}, {g[3]}) x{g[4]}")

# How many unique coords now?
cur.execute("""
    SELECT COUNT(DISTINCT (lat, lon)) as unique_coords, COUNT(*) as total
    FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL
""")
r = cur.fetchone()
print(f"\nUnique coord pairs: {r[0]}, Total trades: {r[1]}")

# Check if scores were cleared (indicates already processed)
cur.execute("SELECT COUNT(*) FROM trades WHERE score_overall IS NULL AND lat IS NOT NULL")
null_scores = cur.fetchone()[0]
print(f"Trades with NULL scores (need re-scoring): {null_scores}")

conn.close()

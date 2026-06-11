import psycopg2
conn = psycopg2.connect('postgresql://hermes@localhost:5432/housing_tracker')
cur = conn.cursor()

# Check columns related to age/build date
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'trades' AND (column_name LIKE '%age%' OR column_name LIKE '%build%' OR column_name LIKE '%year%')
    ORDER BY ordinal_position
""")
print('=== Age/Build related columns ===')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Check build_complete_date stats
cur.execute("SELECT COUNT(*) FROM trades WHERE build_complete_date IS NOT NULL")
has_build_date = cur.fetchone()[0]
cur.execute("SELECT MIN(build_complete_date), MAX(build_complete_date) FROM trades WHERE build_complete_date IS NOT NULL")
date_range = cur.fetchone()
print(f'\nbuild_complete_date:')
print(f'  Has value: {has_build_date}/3486')
print(f'  Range: {date_range[0]} ~ {date_range[1]}')

# Sample values
cur.execute("SELECT DISTINCT build_complete_date FROM trades WHERE build_complete_date IS NOT NULL LIMIT 20")
samples = [r[0] for r in cur.fetchall()]
print(f'  Samples: {samples}')

# Check if there's a computed age field
cur.execute("SELECT COUNT(*) FROM trades WHERE build_complete_date IS NOT NULL")
cnt = cur.fetchone()[0]
if cnt > 0:
    # Compute age from ROC year format (e.g. "110" = 2021)
    cur.execute("""
        SELECT build_complete_date, 
               CASE 
                   WHEN length(build_complete_date) <= 3 THEN 1911 + CAST(build_complete_date AS INT)
                   ELSE CAST(build_complete_date AS INT)
               END as gregorian_year
        FROM trades 
        WHERE build_complete_date IS NOT NULL 
        LIMIT 10
    """)
    print('\n  ROC -> Gregorian conversion samples:')
    for r in cur.fetchall():
        print(f'    {r[0]} -> {r[1]}')

conn.close()

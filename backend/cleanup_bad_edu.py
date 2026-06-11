"""Clean up false positive education POIs from nominatim source"""
import psycopg2

DB_URL = "postgresql://hermes@localhost:5432/housing_tracker"

bad_patterns = [
    '%大樓%', '%會議%', '%國宅%', '%金融%', '%中心%',
    '%飯店%', '%酒店%', '%旅館%', '%餐廳%', '%咖啡%',
    '%商辦%', '%辦公%', '%廣場%', '%影城%', '%戲院%',
    '%健身%', '%美容%', '%髮廊%', '%診所%', '%自助洗衣%',
]

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

total_deleted = 0
for pat in bad_patterns:
    cur.execute("""
        DELETE FROM poi_master 
        WHERE source = 'nominatim' AND category = 'education'
          AND name LIKE %s
    """, (pat,))
    deleted = cur.rowcount
    if deleted > 0:
        print(f'  Deleted {deleted} matching {pat}')
        total_deleted += deleted

conn.commit()
print(f'Total cleaned: {total_deleted}')

# Verify
cur.execute("""
    SELECT COUNT(*) FROM poi_master 
    WHERE category = 'education'
""")
print(f'Remaining edu POIs: {cur.fetchone()[0]}')

cur.close()
conn.close()

import psycopg2
conn = psycopg2.connect('postgresql://hermes:hermes123@localhost:5432/housing_tracker')
cur = conn.cursor()
cur.execute("""
    SELECT pid, now()-query_start AS dur, 
           wait_event_type, wait_event
    FROM pg_stat_activity 
    WHERE pid = 363601
""")
row = cur.fetchone()
print(f'PID {row[0]} | Duration: {row[1]} | Wait: {row[2]}/{row[3]}')

# Check how many batches done (estimate from max id with geom)
cur.execute("""
    SELECT MAX(id) FROM trades 
    WHERE geom IS NOT NULL AND ST_NPoints(geom) > 0
""")
max_geom = cur.fetchone()[0]
print(f'Max ID with geom filled: {max_geom}')
print(f'Progress estimate: {max_geom/4510810*100:.1f}%')
conn.close()

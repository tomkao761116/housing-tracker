import psycopg2
conn = psycopg2.connect('postgresql://hermes@localhost:5432/housing_tracker')
cur = conn.cursor()

# Table columns
cur.execute("""
    SELECT column_name, data_type, is_nullable 
    FROM information_schema.columns 
    WHERE table_name = 'trade_amenities'
    ORDER BY ordinal_position
""")
print('=== trade_amenities columns ===')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} (nullable={row[2]})')

# Stats
cur.execute('SELECT COUNT(DISTINCT trade_id) FROM trade_amenities')
has_poi = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM trades WHERE lat IS NOT NULL AND lon IS NOT NULL')
has_coords = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM trades')
total = cur.fetchone()[0]
needs_poi = has_coords - has_poi

print(f'\n=== Stats ===')
print(f'Total trades: {total}')
print(f'With coords: {has_coords}')
print(f'With POI data: {has_poi}')
print(f'Need POI: {needs_poi}')

conn.close()

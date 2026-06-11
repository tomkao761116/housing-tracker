import psycopg2
conn = psycopg2.connect('postgresql://hermes@localhost:5432/housing_tracker')
conn.autocommit = True
cur = conn.cursor()

# Check if columns already exist
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'trade_amenities' AND column_name IN ('created_at', 'updated_at')
""")
existing = [row[0] for row in cur.fetchall()]
print(f'Existing timestamp columns: {existing}')

if 'created_at' not in existing:
    cur.execute("ALTER TABLE trade_amenities ADD COLUMN created_at TIMESTAMP DEFAULT NOW()")
    print('Added created_at')

if 'updated_at' not in existing:
    cur.execute("ALTER TABLE trade_amenities ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()")
    print('Added updated_at')

# Add trigger to auto-update updated_at
cur.execute("""
    CREATE OR REPLACE FUNCTION update_trade_amenities_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
""")
print('Created trigger function')

cur.execute("""
    DROP TRIGGER IF EXISTS set_trade_amenities_updated_at ON trade_amenities;
    CREATE TRIGGER set_trade_amenities_updated_at
        BEFORE UPDATE ON trade_amenities
        FOR EACH ROW
        EXECUTE FUNCTION update_trade_amenities_updated_at();
""")
print('Created trigger')

# Verify
cur.execute("""
    SELECT column_name, data_type, column_default 
    FROM information_schema.columns 
    WHERE table_name = 'trade_amenities'
    ORDER BY ordinal_position
""")
print('\nFinal columns:')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} (default={row[2]})')

conn.close()

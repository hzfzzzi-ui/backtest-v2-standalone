import os, json, psycopg2
conn = psycopg2.connect(
    host=os.getenv('PGHOST', 'pams-postgres'),
    port=int(os.getenv('PGPORT', '5432')),
    dbname=os.getenv('PGDATABASE', 'pams'),
    user=os.getenv('PGUSER', 'pams'),
    password=os.getenv('PGPASSWORD', ''),
)
cur = conn.cursor()
cur.execute("""
select distinct lower(symbol) as s
from pams_ohlcv_daily
where (
    lower(symbol) like 'sh60____' or
    lower(symbol) like 'sh68____' or
    lower(symbol) like 'sz00____' or
    lower(symbol) like 'sz30____'
)
order by s
""")
raw = [r[0] for r in cur.fetchall()]
conv = []
for s in raw:
    if len(s) == 8 and (s.startswith('sh') or s.startswith('sz')):
        conv.append(f"{s[2:]}.{s[:2].upper()}")
print(json.dumps({'count': len(conv), 'symbols': conv}, ensure_ascii=False))
cur.close(); conn.close()

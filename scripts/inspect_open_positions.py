import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('db/positions.db')
df = pd.read_sql("SELECT * FROM positions WHERE status='OPEN'", conn)
for i, r in df.iterrows():
    print(f"\n--- Position #{r['id']}: {r['symbol']} ---")
    for col in df.columns:
        print(f"  {col}: {r[col]}")
conn.close()

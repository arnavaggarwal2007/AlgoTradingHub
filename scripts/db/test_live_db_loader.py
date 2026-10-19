import sys
sys.path.insert(0, '.')
from rajat_alpha_v67_single import PositionDatabase

db = PositionDatabase('db/positions.db')
open_pos = db.get_open_positions()
print(f"Successfully loaded {len(open_pos)} open positions:")
for p in open_pos:
    days = db.get_days_held(p['id'])
    print(f"  ID {p['id']}: {p['symbol']} | Qty: {p['remaining_qty']} | Buy: ${p['entry_price']} | SL: ${p['stop_loss']} | Stage: {p.get('sl_stage', 0)} | Days Held: {days}d")
db.conn.close()

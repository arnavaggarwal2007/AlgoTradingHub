from alpaca.trading.client import TradingClient
import json

# REPLACE THESE WITH YOUR KEYS
API_KEY = "PKUWEJLYI5NDIIYIXFHMH4SHGT"
SECRET_KEY = "jsbDo612oHJqvvUQBSBJcde2zbfmxLQy9c12oKqqTz9"

# Connect to Paper Trading
try:
    trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
    account = trading_client.get_account()

    print("\n✅ SUCCESS! Connection Established.")
    print(f"Account Status: {account.status}")
    print(f"Cash Available: ${account.cash}")
    print(f"Buying Power:   ${account.buying_power}")

except Exception as e:
    print("\n❌ ERROR: Connection Failed.")
    print(f"Reason: {e}")
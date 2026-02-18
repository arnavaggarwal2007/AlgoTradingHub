from alpaca.trading.client import TradingClient
import json

# REPLACE THESE WITH YOUR KEYS
API_KEY = "PKXP3QE2EM5EHCFSBF7K27VENG"
SECRET_KEY = "NBcjFcXmEks8kpDwm81Srf6mWQSszU4aB3qxgz54UH6"

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
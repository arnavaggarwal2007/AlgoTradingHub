"""
E*TRADE Account Information Utility

Quick script to view account balance, positions, and order history.
Useful for verifying setup and monitoring account status.
"""

import json
from pyetrade import accounts, order

def load_config(config_path='config_etrade_single.json'):
    with open(config_path, 'r') as f:
        return json.load(f)

def display_account_balance(config):
    """Display current account balance and buying power"""
    consumer_key = config['api']['consumer_key']
    consumer_secret = config['api']['consumer_secret']
    access_token = config['api']['access_token']
    access_secret = config['api']['access_secret']
    account_id_key = config['api']['account_id_key']
    is_sandbox = (config['api']['environment'] == 'sandbox')
    
    accounts_client = accounts.ETradeAccounts(
        consumer_key, consumer_secret,
        access_token, access_secret,
        dev=is_sandbox
    )
    
    print("\n" + "=" * 80)
    print("ACCOUNT BALANCE")
    print("=" * 80)
    
    try:
        balance = accounts_client.get_account_balance(
            account_id_key=account_id_key,
            resp_format='json'
        )
        
        computed = balance.get('BalanceResponse', {}).get('Computed', {})
        real_time = computed.get('RealTimeValues', {})
        
        total_value = float(real_time.get('totalAccountValue', 0))
        cash = float(real_time.get('cashBalance', 0))
        buying_power = float(real_time.get('marginBuyingPower', 0))
        unrealized_pl = float(real_time.get('unrealizedTotalGainLoss', 0))
        
        print(f"\nTotal Account Value: ${total_value:,.2f}")
        print(f"Cash Available:      ${cash:,.2f}")
        print(f"Buying Power:        ${buying_power:,.2f}")
        print(f"Unrealized P/L:      ${unrealized_pl:+,.2f}")
        
    except Exception as e:
        print(f"\nERROR: {e}")

def display_positions(config):
    """Display current open positions"""
    consumer_key = config['api']['consumer_key']
    consumer_secret = config['api']['consumer_secret']
    access_token = config['api']['access_token']
    access_secret = config['api']['access_secret']
    account_id_key = config['api']['account_id_key']
    is_sandbox = (config['api']['environment'] == 'sandbox')
    
    accounts_client = accounts.ETradeAccounts(
        consumer_key, consumer_secret,
        access_token, access_secret,
        dev=is_sandbox
    )
    
    print("\n" + "=" * 80)
    print("OPEN POSITIONS")
    print("=" * 80)
    
    try:
        portfolio = accounts_client.get_account_portfolio(
            account_id_key=account_id_key,
            resp_format='json'
        )
        
        positions = portfolio.get('PortfolioResponse', {}).get('AccountPortfolio', [])
        
        if isinstance(positions, dict):
            positions = [positions]
        
        if not positions:
            print("\nNo open positions")
            return
        
        print(f"\nTotal positions: {len(positions)}\n")
        
        for pos in positions:
            position_data = pos.get('Position', {})
            symbol = position_data.get('symbolDescription', 'N/A')
            quantity = position_data.get('quantity', 0)
            price_paid = float(position_data.get('pricePaid', 0))
            current_price = float(position_data.get('Quick', {}).get('lastTrade', 0))
            market_value = float(position_data.get('marketValue', 0))
            
            cost_basis = price_paid * quantity
            unrealized_pl = market_value - cost_basis
            pl_pct = (unrealized_pl / cost_basis * 100) if cost_basis > 0 else 0
            
            print(f"Symbol: {symbol}")
            print(f"  Quantity:      {quantity}")
            print(f"  Entry Price:   ${price_paid:.2f}")
            print(f"  Current Price: ${current_price:.2f}")
            print(f"  Market Value:  ${market_value:,.2f}")
            print(f"  Unrealized P/L: ${unrealized_pl:+,.2f} ({pl_pct:+.2f}%)")
            print()
        
    except Exception as e:
        print(f"\nERROR: {e}")

def display_recent_orders(config):
    """Display recent order history"""
    consumer_key = config['api']['consumer_key']
    consumer_secret = config['api']['consumer_secret']
    access_token = config['api']['access_token']
    access_secret = config['api']['access_secret']
    account_id_key = config['api']['account_id_key']
    is_sandbox = (config['api']['environment'] == 'sandbox')
    
    order_client = order.ETradeOrder(
        consumer_key, consumer_secret,
        access_token, access_secret,
        dev=is_sandbox
    )
    
    print("\n" + "=" * 80)
    print("RECENT ORDERS (Last 25)")
    print("=" * 80)
    
    try:
        orders = order_client.list_orders(
            account_id_key=account_id_key,
            resp_format='json'
        )
        
        order_list = orders.get('OrdersResponse', {}).get('Order', [])
        
        if isinstance(order_list, dict):
            order_list = [order_list]
        
        if not order_list:
            print("\nNo recent orders")
            return
        
        print(f"\nShowing last {min(25, len(order_list))} orders:\n")
        
        for idx, ord_data in enumerate(order_list[:25], 1):
            order_detail = ord_data.get('OrderDetail', [])
            if isinstance(order_detail, dict):
                order_detail = [order_detail]
            
            if not order_detail:
                continue
            
            detail = order_detail[0]
            instrument = detail.get('Instrument', [])
            if isinstance(instrument, dict):
                instrument = [instrument]
            
            if instrument:
                symbol = instrument[0].get('Product', {}).get('symbol', 'N/A')
                action = instrument[0].get('orderAction', 'N/A')
                qty = instrument[0].get('orderedQuantity', 0)
                filled_qty = instrument[0].get('filledQuantity', 0)
            else:
                symbol = 'N/A'
                action = 'N/A'
                qty = 0
                filled_qty = 0
            
            order_status = detail.get('status', 'N/A')
            order_type = detail.get('priceType', 'N/A')
            placed_time = detail.get('placedTime', 'N/A')
            
            print(f"[{idx}] {symbol} - {action} {qty} shares")
            print(f"    Status: {order_status} | Filled: {filled_qty}/{qty}")
            print(f"    Type: {order_type} | Time: {placed_time}")
            print()
        
    except Exception as e:
        print(f"\nERROR: {e}")

def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("E*TRADE ACCOUNT INFORMATION")
    print("=" * 80)
    
    try:
        config = load_config()
    except FileNotFoundError:
        print("\nERROR: config_etrade_single.json not found!")
        return
    
    # Display account info
    display_account_balance(config)
    display_positions(config)
    display_recent_orders(config)
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()

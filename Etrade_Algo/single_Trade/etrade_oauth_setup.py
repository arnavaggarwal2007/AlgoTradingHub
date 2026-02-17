"""
================================================================================
E*TRADE OAUTH SETUP HELPER
================================================================================

This script helps you complete the OAuth 1.0a authorization process for E*TRADE API.

STEPS:
1. Get your Consumer Key and Consumer Secret from E*TRADE Developer portal
2. Run this script
3. Browser will open with E*TRADE authorization page
4. Log in and authorize the application
5. Copy the verification code
6. Paste it back into this script
7. Access tokens will be saved to config_etrade_single.json

REQUIREMENTS:
- pyetrade library installed
- E*TRADE API keys (Consumer Key + Secret)
- Valid E*TRADE account (Sandbox or Production)

================================================================================
"""

import json
import webbrowser
from pyetrade import ETradeOAuth, accounts

def load_config(config_path='config_etrade_single.json'):
    """Load configuration file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Configuration file {config_path} not found!")
        print("Please create config_etrade_single.json with your Consumer Key and Secret")
        return None

def save_config(config, config_path='config_etrade_single.json'):
    """Save updated configuration"""
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    print(f"\n✅ Configuration saved to {config_path}")

def oauth_setup(config):
    """Complete OAuth 1.0a authorization flow"""
    consumer_key = config['api']['consumer_key']
    consumer_secret = config['api']['consumer_secret']
    environment = config['api']['environment']
    
    if not consumer_key or consumer_key == "YOUR_ETRADE_CONSUMER_KEY":
        print("ERROR: Please update config_etrade_single.json with your E*TRADE Consumer Key")
        return False
    
    if not consumer_secret or consumer_secret == "YOUR_ETRADE_CONSUMER_SECRET":
        print("ERROR: Please update config_etrade_single.json with your E*TRADE Consumer Secret")
        return False
    
    print("=" * 80)
    print("E*TRADE OAUTH AUTHORIZATION")
    print("=" * 80)
    print(f"Environment: {environment.upper()}")
    print(f"Consumer Key: {consumer_key[:10]}...")
    print()
    
    # Initialize OAuth
    if environment == 'sandbox':
        oauth = ETradeOAuth(consumer_key, consumer_secret, sandbox=True)
    else:
        oauth = ETradeOAuth(consumer_key, consumer_secret, sandbox=False)
    
    # Step 1: Get request token and authorization URL
    print("Step 1: Getting authorization URL...")
    try:
        auth_url = oauth.get_request_token()
    except Exception as e:
        print(f"ERROR getting request token: {e}")
        return False
    
    print(f"\n✅ Authorization URL generated")
    print()
    print("=" * 80)
    print("IMPORTANT: Opening browser for authorization...")
    print("=" * 80)
    print()
    print("URL:", auth_url)
    print()
    print("ACTION REQUIRED:")
    print("1. Browser will open automatically")
    print("2. Log in to your E*TRADE account")
    print("3. Click 'Accept' to authorize the application")
    print("4. Copy the verification code displayed")
    print("5. Return here and paste it below")
    print()
    
    # Open browser
    try:
        webbrowser.open(auth_url)
    except:
        print("Could not open browser automatically. Please open the URL manually.")
    
    # Step 2: Get verification code from user
    verifier_code = input("Enter verification code: ").strip()
    
    if not verifier_code:
        print("ERROR: No verification code provided")
        return False
    
    # Step 3: Get access token
    print("\nStep 2: Exchanging verification code for access token...")
    try:
        tokens = oauth.get_access_token(verifier_code)
    except Exception as e:
        print(f"ERROR getting access token: {e}")
        print("\nTroubleshooting:")
        print("- Verify the code was copied correctly")
        print("- Make sure you didn't wait too long (codes expire quickly)")
        print("- Try running the script again")
        return False
    
    print("\n✅ Access token obtained successfully!")
    
    # Save tokens to config
    config['api']['access_token'] = tokens['oauth_token']
    config['api']['access_secret'] = tokens['oauth_token_secret']
    
    return True

def list_accounts(config):
    """List all accounts and let user select one"""
    consumer_key = config['api']['consumer_key']
    consumer_secret = config['api']['consumer_secret']
    access_token = config['api']['access_token']
    access_secret = config['api']['access_secret']
    environment = config['api']['environment']
    
    print("\n" + "=" * 80)
    print("LISTING E*TRADE ACCOUNTS")
    print("=" * 80)
    
    # Initialize accounts client
    if environment == 'sandbox':
        oauth = ETradeOAuth(consumer_key, consumer_secret, sandbox=True)
        oauth.access_token = {'oauth_token': access_token, 'oauth_token_secret': access_secret}
        accounts_client = accounts.ETradeAccounts(
            consumer_key,
            consumer_secret,
            access_token,
            access_secret,
            dev=True
        )
    else:
        oauth = ETradeOAuth(consumer_key, consumer_secret, sandbox=False)
        oauth.access_token = {'oauth_token': access_token, 'oauth_token_secret': access_secret}
        accounts_client = accounts.ETradeAccounts(
            consumer_key,
            consumer_secret,
            access_token,
            access_secret,
            dev=False
        )
    
    # Get account list
    try:
        account_list = accounts_client.list_accounts(resp_format='json')
    except Exception as e:
        print(f"ERROR listing accounts: {e}")
        return False
    
    # Display accounts
    accounts_data = account_list.get('AccountListResponse', {}).get('Accounts', {}).get('Account', [])
    
    if not accounts_data:
        print("No accounts found!")
        return False
    
    print(f"\nFound {len(accounts_data)} account(s):\n")
    
    for idx, account in enumerate(accounts_data, 1):
        account_id = account.get('accountId', 'N/A')
        account_id_key = account.get('accountIdKey', 'N/A')
        account_mode = account.get('accountMode', 'N/A')
        account_desc = account.get('accountDesc', 'N/A')
        account_name = account.get('accountName', 'N/A')
        institution_type = account.get('institutionType', 'N/A')
        
        print(f"[{idx}] Account ID: {account_id}")
        print(f"    Account Key: {account_id_key}")
        print(f"    Name: {account_name}")
        print(f"    Description: {account_desc}")
        print(f"    Type: {institution_type}")
        print(f"    Mode: {account_mode}")
        print()
    
    # Let user select account
    while True:
        try:
            selection = input(f"Select account (1-{len(accounts_data)}) or 'q' to quit: ").strip()
            
            if selection.lower() == 'q':
                return False
            
            idx = int(selection) - 1
            if 0 <= idx < len(accounts_data):
                selected_account = accounts_data[idx]
                account_id_key = selected_account.get('accountIdKey')
                
                config['api']['account_id_key'] = account_id_key
                
                print(f"\n✅ Selected account: {selected_account.get('accountName')} ({account_id_key})")
                return True
            else:
                print("Invalid selection. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def main():
    """Main setup workflow"""
    print("\n" + "=" * 80)
    print("E*TRADE API - OAUTH SETUP WIZARD")
    print("=" * 80)
    print()
    print("This wizard will help you:")
    print("1. Complete OAuth 1.0a authorization")
    print("2. Get access tokens")
    print("3. Select trading account")
    print("4. Save configuration for trading bot")
    print()
    
    # Load config
    config = load_config()
    if not config:
        return
    
    # Check if already authorized
    if config['api'].get('access_token') and config['api'].get('access_secret'):
        print("⚠️  Access tokens already exist in configuration")
        print()
        reauth = input("Re-authorize? (y/n): ").strip().lower()
        
        if reauth != 'y':
            print("\nSkipping OAuth authorization...")
        else:
            # Complete OAuth
            if not oauth_setup(config):
                print("\n❌ OAuth setup failed")
                return
    else:
        # Complete OAuth
        if not oauth_setup(config):
            print("\n❌ OAuth setup failed")
            return
    
    # List accounts and select one
    if not list_accounts(config):
        print("\n❌ Account selection failed or cancelled")
        return
    
    # Save updated config
    save_config(config)
    
    print("\n" + "=" * 80)
    print("✅ SETUP COMPLETE!")
    print("=" * 80)
    print()
    print("Your E*TRADE API is now configured and ready to use.")
    print()
    print("Next steps:")
    print("1. Review config_etrade_single.json to verify all settings")
    print("2. Run: python rajat_alpha_v67_etrade.py")
    print("3. Monitor the first few trades carefully")
    print()
    print("IMPORTANT REMINDERS:")
    print("- Start in SANDBOX environment for testing")
    print("- Access tokens expire after ~24 hours")
    print("- Re-run this script when tokens expire")
    print("- Switch to 'production' environment only after thorough testing")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user (Ctrl+C)")
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()

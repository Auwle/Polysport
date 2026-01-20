# Setup Guide - Polysport Trading Bot

Complete step-by-step guide to get your Polymarket trading bot running.

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Ethereum wallet with private key
- USDC on Polygon network

## Step 1: Install Python Dependencies

Open terminal in the project directory and run:

```bash
pip install -r requirements.txt
```

This installs:
- `py-clob-client` - Polymarket CLOB API client
- `web3` - Ethereum blockchain interaction
- `aiohttp` - Async HTTP requests
- `websockets` - Real-time price feeds
- `sqlalchemy` - Database management
- Other utilities

## Step 2: Get Your Private Key

You need the private key of your Ethereum wallet:

### From MetaMask:
1. Open MetaMask
2. Click the three dots menu
3. Select "Account Details"
4. Click "Show Private Key"
5. Enter your password
6. Copy the private key

### Security Warning:
- Use a dedicated trading wallet
- Don't use your main wallet
- Only fund with what you're willing to risk
- Never share your private key

## Step 3: Configure Credentials

1. Open `config/secrets.env`
2. Replace `your_private_key_here` with your actual private key
3. Remove the "0x" prefix if present

```env
# Example (DO NOT use this key!)
PRIVATE_KEY=abc123def456...  # Your actual key here

# Use mainnet for real trading
CHAIN_ID=137

# Or testnet for testing
# CHAIN_ID=80002
```

## Step 4: Get USDC on Polygon

You need USDC on Polygon network for trading:

### Option A: Bridge from Ethereum
1. Go to https://wallet.polygon.technology/
2. Connect your wallet
3. Select "Bridge" → "Polygon PoS"
4. Bridge USDC from Ethereum to Polygon

### Option B: CEX Withdrawal
1. Use exchanges that support Polygon:
   - Coinbase (select Polygon network)
   - Binance (select Polygon network)
   - Kraken (check availability)
2. Withdraw USDC directly to Polygon

### Option C: Buy on Polygon
1. Bridge ETH or MATIC to Polygon
2. Use QuickSwap or Uniswap on Polygon
3. Swap for USDC

**Recommended Starting Amount**: $100-$500 USDC

## Step 5: Test Connection

Run the example script:

```bash
python src/simple_trade_example.py
```

You should see:

```
============================================================
Polymarket CLOB Trading Example
============================================================

[1] Connecting to Polymarket CLOB API...
✓ Connected successfully

[2] Checking USDC balance...
✓ Balance: $100.50 USDC
...
```

If you see errors, check:
- Private key is correct in `secrets.env`
- Wallet has USDC on Polygon
- Internet connection is working

## Step 6: Find a Market to Trade

To place trades, you need a token_id. Here's how to find one:

### Method 1: Browser DevTools
1. Go to https://polymarket.com
2. Find a sports market (NBA, NHL, LOL, DOTA2)
3. Open browser DevTools (F12)
4. Go to "Network" tab
5. Look for API calls to find token IDs   

### Method 2: Use Market Scanner (Coming Soon)
The bot will include automatic market discovery.

### Method 3: Polymarket API
```python
# Example: Query markets via Gamma API
# (To be implemented in next phase)
```

## Step 7: Place Your First Trade

Create a test script `my_first_trade.py`:

```python
from decimal import Decimal
from src.api.polymarket_client import create_client_from_env

# Initialize client
client = create_client_from_env()

# Your token ID (replace with actual)
token_id = "your_token_id_here"

# Check current price
price = client.get_midpoint_price(token_id)
print(f"Current price: ${price}")

# Place a small test order
order = client.place_market_buy(
    token_id=token_id,
    amount_usdc=Decimal("5"),  # Start small!
    slippage=Decimal("0.02")
)

print("Order placed:", order)
```

Run it:
```bash
python my_first_trade.py
```

## Step 8: Verify on Polymarket

1. Go to https://polymarket.com
2. Connect your wallet
3. Check "Portfolio" → "Open Positions"
4. You should see your position
5. You can manually close it from the website

## Step 9: Advanced Configuration

Edit `config/config.yaml` to customize:

```yaml
sports:
  lol:
    enabled: true
    position_sizes: [25, 10]  # Adjust based on your bankroll

  nba:
    enabled: true
    position_sizes: [10, 3]

risk:
  max_entries_per_match: 2
  min_balance_reserve: 50  # Always keep $50 USDC
```

## Testing Checklist

Before running automated trading:

- [ ] Installed all dependencies
- [ ] Added private key to secrets.env
- [ ] Funded wallet with USDC on Polygon
- [ ] Tested connection with example script
- [ ] Placed and verified a manual test trade
- [ ] Can see position on polymarket.com
- [ ] Successfully closed test position
- [ ] Configured strategy parameters
- [ ] Tested on small position sizes first

## Common Issues

### "Module not found"
```bash
pip install -r requirements.txt
```

### "PRIVATE_KEY not found"
- Check `config/secrets.env` exists
- Verify private key is set correctly
- No spaces or quotes around the key

### "Insufficient balance"
- Bridge more USDC to Polygon
- Check you're on the right network (CHAIN_ID=137)

### "Cannot connect to API"
- Check internet connection
- Verify Polymarket API is online
- Try again in a few minutes

### Orders not appearing on Polymarket
- Wait 1-2 minutes for indexing
- Refresh the page
- Check you're connected with the same wallet

## Safety Tips

1. **Start Small**: Test with $5-10 positions first
2. **Use Testnet**: Try CHAIN_ID=80002 for practice
3. **Monitor Manually**: Check polymarket.com regularly
4. **Set Limits**: Configure max position sizes
5. **Keep Reserves**: Don't trade your entire balance
6. **Backup Keys**: Store private key securely offline
7. **Paper Trade**: Run strategy without real money first

## Next Steps

Once you've successfully:
1. Connected to the API
2. Checked your balance
3. Placed a test trade
4. Verified it on Polymarket

You're ready to:
- Build the market scanner
- Add real-time monitoring
- Implement automated trading
- Add the full strategy logic

## Getting Help

If you encounter issues:

1. Check the error messages carefully
2. Review the README.md
3. Check Polymarket documentation: https://docs.polymarket.com/
4. Review py-clob-client docs: https://github.com/Polymarket/py-clob-client

## Environment Check Script

Create `check_setup.py`:

```python
import os
from decimal import Decimal
import sys

def check_setup():
    print("Checking setup...\n")

    # Check Python version
    print(f"Python version: {sys.version}")

    # Check dependencies
    try:
        import py_clob_client
        print("✓ py-clob-client installed")
    except ImportError:
        print("✗ py-clob-client missing")

    # Check config files
    if os.path.exists("config/secrets.env"):
        print("✓ secrets.env exists")
    else:
        print("✗ secrets.env missing")

    if os.path.exists("config/config.yaml"):
        print("✓ config.yaml exists")
    else:
        print("✗ config.yaml missing")

    # Check environment variables
    from dotenv import load_dotenv
    load_dotenv("config/secrets.env")

    if os.getenv("PRIVATE_KEY"):
        print("✓ PRIVATE_KEY is set")
    else:
        print("✗ PRIVATE_KEY not set")

    # Try connection
    try:
        from src.api.polymarket_client import create_client_from_env
        client = create_client_from_env()
        balance = client.get_balance("USDC")
        print(f"✓ Connected! Balance: ${balance}")
    except Exception as e:
        print(f"✗ Connection failed: {e}")

    print("\nSetup check complete!")

if __name__ == "__main__":
    check_setup()
```

Run it:
```bash
python check_setup.py
```

## You're Ready!

If all checks pass, you're ready to start trading on Polymarket through the CLOB API. All your trades will appear on the Polymarket website and count toward your stats and P&L.

Happy trading! 🚀

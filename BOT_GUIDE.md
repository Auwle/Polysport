# LOL Trading Bot - User Guide

Automated trading bot for League of Legends markets on Polymarket.

## Features

✅ **Automatic Market Scanning**
- Scans all LOL markets every 5 minutes
- Filters by volume (>$1000 USD)
- Filters by total price (<110¢)
- Only trades markets with strong team ≥60¢

✅ **Smart Entry Strategy**
- Automatically places 2 limit entries on weak team
- Entry prices based on strong team price (from strategy table)
- Each entry is $5 USD

✅ **Order Monitoring**
- Checks open orders every 5 minutes
- Recreates orders if they disappear (Polymarket bug)
- Especially important before match starts

✅ **Automatic Take Profit**
- Auto-places TP orders when entry fills
- 15% profit target
- Can disable auto-TP for specific markets

## Strategy Table

| Strong Team Price | Entry 1 | Entry 2 |
|-------------------|---------|---------|
| 61-63¢            | 42¢     | 27¢     |
| 64-66¢            | 44¢     | 31¢     |
| 67-69¢            | 45¢     | 33¢     |
| 70-74¢            | 52¢     | 38¢     |
| 75-79¢            | 58¢     | 42¢     |
| 80¢+              | 68¢     | 55¢     |

## Quick Start

### 1. Test the Bot (Single Scan)

```bash
python test_bot.py
```

This will:
- Scan for LOL markets
- Show which markets match criteria
- Show what orders would be placed
- NOT place any real orders (dry run)

### 2. Run the Bot (Continuous)

```bash
python trading_bot.py
```

This will:
- Run continuous scanning every 5 minutes
- Place real orders automatically
- Monitor and manage positions
- Press Ctrl+C to stop

## Configuration

Edit `trading_bot.py` to change settings:

```python
bot = LOLTradingBot(
    check_interval_seconds=300,      # 5 minutes
    entry_size_usd=Decimal("5"),     # $5 per entry
    min_volume_usd=Decimal("1000"),  # Min $1000 volume
    max_total_price=Decimal("110"),  # Max 110¢ total
    min_strong_team_price=Decimal("60")  # Min 60¢ strong team
)
```

## Managing Markets with Manual TP

If you take profit manually on a market, tell the bot to skip auto-TP:

```python
# In trading_bot.py, after creating bot:
bot.add_profitable_market("market-slug-here")
```

Example:
```python
bot = LOLTradingBot(...)

# Skip auto-TP for these markets
bot.add_profitable_market("lol-t1-vs-geng-game-1")
bot.add_profitable_market("lol-blg-vs-fpx-series-winner")

bot.run()
```

## How It Works

### Every 5 Minutes:

1. **Scan Markets**
   - Get all active LOL markets
   - Filter by volume, price constraints
   - Find trading opportunities

2. **Place Entry Orders**
   - Calculate entry prices based on strategy table
   - Place 2 limit buy orders on weak team
   - Track all orders in database

3. **Monitor Orders**
   - Check if orders still exist
   - Recreate orders that disappeared
   - Especially important before match start

4. **Set Take Profits**
   - Detect filled entry orders
   - Calculate TP price (15% profit)
   - Place limit sell order
   - Skip if market already profitable

5. **Cleanup**
   - Remove old completed orders (>7 days)

## Order Tracking

Orders are tracked in: `data/order_tracking.json`

This file stores:
- Order IDs
- Market slugs
- Entry/exit prices
- Order status (active/filled/disappeared)
- Recreation history

## Important Notes

### Order Disappearance Issue
Polymarket has a bug where limit orders placed too early can disappear. The bot:
- Checks orders every 5 minutes
- Recreates disappeared orders automatically
- Extra vigilant within 5 minutes of match start

### Balance Requirements
- Each market requires $10 (2 entries × $5)
- Keep enough USDC.e balance for multiple markets
- Bot will skip markets if insufficient balance

### Manual Trading
If you want to manually manage a position:
1. Take your profit manually
2. Add market to `already_profitable_markets`
3. Bot will skip auto-TP for that market

### Safety
- Bot only trades LOL markets
- Respects your balance limits
- Will not override manual actions
- Logs all activities

## Monitoring the Bot

While running, the bot shows:
- Current balance
- Markets scanned
- Orders placed
- Orders recreated
- TPs set
- Next check time

Example output:
```
======================================================================
SCAN CYCLE - 2026-01-17 15:30:00
======================================================================
Balance: $150.50 USDC.e

[1] Scanning LOL markets...
Found 5 markets matching criteria

[2] Checking for new trading opportunities...
  → Placing orders for: T1 vs GenG - Game 1 Winner
  ✓ Placed T1 Entry 1: $5 at $0.420
  ✓ Placed T1 Entry 2: $5 at $0.270

[3] Monitoring existing orders...
  All orders are active

[4] Checking filled positions...
  ✓ Placed TP for Entry 1: 11.9 shares at $0.483

======================================================================
Cycle complete. Next check in 5 minutes
======================================================================
```

## Troubleshooting

### Bot not finding markets
- Check if LOL markets exist on Polymarket
- Verify markets meet criteria (volume, prices)
- Markets may be closed or low volume

### Orders not being placed
- Check USDC.e balance
- Verify private key in config/secrets.env
- Check for error messages in console

### Orders disappearing
- This is a known Polymarket issue
- Bot will recreate them automatically
- Check `data/order_tracking.json` for history

### TP not being placed
- Check if market in `already_profitable_markets`
- Verify position exists (entry filled)
- Check balance for TP order

## Files Structure

```
Polysport/
├── trading_bot.py              # Main bot (continuous)
├── test_bot.py                 # Test bot (single scan)
├── src/
│   ├── scanner/
│   │   └── market_scanner.py   # Market scanning logic
│   ├── strategy/
│   │   └── entry_strategy.py   # Entry price calculations
│   ├── monitor/
│   │   └── order_monitor.py    # Order tracking
│   ├── execution/
│   │   └── trade_executor.py   # Order placement
│   └── api/
│       └── polymarket_client.py # CLOB API wrapper
├── data/
│   └── order_tracking.json     # Order database
└── config/
    └── secrets.env             # API credentials
```

## Next Steps

1. Test with `python test_bot.py`
2. Verify it finds markets correctly
3. Check entry prices match strategy table
4. Run continuously with `python trading_bot.py`
5. Monitor for first few cycles
6. Let it run and trade automatically

## Support

If you encounter issues:
1. Check console output for errors
2. Verify balance and credentials
3. Check `data/order_tracking.json` for order history
4. Review Polymarket UI for actual positions

# LOL Trading Bot - Polymarket Automation

Automated trading bot for League of Legends matches on Polymarket.

## Quick Start

### Run Bot (Auto-restart on crash)
```bash
run_bot_forever.bat
```

### Run Bot (Manual restart)
```bash
start_bot.bat
```

## Bot Configuration

- **Entry Size:** $3.5 per entry
- **Scan Interval:** Every 5 minutes
- **Min Volume:** $1,000
- **Strong Team Price:** 60¢ - 100¢

## Strategy

### Entry Points (Based on Strong Team Price)
- 61-63¢: Entry1 @ 42¢, Entry2 @ 27¢
- 64-66¢: Entry1 @ 44¢, Entry2 @ 31¢
- 67-69¢: Entry1 @ 45¢, Entry2 @ 33¢
- 70-74¢: Entry1 @ 52¢, Entry2 @ 38¢
- 75-79¢: Entry1 @ 58¢, Entry2 @ 42¢
- 80+¢: Entry1 @ 68¢, Entry2 @ 55¢

### Take Profit (50/50 Split)

**If only Entry 1 filled:**
- TP1: 50% @ strong_start_price
- TP2: 50% @ 96¢

**If both entries filled:**
- TP1: 50% @ entry1_price
- TP2: 50% @ strong_start_price

## What Bot Does

Every 5 minutes:
1. ✅ Scan all LOL markets
2. ✅ Place limit orders for markets matching strategy
3. ✅ Monitor filled positions
4. ✅ Auto-place take profit orders (50/50 split)
5. ✅ Recreate disappeared orders
6. ✅ Clean up old orders

## Files

### Main Bot
- `trading_bot.py` - Main bot logic
- `start_bot.bat` - Simple start script
- `run_bot_forever.bat` - Auto-restart script

### Core Logic
- `src/strategy/entry_strategy.py` - Entry & TP strategy
- `src/execution/trade_executor.py` - Order placement
- `src/scanner/market_scanner.py` - Market scanning
- `src/monitor/order_monitor.py` - Order tracking
- `src/storage/market_queue.py` - Entry timing

### Testing
- `test_tp_logic.py` - Test TP calculations

## Important Notes

⚠️ **No balance checking** - Bot places orders for ALL qualifying markets
⚠️ Polymarket automatically rejects orders when insufficient balance
⚠️ Keep terminal window open for bot to run
⚠️ Check logs regularly to monitor performance

## Setup

See `SETUP_GUIDE.md` for initial setup instructions.
See `BOT_GUIDE.md` for detailed bot operation guide.

"""
LOL Trading Bot - Automated trading bot for League of Legends markets
Scans markets, places entry orders, monitors positions, and manages take profits
"""

import sys
import time
import json
import os
from decimal import Decimal
from datetime import datetime
from typing import Set, Dict

from src.api.polymarket_client import create_client_from_env
from src.scanner.market_scanner import MarketScanner
from src.strategy.entry_strategy import EntryStrategy
from src.monitor.order_monitor import OrderMonitor
from src.storage.market_queue import MarketQueue
from src.execution.trade_executor import TradeExecutor


class LOLTradingBot:
    """
    Automated trading bot for LOL markets on Polymarket.
    """

    def __init__(
        self,
        check_interval_seconds: int = 300,  # 5 minutes
        entry_size_usd: Decimal = Decimal("3.5"),
        min_volume_usd: Decimal = Decimal("1000"),
        max_total_price: Decimal = Decimal("110"),
        min_strong_team_price: Decimal = Decimal("60")
    ):
        """
        Initialize trading bot.

        Args:
            check_interval_seconds: Time between checks (default 300s = 5min)
            entry_size_usd: Size of each entry in USD (default $3.5)
            min_volume_usd: Minimum market volume (default $1000)
            max_total_price: Maximum total price of both teams (default 110¢)
            min_strong_team_price: Minimum strong team price (default 60¢)
        """
        print("="*70)
        print("LOL TRADING BOT - Initializing")
        print("="*70)

        # Initialize components
        self.client = create_client_from_env()
        self.scanner = MarketScanner()
        self.strategy = EntryStrategy(entry_size_usd=entry_size_usd)
        self.order_monitor = OrderMonitor()
        self.market_queue = MarketQueue()
        self.executor = TradeExecutor(self.client, self.order_monitor, self.scanner, self.market_queue)

        # Configuration
        self.check_interval = check_interval_seconds
        self.min_volume_usd = min_volume_usd
        self.max_total_price = max_total_price
        self.min_strong_team_price = min_strong_team_price

        # Track markets where we already took profit manually
        self.already_profitable_markets: Set[str] = set()

        # Track markets we've already placed orders on
        self.markets_with_orders: Set[str] = set()

        # Load price cache
        self.price_cache = self._load_price_cache()

        print(f"\n[OK] Bot initialized successfully")
        print(f"  - Check interval: {check_interval_seconds}s ({check_interval_seconds//60}min)")
        print(f"  - Entry size: ${entry_size_usd}")
        print(f"  - Min volume: ${min_volume_usd}")
        print(f"  - Max total price: {max_total_price}¢")
        print(f"  - Min strong team price: {min_strong_team_price}¢")

    def _load_price_cache(self) -> Dict:
        """Load price cache from file."""
        cache_file = "data/price_cache.json"
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading price cache: {e}")
        return {}

    def add_profitable_market(self, market_slug: str):
        """
        Mark a market as already profitable (manual TP taken).

        Args:
            market_slug: Market identifier
        """
        self.already_profitable_markets.add(market_slug)
        print(f"Added {market_slug} to profitable markets (won't auto-TP)")

    def _parse_market_for_strategy(self, market_data: dict) -> dict:
        """
        Parse market data from get_market_details into scanner format.

        Args:
            market_data: Raw market data from API

        Returns:
            Parsed market in scanner format
        """
        if not market_data or 'tokens' not in market_data:
            return None

        tokens = market_data.get('tokens', [])
        if len(tokens) != 2:
            return None

        # Get prices
        price_a = float(tokens[0].get('price', 0))
        price_b = float(tokens[1].get('price', 0))

        # Determine strong vs weak team
        if price_a > price_b:
            strong_idx = 0
            weak_idx = 1
            strong_price = price_a
            weak_price = price_b
        else:
            strong_idx = 1
            weak_idx = 0
            strong_price = price_b
            weak_price = price_a

        return {
            'question': market_data.get('question', ''),
            'slug': market_data.get('condition_id', ''),
            'volume': float(market_data.get('volume', 0)),
            'strong_team': {
                'name': tokens[strong_idx].get('outcome', ''),
                'token_id': tokens[strong_idx].get('token_id', ''),
                'price': strong_price,
                'price_cents': strong_price * 100
            },
            'weak_team': {
                'name': tokens[weak_idx].get('outcome', ''),
                'token_id': tokens[weak_idx].get('token_id', ''),
                'price': weak_price,
                'price_cents': weak_price * 100
            }
        }

    def scan_and_execute(self):
        """
        Main trading logic: scan markets, add to queue, place time-based orders, monitor positions.
        """
        print(f"\n{'='*70}")
        print(f"SCAN CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")

        # Check balance (for display only)
        balance = self.client.get_balance()
        print(f"Balance: ${balance} USDC.e")

        # Step 1: Scan for new LOL markets
        print("\n[1] Scanning LOL markets...")
        markets = self.scanner.scan_lol_markets(
            min_volume_usd=self.min_volume_usd,
            max_total_price=self.max_total_price,
            min_strong_team_price=self.min_strong_team_price
        )

        # Markets scanned - processing silently

        # Step 2: Add new markets and place orders IMMEDIATELY
        print("\n[2] Placing orders for new markets...")
        new_orders_placed = 0

        # Get open orders once for efficiency
        all_open_orders = self.client.get_open_orders()

        for market in markets:
            slug = market['slug']
            strong_team_token_id = market['strong_team']['token_id']

            # Add to queue if not exists (for tracking)
            if not self.market_queue.has_market(slug):
                self.market_queue.add_pending_market(
                    slug=slug,
                    entry_time=market['entry_time'],
                    match_start_time=market['match_start_time']
                )

            # Check for existing open orders for this token (fast check first)
            has_open_order = any(
                order.get('asset_id') == strong_team_token_id and order.get('side') == 'BUY'
                for order in all_open_orders
            )

            if has_open_order:
                self.market_queue.mark_market_entered(slug)
                continue

            # Check for manual position (slower check, only if no open orders)
            existing_balance = self.client.get_token_balance(strong_team_token_id)

            if existing_balance > Decimal("0.01"):
                self.market_queue.mark_market_entered(slug)
                continue

            # PLACE ORDERS (no position, no open orders)
            print(f"\n  -> {market['question'][:60]}...")

            # Calculate orders
            orders = self.strategy.calculate_orders(market)

            if not orders:
                print(f"    [X] No valid entry strategy")
                self.market_queue.mark_market_entered(slug)
                continue

            # Place orders
            strong_price_cents = market['strong_team']['price_cents']
            order_ids = self.executor.place_entry_orders(
                orders=orders,
                strong_team_price_cents=strong_price_cents
            )

            if order_ids:
                self.markets_with_orders.add(slug)
                self.market_queue.mark_market_entered(slug)
                new_orders_placed += len(order_ids)

        if new_orders_placed > 0:
            print(f"\n  [OK] Placed {new_orders_placed} new entry orders")
        else:
            print("  No new orders placed")

        # Step 3: Check for markets ready for entry (LEGACY - now unused)
        print("\n[3] Checking markets ready for entry...")
        ready_markets = []  # Empty since we place immediately above

        print("  (Legacy step - orders now placed immediately above)")

        # Step 4: Monitor and recreate disappeared orders
        print("\n[4] Monitoring existing orders...")
        recreated = self.executor.check_and_recreate_orders()

        if recreated > 0:
            print(f"  [OK] Recreated {recreated} disappeared orders")
        else:
            print("  All orders active")

        # Step 5: Check filled positions and set take profits
        print("\n[5] Checking filled positions...")
        # Reload price cache in case it was updated
        self.price_cache = self._load_price_cache()
        tp_placed = self.executor.check_filled_positions_and_set_tp(
            strategy=self.strategy,
            already_profitable_markets=self.already_profitable_markets,
            price_cache=self.price_cache
        )

        if tp_placed > 0:
            print(f"  [OK] Placed {tp_placed} TP orders")
        else:
            print("  No new positions for TP")

        # Step 6: Cleanup old orders
        self.order_monitor.cleanup_old_orders(days_old=7)

        print(f"\n{'='*70}")
        print(f"Cycle complete. Next check in {self.check_interval//60} minutes")
        print(f"{'='*70}")

    def run(self):
        """
        Run the bot in continuous loop.
        """
        print("\n" + "="*70)
        print("BOT STARTED - Press Ctrl+C to stop")
        print("="*70)

        try:
            while True:
                try:
                    self.scan_and_execute()
                except Exception as e:
                    print(f"\n⚠ Error in scan cycle: {e}")
                    print("Continuing to next cycle...")

                # Wait for next cycle
                print(f"\nWaiting {self.check_interval}s until next scan...")
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print("BOT STOPPED BY USER")
            print("="*70)

    def run_once(self):
        """
        Run a single scan cycle (useful for testing).
        """
        self.scan_and_execute()


def main():
    """
    Main entry point for the trading bot.
    """
    print("\n" + "="*70)
    print("LOL TRADING BOT v1.0 - Automated Polymarket Trading")
    print("="*70 + "\n")

    # Create and configure bot
    bot = LOLTradingBot(
        check_interval_seconds=60,  # 1 minute
        entry_size_usd=Decimal("3.5"),
        min_volume_usd=Decimal("1000"),
        max_total_price=Decimal("110"),
        min_strong_team_price=Decimal("0")  # Allow balanced matches (≤60¢)
    )

    # Add any markets where you've already taken profit manually
    # Example:
    # bot.add_profitable_market("lol-match-team-a-vs-team-b")

    # Start the bot
    print("\nStarting bot in continuous mode...")
    print("The bot will:")
    print("  1. Scan LOL markets every 5 minutes")
    print("  2. Place entry orders based on strategy table")
    print("  3. Monitor and recreate disappeared orders")
    print("  4. Auto-place take profit orders when entries fill")
    print()

    # Run the bot
    bot.run()


if __name__ == "__main__":
    main()

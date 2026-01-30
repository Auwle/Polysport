"""
Trade Executor - Execute trades based on strategy signals
"""

from typing import Dict, List, Optional
from decimal import Decimal
from src.api.polymarket_client import PolymarketClient
from src.monitor.order_monitor import OrderMonitor


class TradeExecutor:
    """
    Execute trades and manage orders on Polymarket.
    """

    def __init__(self, client: PolymarketClient, order_monitor: OrderMonitor, market_scanner=None, market_queue=None):
        """
        Initialize trade executor.

        Args:
            client: Polymarket client
            order_monitor: Order monitor for tracking
            market_scanner: MarketScanner for checking market status (optional)
            market_queue: MarketQueue for removing ended markets (optional)
        """
        self.client = client
        self.order_monitor = order_monitor
        self.market_scanner = market_scanner
        self.market_queue = market_queue

    def place_entry_orders(self, orders: List[Dict], strong_team_price_cents: float = None) -> List[str]:
        """
        Place entry limit buy orders.

        Args:
            orders: List of order specifications from strategy
            strong_team_price_cents: Strong team price when entry was made (for TP calculation)

        Returns:
            List of order IDs that were successfully placed
        """
        placed_order_ids = []

        for order_spec in orders:
            try:
                # Place limit buy order
                response = self.client.place_limit_buy(
                    token_id=order_spec['token_id'],
                    price=order_spec['price'],
                    amount_usdc=order_spec['amount_usd']
                )

                if response and 'orderID' in response:
                    order_id = response['orderID']
                    placed_order_ids.append(order_id)

                    # Track this order
                    size = order_spec['amount_usd'] / order_spec['price']
                    self.order_monitor.add_order(
                        order_id=order_id,
                        token_id=order_spec['token_id'],
                        market_slug=order_spec['market_slug'],
                        side='BUY',
                        price=order_spec['price'],
                        size=size,
                        entry_number=order_spec.get('entry_number'),
                        strong_team_price_cents=strong_team_price_cents
                    )

                    print(f"      [OK] Entry {order_spec['entry_number']}: ${order_spec['amount_usd']} @ ${order_spec['price']:.3f}")
                else:
                    print(f"      [X] Entry {order_spec['entry_number']} failed")

            except Exception as e:
                print(f"Error placing order: {e}")
                continue

        return placed_order_ids

    def place_take_profit_orders(
        self,
        token_id: str,
        market_slug: str,
        team_name: str,
        tp_price: Decimal,
        position_size: Decimal
    ) -> Optional[str]:
        """
        Place take profit limit sell order.

        Args:
            token_id: Token ID to sell
            market_slug: Market identifier
            team_name: Team name for logging
            tp_price: Take profit price
            position_size: Number of shares to sell

        Returns:
            Order ID if successful, None otherwise
        """
        try:
            response = self.client.place_limit_sell(
                token_id=token_id,
                price=tp_price,
                size=position_size
            )

            if response and 'orderID' in response:
                order_id = response['orderID']

                # Track this order
                self.order_monitor.add_order(
                    order_id=order_id,
                    token_id=token_id,
                    market_slug=market_slug,
                    side='SELL',
                    price=tp_price,
                    size=position_size
                )

                print(f"      [OK] TP: {team_name} - {position_size} shares @ ${tp_price:.3f}")
                return order_id
            else:
                print(f"      [X] TP failed: {team_name}")
                return None

        except Exception as e:
            print(f"Error placing TP order: {e}")
            return None

    def check_and_recreate_orders(self) -> int:
        """
        Check all tracked orders and recreate if disappeared.

        Returns:
            Number of orders recreated
        """
        # Get all open orders from CLOB
        open_orders = self.client.get_open_orders()
        open_order_ids = {order.get('id') for order in open_orders if order.get('id')}

        # Update status for all tracked orders
        for order_id in list(self.order_monitor.tracked_orders.keys()):
            still_exists = order_id in open_order_ids
            self.order_monitor.update_order_status(order_id, still_exists)

        # Get disappeared orders
        disappeared = self.order_monitor.get_disappeared_orders()

        if not disappeared:
            return 0

        print(f"  [!] {len(disappeared)} disappeared orders found - checking...")

        # BATCH CHECK: Pre-check all unique markets to avoid repeated API calls
        ended_markets = set()
        if self.market_scanner:
            unique_markets = {order['market_slug'] for order in disappeared}
            for market_slug in unique_markets:
                if not self.market_scanner.is_market_active(market_slug):
                    ended_markets.add(market_slug)

        recreated_count = 0
        skipped_ended_markets = 0

        for order_data in disappeared:
            try:
                market_slug = order_data['market_slug']

                # CHECK 1: Skip if market has ended
                if market_slug in ended_markets:
                    skipped_ended_markets += 1
                    # Remove from tracking - no need to check again
                    self.order_monitor.remove_order(order_data['order_id'])
                    # Also remove from queue
                    if self.market_queue:
                        self.market_queue.remove_market(market_slug)
                    continue

                # CHECK 2: Check if we already have position (order was filled)
                token_id = order_data['token_id']
                existing_balance = self.client.get_token_balance(token_id)

                if existing_balance > Decimal("0.1"):
                    # Order was filled, not disappeared - don't recreate
                    print(f"    [!] Skipping recreate - position exists ({existing_balance} shares)")
                    self.order_monitor.mark_order_filled(order_data['order_id'])
                    continue

                # Recreate the order
                side = order_data['side']
                price = Decimal(order_data['price'])
                size = Decimal(order_data['size'])

                if side == 'BUY':
                    amount_usd = price * size
                    response = self.client.place_limit_buy(
                        token_id=token_id,
                        price=price,
                        amount_usdc=amount_usd
                    )
                else:  # SELL
                    response = self.client.place_limit_sell(
                        token_id=token_id,
                        price=price,
                        size=size
                    )

                if response and 'orderID' in response:
                    new_order_id = response['orderID']

                    # Track new order
                    self.order_monitor.add_order(
                        order_id=new_order_id,
                        token_id=token_id,
                        market_slug=market_slug,
                        side=side,
                        price=price,
                        size=size,
                        entry_number=order_data.get('entry_number')
                    )

                    # Mark old order as recreated
                    self.order_monitor.mark_order_recreated(
                        order_data['order_id'],
                        new_order_id
                    )

                    recreated_count += 1

            except Exception as e:
                print(f"    [X] Recreate failed: {e}")
                continue

        # Print summary
        if skipped_ended_markets > 0:
            print(f"  [!] Skipped {skipped_ended_markets} orders from ended markets")

        return recreated_count

    def check_filled_positions_and_set_tp(
        self,
        strategy,
        already_profitable_markets: set,
        price_cache: dict = None
    ) -> int:
        """
        Check ALL positions and set take profit orders.

        NEW LOGIC (Simple and Robust):
        1. Get ALL current positions from Polymarket Data API
        2. Get ALL open SELL orders from CLOB API
        3. For each position:
           - Check if there's already a SELL order covering it
           - If not enough SELL orders, get start price from price_cache
           - Apply strategy and place SELL order
        4. Verify all positions have SELL orders

        Args:
            strategy: EntryStrategy instance with calculate_take_profit_orders method
            already_profitable_markets: Set of markets to skip
            price_cache: Dict of cached prices {market_slug:token_id -> price_data}

        Returns:
            Number of TP orders placed
        """
        tp_placed = 0

        if price_cache is None:
            price_cache = {}

        # STEP 1: Get ALL positions from Data API
        print("    [1] Fetching all positions from Data API...")
        all_positions = self.client.get_all_positions()

        if not all_positions:
            print("    No positions found")
            return 0

        print(f"    Found {len(all_positions)} positions")

        # STEP 2: Get ALL open orders from CLOB API
        print("    [2] Fetching all open orders...")
        all_open_orders = self.client.get_open_orders()

        # Build a map of existing SELL orders: token_id -> total sell size
        existing_sell_orders = {}
        for order in all_open_orders:
            if order.get('side') == 'SELL':
                token_id = order.get('asset_id')
                size = Decimal(str(order.get('original_size', 0)))
                if token_id not in existing_sell_orders:
                    existing_sell_orders[token_id] = Decimal("0")
                existing_sell_orders[token_id] += size

        print(f"    Found {len(existing_sell_orders)} tokens with SELL orders")

        # STEP 3: Process each position
        print("    [3] Processing positions...")

        for position in all_positions:
            try:
                # Extract position data
                token_id = position.get('asset')
                position_size = Decimal(str(position.get('size', 0)))
                market_slug = position.get('slug', 'unknown')
                outcome = position.get('outcome', 'unknown')
                avg_price = Decimal(str(position.get('avgPrice', 0)))

                # Skip tiny positions
                if position_size < Decimal("0.1"):
                    continue

                # Skip already profitable markets if specified
                if market_slug in already_profitable_markets:
                    continue

                # Check existing SELL orders for this token
                existing_sell_size = existing_sell_orders.get(token_id, Decimal("0"))

                # Calculate unsold position
                unsold_position = position_size - existing_sell_size

                if unsold_position <= Decimal("0.1"):
                    # Already have enough sell orders
                    continue

                # STEP 4: Get start price from price_cache
                cache_key = f"{market_slug}:{token_id}"
                start_price_data = price_cache.get(cache_key)

                if not start_price_data:
                    # Try to find from order tracking
                    # Look for BUY orders for THIS token_id to get entry price
                    tracked_orders = self.order_monitor.get_active_orders_by_market(market_slug)
                    strong_team_price_cents = None
                    entry_price = None
                    filled_entry_numbers = set()

                    for order_data in tracked_orders:
                        # Record strong_team_price_cents for strategy
                        if order_data.get('strong_team_price_cents'):
                            strong_team_price_cents = order_data.get('strong_team_price_cents')

                        # If this order is for our token, get the entry price and entry number
                        if order_data.get('token_id') == token_id and order_data.get('side') == 'BUY':
                            entry_price = Decimal(str(order_data.get('price', 0)))
                            if order_data.get('entry_number'):
                                filled_entry_numbers.add(order_data.get('entry_number'))

                    if entry_price and strong_team_price_cents:
                        start_price_data = {
                            'price': str(entry_price),
                            'strong_team_price_cents': strong_team_price_cents,
                            'filled_entry_numbers': filled_entry_numbers
                        }

                if not start_price_data:
                    # No cached price - skip this position (let user manage manually)
                    print(f"      [!] No cached price for {outcome} in {market_slug} - skipping (manual management)")
                    continue

                # Get strong team price and entry price for TP calculation
                strong_team_price_cents = start_price_data.get('strong_team_price_cents')
                entry_price = Decimal(str(start_price_data.get('price', 0)))
                entry_price_cents = float(entry_price * 100)

                if not strong_team_price_cents:
                    print(f"      [!] No strong team price for {outcome} in {market_slug} - skipping")
                    continue

                strong_price_cents = float(strong_team_price_cents)

                # Rule: If strong team > 75 cents, no TP (run to resolution)
                if strong_price_cents > 75:
                    print(f"      [!] {outcome}: Strong team @ {strong_price_cents:.1f}c > 75c - no TP, run to resolution")
                    continue

                # STEP 5: Apply TP strategy based on strong team price

                # BALANCED MATCH: Strong ≤ 60¢
                # Each team has only 1 entry, TP immediately when filled
                if strong_price_cents <= 60:
                    # Determine if this is strong or weak team based on entry price
                    # Strong team entry = 25¢, Weak team entry = 22¢
                    if entry_price_cents >= 24:  # Strong team (entry ~25¢)
                        tp_price = Decimal(str(strong_price_cents)) / Decimal("100") - Decimal("0.02")
                        print(f"      [BALANCED] {outcome} is STRONG team, TP = {strong_price_cents:.1f}c - 2c")
                    else:  # Weak team (entry ~22¢)
                        # TP = 102 - strong_price (in cents), then convert to decimal
                        tp_price_cents = 102 - strong_price_cents
                        tp_price = Decimal(str(tp_price_cents)) / Decimal("100")
                        print(f"      [BALANCED] {outcome} is WEAK team, TP = 102 - {strong_price_cents:.1f}c = {tp_price_cents:.1f}c")

                # NON-BALANCED MATCH: Strong 61-75¢
                else:
                    # Rule: Only TP if both entries filled (entry 1 and 2)
                    filled_entries = start_price_data.get('filled_entry_numbers', set())
                    num_entries_filled = len(filled_entries)

                    if num_entries_filled < 2:
                        print(f"      [!] {outcome}: Only {num_entries_filled} entry filled - no TP, run to resolution")
                        continue

                    # Both entries filled: TP at strong team's start price - 2 cents
                    tp_price = Decimal(str(strong_price_cents)) / Decimal("100") - Decimal("0.02")

                print(f"\n      Position: {outcome} ({market_slug})")
                print(f"        Size: {position_size:.2f} | SELL: {existing_sell_size:.2f} | Unsold: {unsold_position:.2f}")
                print(f"        TP Price: ${tp_price:.3f}")

                # Place TP order for unsold position
                tp_order_id = self.place_take_profit_orders(
                    token_id=token_id,
                    market_slug=market_slug,
                    team_name=outcome,
                    tp_price=tp_price,
                    position_size=unsold_position
                )

                if tp_order_id:
                    tp_placed += 1
                    # Update existing_sell_orders to avoid duplicate
                    existing_sell_orders[token_id] = existing_sell_orders.get(token_id, Decimal("0")) + unsold_position

            except Exception as e:
                print(f"      [X] Error processing position: {e}")
                continue

        # STEP 6: Final verification
        print(f"\n    [4] Summary: Placed {tp_placed} TP orders")

        return tp_placed

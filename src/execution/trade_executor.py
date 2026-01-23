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
        already_profitable_markets: set
    ) -> int:
        """
        Check for filled entry orders and set take profit orders.

        NEW Logic:
        1. Get all open orders from API (BUY and SELL side)
        2. For each market, check how many BUY entries are filled
        3. Check current position size
        4. Check how many shares are already in SELL orders
        5. If position > sell orders, place TP for the difference

        Args:
            strategy: EntryStrategy instance with calculate_take_profit_orders method
            already_profitable_markets: Set of markets to skip

        Returns:
            Number of TP orders placed
        """
        tp_placed = 0

        # Get all open orders from CLOB API
        all_open_orders = self.client.get_open_orders()

        # Get markets with tracked orders
        markets = self.order_monitor.get_markets_with_orders()

        for market_slug in markets:
            # Skip if already profitable
            if market_slug in already_profitable_markets:
                continue

            # Get tracked orders for this market
            market_orders = self.order_monitor.get_active_orders_by_market(market_slug)

            # Group by token_id (handle both strong and weak team orders)
            tokens_in_market = {}

            for order_data in market_orders:
                if order_data['side'] != 'BUY':
                    continue

                token_id = order_data['token_id']
                if token_id not in tokens_in_market:
                    tokens_in_market[token_id] = {
                        'buy_orders': [],
                        'strong_team_price_cents': order_data.get('strong_team_price_cents')
                    }

                tokens_in_market[token_id]['buy_orders'].append(order_data)

            # Check each token (team) in this market
            for token_id, token_data in tokens_in_market.items():
                buy_orders = token_data['buy_orders']
                strong_team_price_cents = token_data['strong_team_price_cents']

                # Count how many BUY orders still open (not filled)
                open_buy_count = sum(
                    1 for order in all_open_orders
                    if order.get('asset_id') == token_id and order.get('side') == 'BUY'
                )

                # Count filled entries = total entries - open entries
                total_entries = len(buy_orders)
                filled_entries_count = total_entries - open_buy_count

                # Get current position size
                position_size = self.client.get_token_balance(token_id)

                if position_size <= 0:
                    continue  # No position, skip

                # Check existing SELL orders for this token
                existing_sell_size = sum(
                    Decimal(str(order.get('original_size', 0)))
                    for order in all_open_orders
                    if order.get('asset_id') == token_id and order.get('side') == 'SELL'
                )

                # Calculate how much we need to sell
                unsold_position = position_size - existing_sell_size

                if unsold_position <= Decimal("0.01"):
                    continue  # Already have enough sell orders

                # Build filled_entries list for strategy
                filled_entries = []
                for i, order_data in enumerate(buy_orders[:filled_entries_count]):
                    filled_entries.append({
                        'entry_number': order_data.get('entry_number', i + 1),
                        'price': order_data['price']
                    })

                # Mark filled orders
                for order_data in buy_orders[:filled_entries_count]:
                    self.order_monitor.mark_order_filled(order_data['order_id'])

                # Calculate TP orders
                if strong_team_price_cents:
                    tp_specs = strategy.calculate_take_profit_orders(
                        filled_entries=filled_entries,
                        strong_team_start_price_cents=strong_team_price_cents,
                        total_position_size=unsold_position  # Only sell what's not already in orders
                    )

                    # Place TP orders
                    for tp_spec in tp_specs:
                        tp_order_id = self.place_take_profit_orders(
                            token_id=token_id,
                            market_slug=market_slug,
                            team_name=tp_spec['label'],
                            tp_price=tp_spec['price'],
                            position_size=tp_spec['size']
                        )

                        if tp_order_id:
                            tp_placed += 1

        return tp_placed

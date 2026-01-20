"""
Entry Strategy - Determine entry points based on strong team price
Implements the strategy table with limit entry prices
"""

from decimal import Decimal
from typing import Dict, List, Optional


class EntryStrategy:
    """
    Entry strategy based on strong team price ranges.

    Strategy table (from image):
    - Price 61-63: Entry 1 at 42¢, Entry 2 at 27¢
    - Price 64-66: Entry 1 at 44¢, Entry 2 at 31¢
    - Price 67-69: Entry 1 at 45¢, Entry 2 at 33¢
    - Price 70-74: Entry 1 at 52¢, Entry 2 at 38¢
    - Price 75-79: Entry 1 at 58¢, Entry 2 at 42¢
    - Price 80+:   Entry 1 at 68¢, Entry 2 at 55¢
    """

    # Strategy table: (min_price, max_price) -> (entry1, entry2)
    # Ranges are inclusive on both ends and cover decimals (e.g., 79.5 matches 75-80 range)
    STRATEGY_TABLE = {
        (61, 63.99): (42, 27),
        (64, 66.99): (44, 31),
        (67, 69.99): (45, 33),
        (70, 74.99): (52, 38),
        (75, 79.99): (58, 42),
        (80, 100): (68, 55),  # 80+ means up to 100
    }

    def __init__(self, entry_size_usd: Decimal = Decimal("5")):
        """
        Initialize entry strategy.

        Args:
            entry_size_usd: Size of each entry in USD (default $5)
        """
        self.entry_size_usd = entry_size_usd

    def get_entry_prices(self, strong_team_price_cents: float) -> Optional[Dict]:
        """
        Get entry prices for weak team based on strong team price.

        Args:
            strong_team_price_cents: Strong team price in cents (e.g., 65.5)

        Returns:
            Dict with entry1 and entry2 prices in cents, or None if no strategy
        """
        # Find matching price range
        for (min_price, max_price), (entry1, entry2) in self.STRATEGY_TABLE.items():
            if min_price <= strong_team_price_cents <= max_price:
                return {
                    'entry1_cents': entry1,
                    'entry1_price': Decimal(str(entry1)) / Decimal("100"),
                    'entry2_cents': entry2,
                    'entry2_price': Decimal(str(entry2)) / Decimal("100"),
                    'entry_size_usd': self.entry_size_usd
                }

        # No strategy for this price range
        return None

    def calculate_orders(self, market: Dict) -> Optional[List[Dict]]:
        """
        Calculate limit orders for a market.

        Args:
            market: Market data from scanner

        Returns:
            List of order specifications, or None if no strategy applicable
        """
        strong_price_cents = market['strong_team']['price_cents']

        # Get entry prices
        entry_config = self.get_entry_prices(strong_price_cents)

        if not entry_config:
            return None

        # Create two limit buy orders for STRONG team (the favorite)
        strong_team_token_id = market['strong_team']['token_id']

        orders = [
            {
                'order_type': 'limit_buy',
                'token_id': strong_team_token_id,
                'team_name': market['strong_team']['name'],
                'price': entry_config['entry1_price'],
                'price_cents': entry_config['entry1_cents'],
                'amount_usd': self.entry_size_usd,
                'entry_number': 1,
                'market_question': market['question'],
                'market_slug': market['slug']
            },
            {
                'order_type': 'limit_buy',
                'token_id': strong_team_token_id,
                'team_name': market['strong_team']['name'],
                'price': entry_config['entry2_price'],
                'price_cents': entry_config['entry2_cents'],
                'amount_usd': self.entry_size_usd,
                'entry_number': 2,
                'market_question': market['question'],
                'market_slug': market['slug']
            }
        ]

        return orders

    def calculate_take_profit_orders(
        self,
        filled_entries: List[Dict],
        strong_team_start_price_cents: float,
        total_position_size: Decimal
    ) -> List[Dict]:
        """
        Calculate take profit orders based on which entries were filled.

        Strategy:
        - If only Entry 1 filled: 50% at strong_start_price, 50% at 0.96
        - If both entries filled: 50% at entry1_price, 50% at strong_start_price

        Args:
            filled_entries: List of filled entry orders with entry_number and price
            strong_team_start_price_cents: Strong team price when we entered (in cents)
            total_position_size: Total shares we own

        Returns:
            List of TP order specs with price and size
        """
        tp_orders = []

        # Determine which entries were filled
        entry_numbers = {e['entry_number'] for e in filled_entries}

        # Get entry prices from filled orders
        entry1_price = None
        entry2_price = None

        for entry in filled_entries:
            if entry['entry_number'] == 1:
                entry1_price = Decimal(str(entry['price']))
            elif entry['entry_number'] == 2:
                entry2_price = Decimal(str(entry['price']))

        # Strong team start price in decimal
        strong_start_decimal = Decimal(str(strong_team_start_price_cents)) / Decimal("100")

        # Split position 50/50
        half_position = total_position_size / Decimal("2")

        if 1 in entry_numbers and 2 not in entry_numbers:
            # Case 1: Only Entry 1 filled
            # TP1: 50% at strong_start_price
            # TP2: 50% at 0.96
            tp_orders.append({
                'price': strong_start_decimal,
                'size': half_position,
                'label': 'TP1 (50% at start price)'
            })
            tp_orders.append({
                'price': Decimal("0.96"),
                'size': half_position,
                'label': 'TP2 (50% at 0.96)'
            })

        elif 1 in entry_numbers and 2 in entry_numbers:
            # Case 2: Both entries filled
            # TP1: 50% at entry1_price
            # TP2: 50% at strong_start_price
            tp_orders.append({
                'price': entry1_price,
                'size': half_position,
                'label': 'TP1 (50% at Entry1 price)'
            })
            tp_orders.append({
                'price': strong_start_decimal,
                'size': half_position,
                'label': 'TP2 (50% at start price)'
            })

        elif 2 in entry_numbers and 1 not in entry_numbers:
            # Edge case: Only Entry 2 filled (Entry 1 skipped)
            # Use same logic as Entry 1 only
            tp_orders.append({
                'price': strong_start_decimal,
                'size': half_position,
                'label': 'TP1 (50% at start price)'
            })
            tp_orders.append({
                'price': Decimal("0.96"),
                'size': half_position,
                'label': 'TP2 (50% at 0.96)'
            })

        return tp_orders

    def get_take_profit_price(
        self,
        entry_price: Decimal,
        target_profit_pct: Decimal = Decimal("0.15")
    ) -> Decimal:
        """
        Calculate take profit price based on entry price.
        DEPRECATED: Use calculate_take_profit_orders instead for new 50/50 strategy.

        Args:
            entry_price: Entry price (0.0 to 1.0)
            target_profit_pct: Target profit percentage (default 15%)

        Returns:
            Take profit price (capped at 0.99)
        """
        tp_price = entry_price * (Decimal("1") + target_profit_pct)

        # Cap at 0.99 (maximum tradable price)
        if tp_price > Decimal("0.99"):
            tp_price = Decimal("0.99")

        return tp_price

    def should_skip_market(self, market_slug: str, already_profitable_markets: set) -> bool:
        """
        Check if market should be skipped (already taken profit manually).

        Args:
            market_slug: Market slug identifier
            already_profitable_markets: Set of market slugs already profitable

        Returns:
            True if should skip, False otherwise
        """
        return market_slug in already_profitable_markets

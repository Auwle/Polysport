"""
Order Monitor - Monitor open orders and recreate if disappeared
Polymarket has an issue where limit orders can disappear before match starts
"""

from typing import Dict, List, Set, Optional
from decimal import Decimal
from datetime import datetime, timedelta
import json
import os


class OrderMonitor:
    """
    Monitor open orders and track which orders need recreation.
    """

    def __init__(self, storage_file: str = "data/order_tracking.json"):
        """
        Initialize order monitor.

        Args:
            storage_file: Path to JSON file for tracking orders
        """
        self.storage_file = storage_file
        self.tracked_orders = self._load_tracked_orders()

    def _load_tracked_orders(self) -> Dict:
        """Load tracked orders from storage file."""
        if not os.path.exists(self.storage_file):
            return {}

        try:
            with open(self.storage_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading tracked orders: {e}")
            return {}

    def _save_tracked_orders(self):
        """Save tracked orders to storage file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)

            with open(self.storage_file, 'w') as f:
                json.dump(self.tracked_orders, f, indent=2)
        except Exception as e:
            print(f"Error saving tracked orders: {e}")

    def add_order(
        self,
        order_id: str,
        token_id: str,
        market_slug: str,
        side: str,
        price: Decimal,
        size: Decimal,
        entry_number: Optional[int] = None,
        strong_team_price_cents: Optional[float] = None
    ):
        """
        Add an order to tracking.

        Args:
            order_id: Order ID from CLOB
            token_id: Token ID
            market_slug: Market identifier
            side: BUY or SELL
            price: Order price
            size: Order size
            entry_number: Entry number (1 or 2) for buy orders
            strong_team_price_cents: Strong team price when entry was placed (for TP calculation)
        """
        order_data = {
            'order_id': order_id,
            'token_id': token_id,
            'market_slug': market_slug,
            'side': side,
            'price': str(price),
            'size': str(size),
            'entry_number': entry_number,
            'strong_team_price_cents': strong_team_price_cents,
            'created_at': datetime.now().isoformat(),
            'last_seen': datetime.now().isoformat(),
            'disappeared_count': 0,
            'status': 'active'
        }

        self.tracked_orders[order_id] = order_data
        self._save_tracked_orders()

    def update_order_status(
        self,
        order_id: str,
        still_exists: bool,
        current_status: Optional[str] = None
    ):
        """
        Update order status based on whether it still exists.

        Args:
            order_id: Order ID
            still_exists: Whether order still exists in open orders
            current_status: Current order status if available
        """
        if order_id not in self.tracked_orders:
            return

        order = self.tracked_orders[order_id]

        if still_exists:
            # Order still exists
            order['last_seen'] = datetime.now().isoformat()
            order['disappeared_count'] = 0
            if current_status:
                order['status'] = current_status
        else:
            # Order disappeared
            order['disappeared_count'] += 1

            # Mark as disappeared if not seen
            if order['disappeared_count'] >= 1:
                order['status'] = 'disappeared'

        self._save_tracked_orders()

    def get_disappeared_orders(self) -> List[Dict]:
        """
        Get list of orders that have disappeared.

        Returns:
            List of disappeared order data
        """
        disappeared = []

        for order_id, order_data in self.tracked_orders.items():
            if order_data['status'] == 'disappeared':
                disappeared.append(order_data)

        return disappeared

    def mark_order_filled(self, order_id: str):
        """Mark order as filled/completed."""
        if order_id in self.tracked_orders:
            self.tracked_orders[order_id]['status'] = 'filled'
            self._save_tracked_orders()

    def mark_order_recreated(self, old_order_id: str, new_order_id: str):
        """
        Mark old order as recreated with new order ID.

        Args:
            old_order_id: Original order ID that disappeared
            new_order_id: New order ID after recreation
        """
        if old_order_id in self.tracked_orders:
            old_order = self.tracked_orders[old_order_id]
            old_order['status'] = 'recreated'
            old_order['recreated_as'] = new_order_id
            self._save_tracked_orders()

    def remove_order(self, order_id: str):
        """
        Remove order from tracking completely.
        Use this for orders from ended/invalid markets.

        Args:
            order_id: Order ID to remove
        """
        if order_id in self.tracked_orders:
            del self.tracked_orders[order_id]
            self._save_tracked_orders()

    def get_active_orders_by_market(self, market_slug: str) -> List[Dict]:
        """
        Get all active orders for a specific market.

        Args:
            market_slug: Market identifier

        Returns:
            List of active orders for this market
        """
        active_orders = []

        for order_id, order_data in self.tracked_orders.items():
            if (order_data['market_slug'] == market_slug and
                order_data['status'] in ['active', 'disappeared']):
                active_orders.append(order_data)

        return active_orders

    def should_check_before_match(self, match_start_time: datetime) -> bool:
        """
        Check if we should verify orders (within 5 minutes of match start).

        Args:
            match_start_time: Match start time

        Returns:
            True if within 5 minutes before match
        """
        now = datetime.now()
        time_to_match = match_start_time - now

        # Check if within 5 minutes before match
        return timedelta(0) <= time_to_match <= timedelta(minutes=5)

    def get_markets_with_orders(self) -> Set[str]:
        """
        Get set of market slugs that have active orders.

        Returns:
            Set of market slugs
        """
        markets = set()

        for order_data in self.tracked_orders.values():
            if order_data['status'] in ['active', 'disappeared']:
                markets.add(order_data['market_slug'])

        return markets

    def cleanup_old_orders(self, days_old: int = 7):
        """
        Remove tracking for old completed/cancelled orders.

        Args:
            days_old: Remove orders older than this many days
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)
        orders_to_remove = []

        for order_id, order_data in self.tracked_orders.items():
            created_at = datetime.fromisoformat(order_data['created_at'])

            # Remove if old and not active
            if (created_at < cutoff_date and
                order_data['status'] not in ['active', 'disappeared']):
                orders_to_remove.append(order_id)

        for order_id in orders_to_remove:
            del self.tracked_orders[order_id]

        if orders_to_remove:
            print(f"Cleaned up {len(orders_to_remove)} old orders")
            self._save_tracked_orders()

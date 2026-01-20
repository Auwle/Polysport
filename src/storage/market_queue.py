"""
Market Queue - Manages pending markets awaiting entry time
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from pathlib import Path


class MarketQueue:
    """
    Persistent queue for markets pending entry.
    Tracks markets and their entry times for time-based order placement.
    """

    def __init__(self, storage_path: str = "data/market_queue.json", grace_period_minutes: int = 2):
        """
        Initialize market queue with persistent storage.

        Args:
            storage_path: Path to JSON file for persistence
            grace_period_minutes: Allow late entry within this window (default: 2)
        """
        self.storage_path = storage_path
        self.grace_period_minutes = grace_period_minutes
        self.pending_markets: Dict[str, Dict] = {}

        # Ensure data directory exists
        Path(storage_path).parent.mkdir(parents=True, exist_ok=True)

        # Load existing queue
        self._load_queue()

    def _load_queue(self):
        """Load pending markets from JSON file"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pending_markets = data.get('pending_markets', {})
                    print(f"Loaded {len(self.pending_markets)} pending markets from queue")
            except Exception as e:
                print(f"Error loading market queue: {e}")
                self.pending_markets = {}
        else:
            self.pending_markets = {}

    def _save_queue(self):
        """Save pending markets to JSON file"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'pending_markets': self.pending_markets,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving market queue: {e}")

    def add_pending_market(
        self,
        slug: str,
        entry_time: str,
        match_start_time: str
    ):
        """
        Add a market to the pending queue.

        Args:
            slug: Market slug (unique identifier)
            entry_time: ISO format timestamp when to place orders
            match_start_time: ISO format timestamp when match starts
        """
        if slug in self.pending_markets:
            # Already in queue
            return

        self.pending_markets[slug] = {
            'slug': slug,
            'entry_time': entry_time,
            'match_start_time': match_start_time,
            'discovered_at': datetime.now(timezone.utc).isoformat(),
            'status': 'pending'
        }

        self._save_queue()
        # Market added silently

    def has_market(self, slug: str) -> bool:
        """
        Check if market is already in queue.

        Args:
            slug: Market slug

        Returns:
            True if market exists in queue
        """
        return slug in self.pending_markets

    def get_markets_ready_for_entry(self) -> List[str]:
        """
        Get list of market slugs ready for entry.

        Returns markets where:
        - current_time >= entry_time
        - current_time <= entry_time + grace_period
        - current_time < match_start_time
        - status == 'pending'

        Returns:
            List of market slugs ready for order placement
        """
        now = datetime.now(timezone.utc)
        ready_slugs = []

        for slug, market_data in self.pending_markets.items():
            if market_data['status'] != 'pending':
                continue

            try:
                entry_time = datetime.fromisoformat(market_data['entry_time'])
                match_start_time = datetime.fromisoformat(market_data['match_start_time'])

                # Check if we're in the entry window
                grace_end = entry_time + timedelta(minutes=self.grace_period_minutes)

                if now >= entry_time and now <= grace_end and now < match_start_time:
                    # Calculate delay if late
                    if now > entry_time:
                        delay_minutes = (now - entry_time).total_seconds() / 60
                        print(f"[LATE_ENTRY] {slug} | Delay: {delay_minutes:.1f} min | Entering")

                    ready_slugs.append(slug)

            except Exception as e:
                print(f"Error parsing times for {slug}: {e}")
                continue

        return ready_slugs

    def mark_market_entered(self, slug: str):
        """
        Mark market as entered (orders placed).

        Args:
            slug: Market slug
        """
        if slug in self.pending_markets:
            self.pending_markets[slug]['status'] = 'entered'
            self.pending_markets[slug]['entered_at'] = datetime.now(timezone.utc).isoformat()
            self._save_queue()
            print(f"[QUEUE] Marked {slug} as entered")

    def get_match_start_time(self, slug: str) -> Optional[str]:
        """
        Get match start time for a market.

        Args:
            slug: Market slug

        Returns:
            ISO format timestamp or None if market not found
        """
        market_data = self.pending_markets.get(slug)
        if market_data:
            return market_data.get('match_start_time')
        return None

    def remove_market(self, slug: str):
        """
        Remove a specific market from the queue.
        Use this for markets that ended/invalid.

        Args:
            slug: Market slug to remove
        """
        if slug in self.pending_markets:
            del self.pending_markets[slug]
            self._save_queue()

    def cleanup_expired_markets(self):
        """
        Remove markets past match start + 1 hour.
        Keeps queue from growing unbounded.
        """
        now = datetime.now(timezone.utc)
        expired_slugs = []

        for slug, market_data in self.pending_markets.items():
            try:
                match_start_time = datetime.fromisoformat(market_data['match_start_time'])
                expiry_time = match_start_time + timedelta(hours=1)

                if now > expiry_time:
                    expired_slugs.append(slug)

            except Exception as e:
                print(f"Error parsing match time for {slug}: {e}")
                # Remove markets with unparseable times
                expired_slugs.append(slug)

        # Remove expired markets
        for slug in expired_slugs:
            del self.pending_markets[slug]

        if expired_slugs:
            self._save_queue()
            print(f"[QUEUE] Cleaned up {len(expired_slugs)} expired markets")

    def get_queue_status(self) -> Dict:
        """
        Get queue statistics for monitoring.

        Returns:
            Dict with queue stats (pending, entered, total)
        """
        status_counts = {'pending': 0, 'entered': 0, 'total': len(self.pending_markets)}

        for market_data in self.pending_markets.values():
            status = market_data.get('status', 'unknown')
            if status in status_counts:
                status_counts[status] += 1

        return status_counts

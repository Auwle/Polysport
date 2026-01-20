"""
Price Cache - Store initial pre-match prices for markets
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone
from decimal import Decimal


class PriceCache:
    """
    Cache pre-match prices to ensure orders use initial prices,
    not live-updated prices during the match.
    """

    def __init__(self, cache_file: str = "data/price_cache.json"):
        """
        Initialize price cache.

        Args:
            cache_file: Path to JSON file for storing cached prices
        """
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cached_prices: Dict = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cached prices from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading price cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        """Save cached prices to file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cached_prices, f, indent=2)
        except Exception as e:
            print(f"Error saving price cache: {e}")

    def get_cached_price(self, market_slug: str, token_id: str) -> Optional[Decimal]:
        """
        Get cached price for a market/token.

        Args:
            market_slug: Market identifier
            token_id: Token ID

        Returns:
            Cached price as Decimal, or None if not cached
        """
        cache_key = f"{market_slug}:{token_id}"
        if cache_key in self.cached_prices:
            return Decimal(str(self.cached_prices[cache_key]['price']))
        return None

    def cache_price(
        self,
        market_slug: str,
        token_id: str,
        price: Decimal,
        team_name: str
    ):
        """
        Cache a price for a market/token (only if not already cached).

        Args:
            market_slug: Market identifier
            token_id: Token ID
            price: Price to cache
            team_name: Team name for reference
        """
        cache_key = f"{market_slug}:{token_id}"

        # Only cache if not already cached (preserve first price seen)
        if cache_key not in self.cached_prices:
            self.cached_prices[cache_key] = {
                'price': str(price),
                'team_name': team_name,
                'cached_at': datetime.now(timezone.utc).isoformat()
            }
            self._save_cache()

    def has_cached_price(self, market_slug: str) -> bool:
        """
        Check if market has any cached prices.

        Args:
            market_slug: Market identifier

        Returns:
            True if market has cached prices
        """
        return any(key.startswith(f"{market_slug}:") for key in self.cached_prices)

    def clear_market(self, market_slug: str):
        """
        Clear all cached prices for a market.

        Args:
            market_slug: Market identifier
        """
        keys_to_remove = [key for key in self.cached_prices if key.startswith(f"{market_slug}:")]
        for key in keys_to_remove:
            del self.cached_prices[key]

        if keys_to_remove:
            self._save_cache()

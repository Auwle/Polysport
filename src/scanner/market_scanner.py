"""
Market Scanner - Scan and filter LOL markets on Polymarket
"""

import requests
import json
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from src.storage.price_cache import PriceCache


class MarketScanner:
    """Scanner for finding and filtering Polymarket markets"""

    def __init__(self, gamma_api_url: str = "https://gamma-api.polymarket.com"):
        self.gamma_api_url = gamma_api_url
        self.min_event_volume = Decimal("1000")  # Minimum event volume to consider (lowered from 10000)
        self.price_cache = PriceCache()

    def scan_lol_markets(
        self,
        min_volume_usd: Decimal = Decimal("1000"),
        max_total_price: Decimal = Decimal("110"),
        min_strong_team_price: Decimal = Decimal("60"),
        min_event_volume: Decimal = None
    ) -> List[Dict]:
        """
        Scan LOL markets from high-volume events and filter based on criteria.

        Strategy:
        1. Fetch LOL events with volume > min_event_volume
        2. Extract ALL markets from those events (regardless of individual market volume)
        3. Filter markets by price criteria only

        Args:
            min_volume_usd: IGNORED (kept for backward compatibility)
            max_total_price: Maximum sum of both team prices (default 110)
            min_strong_team_price: Minimum price of stronger team (default 60)
            min_event_volume: Minimum event volume (default 10000)

        Returns:
            List of filtered markets with trading opportunities
        """
        if min_event_volume is None:
            min_event_volume = self.min_event_volume

        # Get all active LOL events and filter by event volume
        all_markets = self._fetch_lol_markets_from_events(min_event_volume)

        if not all_markets:
            print("No LOL markets found")
            return []

        # Filter markets by PRICE CRITERIA and other rules
        filtered_markets = []

        print(f"  Filtering {len(all_markets)} markets from high-volume events...")

        for market in all_markets:
            # Parse market data
            try:
                # FILTER 0: Skip markets from events that have already started
                if market.get('_event_started', False):
                    continue

                # FILTER: Only MATCH WINNER markets (ignore game-specific markets)
                question = market.get('question', '')

                # Skip if contains game-specific keywords
                skip_keywords = [
                    'Game 1', 'Game 2', 'Game 3',
                    'Game Handicap', 'Games Total',
                    'O/U', 'Over/Under',
                    'Map ', 'First Blood', 'First Tower'
                ]

                if any(keyword in question for keyword in skip_keywords):
                    continue

                # Must be BO3/BO5 match winner format: "LoL: TeamA vs TeamB (BO3)"
                if not ('(BO3' in question or '(BO5' in question or
                        '(bo3' in question.lower() or '(bo5' in question.lower()):
                    continue

                outcomes = json.loads(market.get('outcomes', '[]'))
                prices = json.loads(market.get('outcomePrices', '[]'))
                clob_token_ids = json.loads(market.get('clobTokenIds', '[]'))

                # Skip if not exactly 2 outcomes (binary market)
                if len(outcomes) != 2 or len(prices) != 2:
                    continue

                # Parse gameStartTime (actual match start) and endDate
                game_start_str = market.get('gameStartTime', None)
                end_date_str = market.get('endDate', None)

                if not game_start_str or not end_date_str:
                    continue

                try:
                    # Parse gameStartTime: "2026-01-22 16:00:00+00"
                    game_start = datetime.fromisoformat(game_start_str)
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)

                    # Time window: [game_start - 24h, game_start + 60min]
                    # Example: Match at 4pm 23/1 → Track from 4pm 22/1 to 5pm 23/1
                    time_until_start = (game_start - now).total_seconds() / 3600  # hours
                    time_since_start = (now - game_start).total_seconds() / 60    # minutes

                    # Skip if match starts more than 24 hours from now
                    if time_until_start > 24:
                        continue

                    # Skip if match started more than 60 minutes ago
                    if time_since_start > 60:
                        continue

                    # Skip if match already ended
                    if end_date < now:
                        continue

                    # Use actual game start time
                    start_date = game_start
                except:
                    continue

                # Get market slug and volume for caching
                market_slug = market.get('slug', '')
                market_volume = Decimal(str(market.get('volume', 0)))
                token_id_a = clob_token_ids[0] if len(clob_token_ids) > 0 else None
                token_id_b = clob_token_ids[1] if len(clob_token_ids) > 1 else None

                # PRICE CACHING STRATEGY:
                # Cache prices in window: [match_start - 180min, match_start]
                # - If already cached → Use cached prices (locked)
                # - If NOT cached AND in cache window → Cache current prices
                # - If NOT cached AND outside cache window → Use current prices without caching

                # Calculate time until match start (in minutes)
                time_until_start_minutes = time_until_start * 60  # Convert hours to minutes

                if token_id_a and self.price_cache.has_cached_price(market_slug):
                    # Already cached → Use cached prices
                    price_a = self.price_cache.get_cached_price(market_slug, token_id_a)
                    price_b = self.price_cache.get_cached_price(market_slug, token_id_b)
                else:
                    # Not cached yet → Use current prices
                    price_a = Decimal(str(prices[0]))
                    price_b = Decimal(str(prices[1]))

                    # Only cache if in the cache window: 180min before match to match start
                    # Example: Match at 4pm → Cache between 1pm and 4pm
                    if token_id_a and token_id_b and 0 <= time_until_start_minutes <= 180:
                        self.price_cache.cache_price(market_slug, token_id_a, price_a, outcomes[0])
                        self.price_cache.cache_price(market_slug, token_id_b, price_b, outcomes[1])

                # Filter 1: Total price of both teams <= max_total_price
                total_price = (price_a * 100) + (price_b * 100)  # Convert to cents
                if total_price > max_total_price:
                    continue

                # Filter 2: At least one team has price >= min_strong_team_price
                max_price = max(price_a, price_b)
                max_price_cents = max_price * 100

                if max_price_cents < min_strong_team_price:
                    continue

                # Filter 3: Skip finished/live markets (price patterns)
                min_price = min(price_a, price_b)

                # Pattern 1: One team at 0-0.1¢, other at 99-100¢ (match decided)
                if (max_price >= Decimal("0.99") and min_price <= Decimal("0.01")):
                    continue

                # Pattern 2: Both teams at extreme prices (0 or 1)
                if (price_a == Decimal("0") or price_a == Decimal("1")) and \
                   (price_b == Decimal("0") or price_b == Decimal("1")):
                    continue

                # Entry time is the match start time (we allow orders from start-60min to start+60min)
                entry_time = start_date

                # Identify strong and weak team
                if price_a > price_b:
                    strong_team_idx = 0
                    weak_team_idx = 1
                    strong_team_price = price_a
                    weak_team_price = price_b
                else:
                    strong_team_idx = 1
                    weak_team_idx = 0
                    strong_team_price = price_b
                    weak_team_price = price_a

                # Add to filtered list
                market_volume = market.get('volume', 0)

                filtered_market = {
                    'question': market.get('question', 'N/A'),
                    'slug': market.get('slug', 'N/A'),
                    'volume': float(market_volume) if market_volume else 0.0,
                    'end_date': market.get('endDate', 'N/A'),
                    'entry_time': entry_time.isoformat(),
                    'match_start_time': start_date.isoformat(),
                    'strong_team': {
                        'name': outcomes[strong_team_idx],
                        'price': float(strong_team_price),
                        'price_cents': float(strong_team_price * 100),
                        'token_id': clob_token_ids[strong_team_idx]
                    },
                    'weak_team': {
                        'name': outcomes[weak_team_idx],
                        'price': float(weak_team_price),
                        'price_cents': float(weak_team_price * 100),
                        'token_id': clob_token_ids[weak_team_idx]
                    },
                    'total_price_cents': float(total_price),
                    'market_id': market.get('id', 'N/A')
                }

                filtered_markets.append(filtered_market)

            except Exception as e:
                print(f"Error parsing market: {e}")
                continue

        # Display filtered markets (max 20)
        print(f"\n  Found {len(filtered_markets)} valid markets:")
        for market in filtered_markets[:10]:
            strong = market['strong_team']
            weak = market['weak_team']
            print(f"     • {market['question'][:70]}")
            print(f"       {strong['name']:25s} {strong['price_cents']:5.1f}¢  vs  {weak['name']:25s} {weak['price_cents']:5.1f}¢")

        if len(filtered_markets) > 10:
            print(f"     ... and {len(filtered_markets) - 10} more")

        return filtered_markets

    def _fetch_lol_markets_from_events(self, min_event_volume: Decimal) -> List[Dict]:
        """
        Fetch LOL markets from high-volume events.

        Strategy:
        1. Fetch all LOL events (series_id=10311)
        2. Filter events by volume >= min_event_volume
        3. Extract ALL markets from those events
        4. Mark markets from events with ended Game 1/2 as live

        Args:
            min_event_volume: Minimum event volume threshold

        Returns:
            List of market dictionaries from high-volume events
        """
        url = f"{self.gamma_api_url}/events"
        params = {
            "series_id": "10311",  # League of Legends
            "active": "true",
            "closed": "false",
            "limit": 200
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            events = response.json()

            # Removed verbose logging

            # Filter events by volume
            high_volume_events = []
            for event in events:
                event_volume = Decimal(str(event.get('volume', 0)))
                if event_volume >= min_event_volume:
                    high_volume_events.append(event)

            print(f"  Fetching markets from {len(high_volume_events)} high-volume events (>${min_event_volume:,.0f})...")

            # Extract ALL markets from high-volume events
            # Also detect which events have started (by checking Game 1/2 markets)
            all_markets = []
            events_started = set()  # Track event IDs that have started

            for event in high_volume_events:
                event_id = event.get('id')
                markets = event.get('markets', [])

                # Check if Game 2 has ended (indicates match is in game 3 or finished)
                # ONLY skip if Game 2 is decided - we still want to catch Game 1 or pre-match
                game2_ended = False
                for market in markets:
                    question = market.get('question', '')

                    # ONLY check Game 2 - if Game 2 ended, we're too late
                    if 'Game 2' in question:
                        try:
                            prices_str = market.get('outcomePrices', '[]')
                            prices = json.loads(prices_str)

                            if len(prices) == 2:
                                price_a = Decimal(str(prices[0]))
                                price_b = Decimal(str(prices[1]))
                                max_price = max(price_a, price_b)
                                min_price = min(price_a, price_b)

                                # Game 2 decided: One team at 99%+, other at 1%-
                                if max_price >= Decimal("0.99") and min_price <= Decimal("0.01"):
                                    # Game 2 ended → Too late to enter
                                    game2_ended = True
                                    break
                        except:
                            pass

                if game2_ended:
                    events_started.add(event_id)

                # Add event_started flag to each market
                for market in markets:
                    market['_event_started'] = (event_id in events_started)

                all_markets.extend(markets)

            return all_markets

        except Exception as e:
            print(f"Error fetching LOL markets: {e}")
            return []

    def get_market_details(self, slug: str) -> Optional[Dict]:
        """
        Get detailed information for a specific market.

        Args:
            slug: Market slug

        Returns:
            Market details or None
        """
        url = f"{self.gamma_api_url}/markets/{slug}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching market {slug}: {e}")
            return None

    def is_market_active(self, slug: str) -> bool:
        """
        Check if a market is still active (not ended).

        Args:
            slug: Market slug or condition_id

        Returns:
            True if market is active, False if ended or error
        """
        try:
            market_data = self.get_market_details(slug)
            if not market_data:
                return False

            # Check endDate
            end_date_str = market_data.get('endDate', None)
            if not end_date_str:
                return True  # No endDate means active

            # Parse and check if ended
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            return end_date > datetime.now(timezone.utc)

        except Exception as e:
            print(f"Error checking market status for {slug}: {e}")
            return False  # Assume inactive on error to be safe

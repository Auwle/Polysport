"""
Debug script to check market parsing for G2 vs GIANTX
"""
import json
import requests

# Fetch G2 vs GIANTX market directly from Gamma API
url = "https://gamma-api.polymarket.com/events"
params = {
    'tag': 'lol',
    'limit': 100,
    'closed': False,
    'active': True
}

response = requests.get(url, params=params)
markets_data = response.json()

# Find G2 vs GIANTX
for event in markets_data:
    for market in event.get('markets', []):
        question = market.get('question', '')
        if 'G2' in question and 'GIANTX' in question:
            print(f"Question: {question}")
            print(f"Slug: {market.get('slug')}")

            outcomes = json.loads(market.get('outcomes', '[]'))
            prices = json.loads(market.get('outcomePrices', '[]'))
            token_ids = json.loads(market.get('clobTokenIds', '[]'))

            print(f"\nOutcome 0: {outcomes[0]}")
            print(f"  Price: {float(prices[0]) * 100:.1f}¢")
            print(f"  Token ID: {token_ids[0]}")

            print(f"\nOutcome 1: {outcomes[1]}")
            print(f"  Price: {float(prices[1]) * 100:.1f}¢")
            print(f"  Token ID: {token_ids[1]}")

            # Determine which is strong
            if float(prices[0]) > float(prices[1]):
                print(f"\nStrong team (higher price): {outcomes[0]} @ {float(prices[0]) * 100:.1f}¢")
                print(f"Weak team (lower price): {outcomes[1]} @ {float(prices[1]) * 100:.1f}¢")
            else:
                print(f"\nStrong team (higher price): {outcomes[1]} @ {float(prices[1]) * 100:.1f}¢")
                print(f"Weak team (lower price): {outcomes[0]} @ {float(prices[0]) * 100:.1f}¢")

            break

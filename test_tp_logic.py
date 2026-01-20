"""
Test script to verify the new 50/50 Take Profit logic
"""

from decimal import Decimal
from src.strategy.entry_strategy import EntryStrategy


def test_tp_logic():
    """Test the TP calculation logic with various scenarios"""

    strategy = EntryStrategy(entry_size_usd=Decimal("3.5"))

    print("="*70)
    print("TESTING TAKE PROFIT LOGIC")
    print("="*70)

    # Test Case 1: Only Entry 1 filled (strong team started at 61¢)
    print("\n[TEST 1] Only Entry 1 filled")
    print("-" * 70)
    print("Strong team start price: 61¢")
    print("Entry 1 filled at: 0.42")
    print("Total position: 8.33 shares ($3.5 / $0.42)")

    filled_entries_case1 = [
        {'entry_number': 1, 'price': '0.42'}
    ]

    tp_orders_case1 = strategy.calculate_take_profit_orders(
        filled_entries=filled_entries_case1,
        strong_team_start_price_cents=61.0,
        total_position_size=Decimal("8.33")
    )

    print("\nTP Orders:")
    for i, tp in enumerate(tp_orders_case1, 1):
        print(f"  TP{i}: {tp['label']}")
        print(f"       Price: ${tp['price']:.3f} ({float(tp['price'])*100:.1f}¢)")
        print(f"       Size: {tp['size']:.2f} shares")
        print()

    # Test Case 2: Both entries filled (strong team started at 61¢)
    print("\n[TEST 2] Both entries filled")
    print("-" * 70)
    print("Strong team start price: 61¢")
    print("Entry 1 filled at: 0.42")
    print("Entry 2 filled at: 0.27")
    print("Total position: 21.31 shares ($3.5/$0.42 + $3.5/$0.27)")

    filled_entries_case2 = [
        {'entry_number': 1, 'price': '0.42'},
        {'entry_number': 2, 'price': '0.27'}
    ]

    tp_orders_case2 = strategy.calculate_take_profit_orders(
        filled_entries=filled_entries_case2,
        strong_team_start_price_cents=61.0,
        total_position_size=Decimal("21.31")
    )

    print("\nTP Orders:")
    for i, tp in enumerate(tp_orders_case2, 1):
        print(f"  TP{i}: {tp['label']}")
        print(f"       Price: ${tp['price']:.3f} ({float(tp['price'])*100:.1f}¢)")
        print(f"       Size: {tp['size']:.2f} shares")
        print()

    # Test Case 3: Only Entry 2 filled (edge case)
    print("\n[TEST 3] Only Entry 2 filled (edge case)")
    print("-" * 70)
    print("Strong team start price: 75¢")
    print("Entry 2 filled at: 0.42")
    print("Total position: 8.33 shares")

    filled_entries_case3 = [
        {'entry_number': 2, 'price': '0.42'}
    ]

    tp_orders_case3 = strategy.calculate_take_profit_orders(
        filled_entries=filled_entries_case3,
        strong_team_start_price_cents=75.0,
        total_position_size=Decimal("8.33")
    )

    print("\nTP Orders:")
    for i, tp in enumerate(tp_orders_case3, 1):
        print(f"  TP{i}: {tp['label']}")
        print(f"       Price: ${tp['price']:.3f} ({float(tp['price'])*100:.1f}¢)")
        print(f"       Size: {tp['size']:.2f} shares")
        print()

    # Verify strategy table
    print("\n[STRATEGY TABLE VERIFICATION]")
    print("-" * 70)

    test_prices = [61, 65, 68, 72, 77, 85]

    for price in test_prices:
        entry_config = strategy.get_entry_prices(price)
        if entry_config:
            print(f"Strong team @ {price}¢:")
            print(f"  - Entry 1: {entry_config['entry1_cents']}¢")
            print(f"  - Entry 2: {entry_config['entry2_cents']}¢")
        else:
            print(f"Strong team @ {price}¢: No strategy")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)


if __name__ == "__main__":
    test_tp_logic()

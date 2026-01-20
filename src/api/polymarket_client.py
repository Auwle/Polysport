"""
Polymarket CLOB API client wrapper using py-clob-client.
Handles all trading operations including placing orders, checking balances, and order management.
"""

from typing import Optional, Dict, Any, List
from decimal import Decimal
import os
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, AssetType, BalanceAllowanceParams
from py_clob_client.constants import POLYGON


class PolymarketClient:
    """
    Wrapper for Polymarket CLOB client.
    All orders placed through this client appear on Polymarket frontend.
    """

    def __init__(
        self,
        private_key: str,
        chain_id: int = 137,
        rpc_url: Optional[str] = None,
        proxy_address: Optional[str] = None
    ):
        """
        Initialize Polymarket CLOB client.

        Args:
            private_key: Ethereum private key (without 0x prefix)
            chain_id: 137 for Polygon mainnet, 80002 for Polygon Amoy testnet
            rpc_url: Optional custom RPC endpoint
            proxy_address: Polymarket proxy wallet address (for UI trading with GNOSIS_SAFE)
                          If provided, uses signature_type=2 and this as funder
                          If None, uses signature_type=0 (EOA direct trading)
        """
        self.chain_id = chain_id
        self.proxy_address = proxy_address

        # Initialize CLOB client
        host = "https://clob.polymarket.com"
        key = private_key if not private_key.startswith("0x") else private_key[2:]

        # Determine signature type and funder based on proxy address
        if proxy_address:
            # GNOSIS_SAFE mode - trades appear on Polymarket UI
            print(f"Using GNOSIS_SAFE mode with proxy: {proxy_address[:10]}...")
            self.client = ClobClient(
                host=host,
                key=key,
                chain_id=chain_id,
                signature_type=2,  # GNOSIS_SAFE
                funder=proxy_address  # Proxy wallet
            )
        else:
            # EOA mode - direct on-chain trading
            print("Using EOA mode (direct on-chain trading)")
            self.client = ClobClient(
                host=host,
                key=key,
                chain_id=chain_id,
                signature_type=0  # EOA
            )

        # Get API credentials
        self._setup_api_credentials()

    def _setup_api_credentials(self):
        """Setup API credentials with the CLOB"""
        try:
            # This will create/derive API credentials from your private key
            creds = self.client.create_or_derive_api_creds()

            # Set the credentials on the client
            self.client.set_api_creds(creds)

            # Confirm setup
            if hasattr(creds, 'api_key'):
                print(f"API Credentials setup: {creds.api_key[:10]}...")
            else:
                print("API Credentials created successfully")
        except Exception as e:
            print(f"Note: API credentials setup: {e}")

    def get_balance(self) -> Decimal:
        """
        Get USDC.e (Polygon Bridged USDC) balance for trading.

        Polymarket uses USDC.e on Polygon:
        - Token address: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
        - This is "Polygon Bridged USDC" (USDC.e)
        - Not the native USDC on Polygon

        Returns:
            USDC.e balance as Decimal (in human-readable format)
        """
        try:
            # Use get_balance_allowance with COLLATERAL asset type to get USDC.e balance
            params = BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            result = self.client.get_balance_allowance(params)

            # Result contains 'balance' and 'allowance' fields
            # Balance is returned as an integer with 6 decimals (USDC.e uses 6 decimals)
            balance_raw = result.get('balance', '0')
            balance = Decimal(str(balance_raw)) / Decimal('1000000')  # Convert from 6 decimals
            return balance
        except Exception as e:
            print(f"Error getting USDC.e balance: {e}")
            return Decimal("0")

    def get_token_balance(self, token_id: str) -> Decimal:
        """
        Get balance of a specific outcome token (conditional token).

        Args:
            token_id: The outcome token ID

        Returns:
            Token balance as Decimal (number of shares)
        """
        try:
            # Use CONDITIONAL asset type for outcome tokens
            params = BalanceAllowanceParams(
                asset_type=AssetType.CONDITIONAL,
                token_id=token_id
            )
            result = self.client.get_balance_allowance(params)
            # Outcome tokens also use 6 decimals
            balance_raw = result.get('balance', '0')
            balance = Decimal(str(balance_raw)) / Decimal('1000000')
            return balance
        except Exception as e:
            print(f"Error getting token balance for {token_id}: {e}")
            return Decimal("0")

    def get_midpoint_price(self, token_id: str) -> Optional[Decimal]:
        """
        Get current midpoint price for a token.

        Args:
            token_id: The outcome token ID

        Returns:
            Midpoint price as Decimal, or None if unavailable
        """
        try:
            result = self.client.get_midpoint(token_id=token_id)

            # API returns dict like {'mid': '0.095'} or None
            if result and isinstance(result, dict):
                mid_value = result.get('mid')
                if mid_value:
                    return Decimal(str(mid_value))

            return None
        except Exception as e:
            print(f"Error getting midpoint price for {token_id}: {e}")
            return None

    def get_order_book(self, token_id: str) -> Dict[str, Any]:
        """
        Get order book for a token.

        Args:
            token_id: The outcome token ID

        Returns:
            Order book with bids and asks as dict
        """
        try:
            book = self.client.get_order_book(token_id=token_id)

            # Convert OrderBookSummary object to dict if needed
            if hasattr(book, 'bids') and hasattr(book, 'asks'):
                return {
                    "bids": book.bids if book.bids else [],
                    "asks": book.asks if book.asks else []
                }
            elif isinstance(book, dict):
                return book
            else:
                return {"bids": [], "asks": []}

        except Exception as e:
            print(f"Error getting order book for {token_id}: {e}")
            return {"bids": [], "asks": []}

    def place_market_buy(
        self,
        token_id: str,
        amount_usdc: Decimal,
        slippage: Decimal = Decimal("0.02")
    ) -> Optional[Dict[str, Any]]:
        """
        Place a market buy order (buy YES tokens).

        Args:
            token_id: The outcome token ID to buy
            amount_usdc: Amount in USDC to spend
            slippage: Maximum slippage tolerance (default 2%)

        Returns:
            Order response or None if failed
        """
        try:
            # Get current midpoint price
            mid_price = self.get_midpoint_price(token_id)
            if not mid_price:
                print(f"Cannot get price for {token_id}")
                return None

            # Calculate worst acceptable price with slippage
            worst_price = mid_price * (1 + slippage)
            if worst_price > Decimal("1.0"):
                worst_price = Decimal("1.0")

            # Calculate size (number of shares)
            size = float(amount_usdc / mid_price)

            # Create order
            order_args = OrderArgs(
                token_id=token_id,
                price=float(worst_price),
                size=size,
                side="BUY"
            )

            # Create and post order to CLOB
            response = self.client.create_and_post_order(order_args)

            print(f"Market BUY order placed: {amount_usdc} USDC at ~{mid_price} for {token_id}")
            return response

        except Exception as e:
            print(f"Error placing market buy: {e}")
            return None

    def place_limit_buy(
        self,
        token_id: str,
        price: Decimal,
        amount_usdc: Decimal
    ) -> Optional[Dict[str, Any]]:
        """
        Place a limit buy order at specific price.

        Args:
            token_id: The outcome token ID to buy
            price: Limit price (0.0 to 1.0)
            amount_usdc: Amount in USDC to spend

        Returns:
            Order response or None if failed
        """
        try:
            # Calculate size (number of shares)
            size = float(amount_usdc / price)

            # Create order
            order_args = OrderArgs(
                token_id=token_id,
                price=float(price),
                size=size,
                side="BUY"
            )

            # Create and post order to CLOB
            response = self.client.create_and_post_order(order_args)

            print(f"Limit BUY order placed: {amount_usdc} USDC at {price} for {token_id}")
            return response

        except Exception as e:
            print(f"Error placing limit buy: {e}")
            return None

    def place_limit_sell(
        self,
        token_id: str,
        price: Decimal,
        size: Decimal
    ) -> Optional[Dict[str, Any]]:
        """
        Place a limit sell order to exit position.

        Args:
            token_id: The outcome token ID to sell
            price: Limit price (0.0 to 1.0)
            size: Number of shares to sell

        Returns:
            Order response or None if failed
        """
        try:
            # Create order
            order_args = OrderArgs(
                token_id=token_id,
                price=float(price),
                size=float(size),
                side="SELL"
            )

            # Create and post order to CLOB
            response = self.client.create_and_post_order(order_args)

            print(f"Limit SELL order placed: {size} shares at {price} for {token_id}")
            return response

        except Exception as e:
            print(f"Error placing limit sell: {e}")
            return None

    def place_market_sell(
        self,
        token_id: str,
        size: Decimal,
        slippage: Decimal = Decimal("0.02")
    ) -> Optional[Dict[str, Any]]:
        """
        Place a market sell order to exit position quickly.

        Args:
            token_id: The outcome token ID to sell
            size: Number of shares to sell
            slippage: Maximum slippage tolerance (default 2%)

        Returns:
            Order response or None if failed
        """
        try:
            # Get current midpoint price
            mid_price = self.get_midpoint_price(token_id)
            if not mid_price:
                print(f"Cannot get price for {token_id}")
                return None

            # Calculate worst acceptable price with slippage
            worst_price = mid_price * (1 - slippage)
            if worst_price < Decimal("0.01"):
                worst_price = Decimal("0.01")

            # Create order
            order_args = OrderArgs(
                token_id=token_id,
                price=float(worst_price),
                size=float(size),
                side="SELL"
            )

            # Create and post order to CLOB
            response = self.client.create_and_post_order(order_args)

            print(f"Market SELL order placed: {size} shares at ~{mid_price} for {token_id}")
            return response

        except Exception as e:
            print(f"Error placing market sell: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order.

        Args:
            order_id: The order ID to cancel

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.cancel(order_id=order_id)
            print(f"Order {order_id} cancelled")
            return True
        except Exception as e:
            print(f"Error cancelling order {order_id}: {e}")
            return False

    def get_open_orders(self, token_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all open orders, optionally filtered by token.

        Args:
            token_id: Optional token ID to filter by

        Returns:
            List of open orders
        """
        try:
            orders = self.client.get_orders()

            if token_id:
                orders = [o for o in orders if o.get("asset_id") == token_id]

            return orders
        except Exception as e:
            print(f"Error getting open orders: {e}")
            return []

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific order.

        Args:
            order_id: The order ID

        Returns:
            Order details or None if not found
        """
        try:
            order = self.client.get_order(order_id=order_id)
            return order
        except Exception as e:
            print(f"Error getting order status for {order_id}: {e}")
            return None


def create_client_from_env() -> PolymarketClient:
    """
    Create Polymarket client from environment variables.

    Environment variables required:
        PRIVATE_KEY: Ethereum private key
        CHAIN_ID: Chain ID (default: 137)
        RPC_URL: Optional custom RPC endpoint
        PROXY_WALLET_ADDRESS: Polymarket proxy wallet (for UI trading)
                             If set, uses GNOSIS_SAFE mode (signature_type=2)
                             If empty, uses EOA mode (signature_type=0)

    Returns:
        Initialized PolymarketClient
    """
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv("config/secrets.env")

    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        raise ValueError("PRIVATE_KEY not found in environment variables")

    chain_id = int(os.getenv("CHAIN_ID", "137"))
    rpc_url = os.getenv("RPC_URL") or None
    proxy_address = os.getenv("PROXY_WALLET_ADDRESS") or None

    return PolymarketClient(
        private_key=private_key,
        chain_id=chain_id,
        rpc_url=rpc_url,
        proxy_address=proxy_address
    )

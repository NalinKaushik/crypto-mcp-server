import asyncio
import logging
from typing import Optional, Dict, List, Any
import ccxt.async_support as ccxt

from src.crypto_mcp.utils.error_handler import (
    retry_with_backoff,
    handle_exchange_error,
    ExchangeConnectionError,
    InvalidPairError,
    TimeoutError as CustomTimeoutError,
)


logger = logging.getLogger(__name__)


class CCXTClient:
    """Async CCXT client for cryptocurrency exchanges."""
    
    # Exchange-specific rate limits (requests per second)
    RATE_LIMITS = {
        "binance": 10,
        "coinbase": 5,
        "kraken": 15,
        "kucoin": 10,
        "huobi": 10,
        "bitfinex": 10,
        "okx": 10,
        "bybit": 10,
    }
    
    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        timeout: int = 10000,
    ):
        """
        Initialize CCXT client.
        
        Args:
            exchange_id: Name of exchange
            api_key: API key for trading
            secret: API secret for trading
            timeout: Request timeout in ms
        """
        self.exchange_id = exchange_id.lower()
        self.timeout = timeout
        self._exchange = None
        self._initialized = False
        
        # Get exchange class
        if not hasattr(ccxt, self.exchange_id):
            raise ValueError(f"Exchange '{self.exchange_id}' not supported by CCXT")
        
        exchange_class = getattr(ccxt, self.exchange_id)
        
        # Initialize exchange with optional credentials
        config = {"timeout": timeout}
        if api_key:
            config["apiKey"] = api_key
        if secret:
            config["secret"] = secret
        
        self._exchange = exchange_class(config)
    
    async def initialize(self) -> None:
        """Load market data and initialize exchange."""
        if self._initialized:
            return
        
        try:
            await self._exchange.load_markets()
            self._initialized = True
            logger.info(f"Initialized CCXT client for {self.exchange_id}")
        except Exception as e:
            raise ExchangeConnectionError(
                f"Failed to initialize {self.exchange_id}: {str(e)}",
                exchange=self.exchange_id
            )
    
    @handle_exchange_error("binance")
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker data for a symbol.
        
        Args:
            symbol: Trading pair (e.g., BTC/USDT)
        
        Returns:
            Ticker data dictionary
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            ticker = await self._exchange.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "exchange": self.exchange_id,
                "price": ticker.get("last"),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "high": ticker.get("high"),
                "low": ticker.get("low"),
                "volume": ticker.get("quoteVolume"),
                "baseVolume": ticker.get("baseVolume"),
                "timestamp": ticker.get("timestamp"),
                "change": ticker.get("change"),
                "changePercent": ticker.get("percentage"),
            }
        except Exception as e:
            raise
    
    @handle_exchange_error("binance")
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: Optional[int] = None,
        limit: int = 100,
    ) -> List[List]:
        """
        Fetch OHLCV (candlestick) data.
        
        Args:
            symbol: Trading pair
            timeframe: Candlestick timeframe (1m, 5m, 1h, 1d, etc.)
            since: Fetch data since this timestamp (ms)
            limit: Number of candles to fetch
        
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            ohlcv = await self._exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                since=since,
                limit=limit
            )
            return ohlcv
        except Exception as e:
            raise
    
    @handle_exchange_error("binance")
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_order_book(
        self,
        symbol: str,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Fetch order book (bid/ask depth).
        
        Args:
            symbol: Trading pair
            limit: Number of levels
        
        Returns:
            Order book data
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            orderbook = await self._exchange.fetch_order_book(symbol, limit=limit)
            return {
                "symbol": symbol,
                "exchange": self.exchange_id,
                "bids": orderbook.get("bids", [])[:limit],
                "asks": orderbook.get("asks", [])[:limit],
                "timestamp": orderbook.get("timestamp"),
                "datetime": orderbook.get("datetime"),
            }
        except Exception as e:
            raise
    
    @handle_exchange_error("binance")
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def fetch_trades(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Fetch recent trades.
        
        Args:
            symbol: Trading pair
            limit: Number of trades
        
        Returns:
            List of trade records
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            trades = await self._exchange.fetch_trades(symbol, limit=limit)
            return [
                {
                    "id": t.get("id"),
                    "symbol": t.get("symbol"),
                    "price": t.get("price"),
                    "amount": t.get("amount"),
                    "cost": t.get("cost"),
                    "side": t.get("side"),
                    "timestamp": t.get("timestamp"),
                }
                for t in trades
            ]
        except Exception as e:
            raise
    
    def get_symbols(self) -> List[str]:
        """Get list of available trading pairs."""
        if not self._initialized:
            raise RuntimeError("Client not initialized. Call initialize() first.")
        
        return self._exchange.symbols
    
    def get_timeframes(self) -> List[str]:
        """Get supported timeframes."""
        return list(self._exchange.timeframes.keys()) if self._exchange.timeframes else []
    
    async def close(self) -> None:
        """Close connection."""
        if self._exchange:
            await self._exchange.close()
            self._initialized = False
            logger.debug(f"Closed CCXT client for {self.exchange_id}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class MultiExchangeClient:
    """Client for fetching data from multiple exchanges."""
    
    def __init__(self, exchanges: Optional[List[str]] = None):
        """
        Initialize multi-exchange client.
        
        Args:
            exchanges: List of exchange names
        """
        self.exchanges = exchanges or ["binance", "coinbase", "kraken"]
        self._clients: Dict[str, CCXTClient] = {}
    
    async def initialize(self) -> None:
        """Initialize all exchange clients."""
        for exchange in self.exchanges:
            try:
                client = CCXTClient(exchange)
                await client.initialize()
                self._clients[exchange] = client
                logger.info(f"Initialized {exchange} client")
            except Exception as e:
                logger.warning(f"Failed to initialize {exchange}: {str(e)}")
    
    async def fetch_price_from_all(self, symbol: str) -> Dict[str, Dict]:
        """Fetch price from all exchanges."""
        results = {}
        tasks = []
        
        for exchange, client in self._clients.items():
            tasks.append(self._fetch_with_fallback(client, symbol, exchange))
        
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        for exchange, result in zip(self._clients.keys(), results_list):
            if isinstance(result, Exception):
                results[exchange] = {"error": str(result)}
            else:
                results[exchange] = result
        
        return results
    
    async def _fetch_with_fallback(
        self,
        client: CCXTClient,
        symbol: str,
        exchange: str
    ) -> Optional[Dict]:
        """Fetch with error handling."""
        try:
            return await client.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Error fetching {symbol} from {exchange}: {str(e)}")
            return None
    
    async def close_all(self) -> None:
        """Close all exchange connections."""
        for client in self._clients.values():
            await client.close()


print("clients/ccxt_client.py created successfully")
print("Features: Async CCXT, error handling, multi-exchange support")
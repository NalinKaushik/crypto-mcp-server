
import logging
from typing import Dict, Any, Optional, List
from src.crypto_mcp.clients.ccxt_client import CCXTClient, MultiExchangeClient
from src.crypto_mcp.utils.cache import CacheManager, CacheKey
from src.crypto_mcp.utils.rate_limiter import RateLimitManager
from src.crypto_mcp.utils.error_handler import (
    validate_input,
    InvalidPairError,
    ExchangeConnectionError,
)


logger = logging.getLogger(__name__)


class RealtimeTools:
    """Real-time market data tools."""
    
    def __init__(
        self,
        cache_manager: CacheManager,
        rate_limiter: RateLimitManager,
    ):
        self.cache = cache_manager
        self.rate_limiter = rate_limiter
    
    async def get_price(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        """
        Get current cryptocurrency price.
        
        Args:
            symbol: Trading pair (e.g., BTC/USDT)
            exchange: Exchange name
        
        Returns:
            Price data with bid/ask spread
        """
        logger.info(f"Fetching price for {symbol} on {exchange}")
        
        # Check cache
        cached = await self.cache.get_price(symbol, exchange)
        if cached:
            logger.debug(f"Returning cached price for {symbol}")
            return cached
        
        # Rate limit
        await self.rate_limiter.acquire(exchange)
        
        # Fetch from exchange
        try:
            async with CCXTClient(exchange) as client:
                ticker = await client.fetch_ticker(symbol)
                
                result = {
                    "symbol": symbol,
                    "exchange": exchange,
                    "price": ticker["price"],
                    "bid": ticker["bid"],
                    "ask": ticker["ask"],
                    "spread": (ticker["ask"] - ticker["bid"]) if ticker["ask"] and ticker["bid"] else None,
                    "high": ticker["high"],
                    "low": ticker["low"],
                    "volume": ticker["volume"],
                    "timestamp": ticker["timestamp"],
                }
                
                # Cache for 5 seconds
                await self.cache.set_price(symbol, exchange, result, ttl_seconds=5)
                return result
        
        except Exception as e:
            logger.error(f"Error fetching price: {str(e)}")
            raise
    
    async def get_market_summary(
        self,
        symbol: str,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        """
        Get comprehensive market summary.
        
        Args:
            symbol: Trading pair
            exchange: Exchange name
        
        Returns:
            Market summary with OHLC and volume
        """
        logger.info(f"Fetching market summary for {symbol}")
        
        # Rate limit
        await self.rate_limiter.acquire(exchange)
        
        try:
            async with CCXTClient(exchange) as client:
                ticker = await client.fetch_ticker(symbol)
                orderbook = await client.fetch_order_book(symbol, limit=5)
                
                return {
                    "symbol": symbol,
                    "exchange": exchange,
                    "price": ticker["price"],
                    "open": ticker.get("open"),
                    "high": ticker["high"],
                    "low": ticker["low"],
                    "close": ticker["price"],
                    "volume": ticker["volume"],
                    "baseVolume": ticker["baseVolume"],
                    "change_24h": ticker["change"],
                    "change_percent_24h": ticker["changePercent"],
                    "bid": ticker["bid"],
                    "ask": ticker["ask"],
                    "bid_volume": orderbook["bids"][0][1] if orderbook["bids"] else None,
                    "ask_volume": orderbook["asks"][0][1] if orderbook["asks"] else None,
                    "timestamp": ticker["timestamp"],
                }
        
        except Exception as e:
            logger.error(f"Error fetching market summary: {str(e)}")
            raise
    
    async def get_top_volumes(
        self,
        limit: int = 10,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        """
        Get top trading pairs by volume.
        
        Args:
            limit: Number of pairs to return
            exchange: Exchange name
        
        Returns:
            List of top volume pairs
        """
        logger.info(f"Fetching top {limit} volumes on {exchange}")
        
        # Rate limit
        await self.rate_limiter.acquire(exchange)
        
        try:
            async with CCXTClient(exchange) as client:
                symbols = client.get_symbols()
                
                # Fetch tickers for all symbols (batched)
                tickers = []
                for symbol in symbols[:100]:  # Limit to first 100
                    try:
                        ticker = await client.fetch_ticker(symbol)
                        tickers.append(ticker)
                    except:
                        continue
                
                # Sort by volume
                sorted_tickers = sorted(
                    tickers,
                    key=lambda x: x.get("volume", 0) or 0,
                    reverse=True
                )
                
                top_pairs = [
                    {
                        "symbol": t["symbol"],
                        "price": t["price"],
                        "volume": t["volume"],
                        "change_24h": t["changePercent"],
                    }
                    for t in sorted_tickers[:limit]
                ]
                
                return {
                    "exchange": exchange,
                    "limit": limit,
                    "top_pairs": top_pairs,
                    "total_symbols": len(symbols),
                }
        
        except Exception as e:
            logger.error(f"Error fetching top volumes: {str(e)}")
            raise
    
    async def list_exchanges(self) -> Dict[str, Any]:
        """
        List all supported exchanges.
        
        Returns:
            List of available exchanges
        """
        from src.crypto_mcp.config import ServerConfig
        config = ServerConfig()
        
        return {
            "exchanges": config.supported_exchanges,
            "count": len(config.supported_exchanges),
            "default": config.default_exchange,
        }
    
    async def get_order_book(
        self,
        symbol: str,
        exchange: str = "binance",
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Get order book depth.
        
        Args:
            symbol: Trading pair
            exchange: Exchange name
            limit: Depth levels
        
        Returns:
            Order book with bids/asks
        """
        logger.info(f"Fetching order book for {symbol}")
        
        # Rate limit
        await self.rate_limiter.acquire(exchange)
        
        try:
            async with CCXTClient(exchange) as client:
                orderbook = await client.fetch_order_book(symbol, limit=limit)
                
                # Calculate midprice
                best_bid = orderbook["bids"][0][0] if orderbook["bids"] else None
                best_ask = orderbook["asks"][0][0] if orderbook["asks"] else None
                
                return {
                    "symbol": symbol,
                    "exchange": exchange,
                    "bids": orderbook["bids"][:limit],
                    "asks": orderbook["asks"][:limit],
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": (best_ask - best_bid) if best_bid and best_ask else None,
                    "timestamp": orderbook["timestamp"],
                }
        
        except Exception as e:
            logger.error(f"Error fetching order book: {str(e)}")
            raise
    
    async def compare_prices(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compare price across multiple exchanges.
        
        Args:
            symbol: Trading pair
            exchanges: List of exchanges to compare
        
        Returns:
            Price comparison data
        """
        logger.info(f"Comparing {symbol} across exchanges")
        
        exchanges = exchanges or ["binance", "coinbase", "kraken"]
        prices = {}
        
        for exchange in exchanges:
            try:
                price = await self.get_price(symbol, exchange)
                prices[exchange] = price
            except Exception as e:
                prices[exchange] = {"error": str(e)}
        
        # Calculate average
        valid_prices = [
            p["price"] for p in prices.values()
            if isinstance(p, dict) and "price" in p
        ]
        
        avg_price = sum(valid_prices) / len(valid_prices) if valid_prices else None
        
        return {
            "symbol": symbol,
            "exchanges": prices,
            "average_price": avg_price,
            "count": len(valid_prices),
        }


print("tools/realtime.py created successfully")
print("Features: Price fetching, market summary, volume ranking, order book, price comparison")
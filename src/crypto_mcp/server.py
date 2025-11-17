import logging
import asyncio
from typing import Any
from mcp.server import Server
from contextlib import asynccontextmanager

from src.crypto_mcp.config import get_config
from src.crypto_mcp.utils.cache import CacheManager, MemoryCache
from src.crypto_mcp.utils.rate_limiter import RateLimitManager
from src.crypto_mcp.utils.error_handler import CryptoMCPError
from src.crypto_mcp.tools.realtime import RealtimeTools
from src.crypto_mcp.tools.historical import HistoricalTools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize configuration
config = get_config()

# Initialize cache and rate limiting
cache_manager = CacheManager(MemoryCache())
rate_limiter = RateLimitManager()

# Initialize tools
realtime_tools = RealtimeTools(cache_manager, rate_limiter)
historical_tools = HistoricalTools(cache_manager, rate_limiter)

# Initialize MCP server
mcp = Server("Crypto Market Data MCP")

# Register rate limiters for supported exchanges
@asynccontextmanager
async def lifespan():
    """Initialize rate limiters on startup."""
    for exchange in config.supported_exchanges:
        rate = config.rate_limit_per_second
        capacity = config.burst_size
        await rate_limiter.register_limiter(exchange, rate, capacity)
        logger.info(f"Registered rate limiter for {exchange}: {rate} req/s")
    yield

# ============================================================================
# REAL-TIME MARKET DATA TOOLS
# ============================================================================

@mcp.call_tool()
async def get_price(symbol: str, exchange: str = "binance") -> str:
    """
    Get current cryptocurrency price.
    """
    try:
        result = await realtime_tools.get_price(symbol, exchange)
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in get_price: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in get_price: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

@mcp.call_tool()
async def get_market_summary(symbol: str, exchange: str = "binance") -> str:
    """
    Get comprehensive market summary for a trading pair.
    """
    try:
        result = await realtime_tools.get_market_summary(symbol, exchange)
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in get_market_summary: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in get_market_summary: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

@mcp.call_tool()
async def get_top_volumes(limit: int = 10, exchange: str = "binance") -> str:
    """
    Get top trading pairs by volume.
    """
    try:
        result = await realtime_tools.get_top_volumes(limit, exchange)
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in get_top_volumes: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in get_top_volumes: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

@mcp.call_tool()
async def list_exchanges() -> str:
    """
    List all supported exchanges.
    """
    try:
        result = await realtime_tools.list_exchanges()
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error in list_exchanges: {str(e)}")
        return {"success": False, "error": f"Error: {str(e)}"}

@mcp.call_tool()
async def get_order_book(symbol: str, exchange: str = "binance", limit: int = 20) -> str:
    """
    Get order book (bid/ask depth).
    """
    try:
        result = await realtime_tools.get_order_book(symbol, exchange, limit)
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in get_order_book: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in get_order_book: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

@mcp.call_tool()
async def compare_prices(symbol: str, exchanges: list = None) -> str:
    """
    Compare price across multiple exchanges.
    """
    try:
        result = await realtime_tools.compare_prices(symbol, exchanges)
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in compare_prices: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in compare_prices: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

# ============================================================================
# HISTORICAL DATA TOOLS
# ============================================================================

@mcp.call_tool()
async def get_historical_ohlcv(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 100,
    exchange: str = "binance"
) -> str:
    """
    Get historical OHLCV (candlestick) data.
    """
    try:
        result = await historical_tools.get_historical_ohlcv(
            symbol, timeframe, limit, exchange=exchange
        )
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in get_historical_ohlcv: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in get_historical_ohlcv: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

@mcp.call_tool()
async def get_price_change(
    symbol: str,
    period: str = "24h",
    exchange: str = "binance"
) -> str:
    """
    Calculate price change over time period.
    """
    try:
        result = await historical_tools.get_price_change(symbol, period, exchange)
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in get_price_change: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in get_price_change: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

@mcp.call_tool()
async def get_volume_history(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 24,
    exchange: str = "binance"
) -> str:
    """
    Get trading volume history.
    """
    try:
        result = await historical_tools.get_volume_history(
            symbol, timeframe, limit, exchange
        )
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in get_volume_history: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in get_volume_history: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

@mcp.call_tool()
async def get_moving_average(
    symbol: str,
    period: int = 20,
    timeframe: str = "1h",
    exchange: str = "binance"
) -> str:
    """
    Calculate simple moving average.
    """
    try:
        result = await historical_tools.get_moving_average(
            symbol, period, timeframe, exchange
        )
        return {"success": True, "data": result}
    except CryptoMCPError as e:
        logger.error(f"Error in get_moving_average: {str(e)}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in get_moving_average: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}

# ============================================================================
# UTILITY TOOLS
# ============================================================================

@mcp.call_tool()
async def get_cache_stats() -> str:
    """
    Get cache statistics.
    """
    try:
        stats = await cache_manager.get_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}")
        return {"success": False, "error": str(e)}

@mcp.call_tool()
async def get_rate_limit_stats() -> str:
    """
    Get rate limiting statistics.
    """
    try:
        stats = await rate_limiter.get_all_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"Error getting rate limit stats: {str(e)}")
        return {"success": False, "error": str(e)}

def run_server():
    """Run the MCP server."""
    logger.info(f"Starting {config.server_name} v{config.server_version}")
    logger.info(f"Supported exchanges: {config.supported_exchanges}")
    mcp.run(transport="stdio")

if __name__ == "__main__":
    run_server()

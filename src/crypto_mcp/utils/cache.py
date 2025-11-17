import time
import asyncio
import json
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import logging


logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a cached entry with TTL."""
    
    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        elapsed = time.time() - self.created_at
        return elapsed > self.ttl_seconds
    
    def remaining_ttl(self) -> int:
        """Get remaining TTL in seconds."""
        elapsed = time.time() - self.created_at
        return max(0, int(self.ttl_seconds - elapsed))


class CacheBackend(ABC):
    """Abstract base class for cache backends."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Store value in cache with TTL."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached data."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass


class MemoryCache(CacheBackend):
    """In-memory cache implementation."""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    self._hits += 1
                    logger.debug(f"Cache hit: {key} (TTL: {entry.remaining_ttl()}s)")
                    return entry.value
                else:
                    del self._cache[key]
            
            self._misses += 1
            logger.debug(f"Cache miss: {key}")
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        async with self._lock:
            self._cache[key] = CacheEntry(value, ttl_seconds)
            logger.debug(f"Cache set: {key} (TTL: {ttl_seconds}s)")
    
    async def delete(self, key: str) -> None:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache delete: {key}")
    
    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "backend": "memory",
                "size": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.2f}%",
                "total_requests": total_requests
            }


class CacheKey:
    """Utility class for generating cache keys."""
    
    @staticmethod
    def price(symbol: str, exchange: str) -> str:
        """Generate cache key for price data."""
        return f"price:{exchange}:{symbol.upper()}"
    
    @staticmethod
    def ticker(symbol: str, exchange: str) -> str:
        """Generate cache key for ticker data."""
        return f"ticker:{exchange}:{symbol.upper()}"
    
    @staticmethod
    def ohlcv(symbol: str, exchange: str, timeframe: str) -> str:
        """Generate cache key for OHLCV data."""
        return f"ohlcv:{exchange}:{symbol.upper()}:{timeframe}"
    
    @staticmethod
    def market_data(exchange: str) -> str:
        """Generate cache key for market data."""
        return f"market_data:{exchange}"
    
    @staticmethod
    def global_metrics() -> str:
        """Generate cache key for global metrics."""
        return "global_metrics"
    
    @staticmethod
    def exchange_info(exchange: str) -> str:
        """Generate cache key for exchange info."""
        return f"exchange_info:{exchange}"


class CacheManager:
    """Central cache manager for the MCP server."""
    
    def __init__(self, backend: Optional[CacheBackend] = None):
        self.backend = backend or MemoryCache()
    
    async def get_price(self, symbol: str, exchange: str) -> Optional[Dict]:
        """Get cached price."""
        key = CacheKey.price(symbol, exchange)
        return await self.backend.get(key)
    
    async def set_price(
        self,
        symbol: str,
        exchange: str,
        price_data: Dict,
        ttl_seconds: int = 5
    ) -> None:
        """Cache price with default 5s TTL."""
        key = CacheKey.price(symbol, exchange)
        await self.backend.set(key, price_data, ttl_seconds)
    
    async def get_ohlcv(
        self,
        symbol: str,
        exchange: str,
        timeframe: str
    ) -> Optional[List]:
        """Get cached OHLCV data."""
        key = CacheKey.ohlcv(symbol, exchange, timeframe)
        return await self.backend.get(key)
    
    async def set_ohlcv(
        self,
        symbol: str,
        exchange: str,
        timeframe: str,
        ohlcv_data: List,
        ttl_seconds: int = 60
    ) -> None:
        """Cache OHLCV data with default 60s TTL."""
        key = CacheKey.ohlcv(symbol, exchange, timeframe)
        await self.backend.set(key, ohlcv_data, ttl_seconds)
    
    async def get_market_data(self, exchange: str) -> Optional[Dict]:
        """Get cached market data."""
        key = CacheKey.market_data(exchange)
        return await self.backend.get(key)
    
    async def set_market_data(
        self,
        exchange: str,
        market_data: Dict,
        ttl_seconds: int = 300
    ) -> None:
        """Cache market data with default 5min TTL."""
        key = CacheKey.market_data(exchange)
        await self.backend.set(key, market_data, ttl_seconds)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return await self.backend.get_stats()


print("utils/cache.py created successfully")
print("Features: TTL-based expiration, multiple backends, hit/miss tracking")
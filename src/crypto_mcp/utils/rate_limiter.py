import asyncio
import time
import logging
from typing import Optional, Dict
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    rate: int  # tokens per second
    capacity: int  # burst capacity
    name: str = "unnamed"


class TokenBucket:
    """Token bucket for rate limiting."""
    
    def __init__(self, rate: int, capacity: int, name: str = "bucket"):
        """
        Initialize token bucket.
        
        Args:
            rate: Tokens refilled per second
            capacity: Maximum tokens in bucket
            name: Name for logging
        """
        self.rate = rate
        self.capacity = capacity
        self.name = name
        self.tokens = float(capacity)
        self.last_update = time.time()
        self._lock = asyncio.Lock()
        self._requests = 0
        self._rejections = 0
    
    async def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens from bucket.
        
        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum wait time
        
        Returns:
            True if tokens acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            async with self._lock:
                now = time.time()
                elapsed = now - self.last_update
                
                # Refill tokens
                self.tokens = min(
                    self.capacity,
                    self.tokens + elapsed * self.rate
                )
                self.last_update = now
                
                # Check if we have enough tokens
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self._requests += 1
                    logger.debug(
                        f"{self.name}: Acquired {tokens} tokens "
                        f"({self.tokens:.2f} remaining)"
                    )
                    return True
            
            # Check timeout
            if timeout is not None:
                elapsed_wait = time.time() - start_time
                if elapsed_wait >= timeout:
                    self._rejections += 1
                    logger.warning(
                        f"{self.name}: Rate limit timeout after {elapsed_wait:.2f}s"
                    )
                    return False
            
            # Wait before retry
            await asyncio.sleep(0.01)
    
    async def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting."""
        async with self._lock:
            if self.tokens >= tokens:
                self.tokens -= tokens
                self._requests += 1
                return True
            else:
                self._rejections += 1
                return False
    
    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        total = self._requests + self._rejections
        success_rate = (self._requests / total * 100) if total > 0 else 0
        
        return {
            "name": self.name,
            "rate": self.rate,
            "capacity": self.capacity,
            "current_tokens": f"{self.tokens:.2f}",
            "requests": self._requests,
            "rejections": self._rejections,
            "success_rate": f"{success_rate:.2f}%"
        }
    
    async def reset(self):
        """Reset rate limiter."""
        async with self._lock:
            self.tokens = float(self.capacity)
            self.last_update = time.time()
            self._requests = 0
            self._rejections = 0


class RateLimitManager:
    """Manages rate limiters for multiple exchanges."""
    
    def __init__(self):
        self._limiters: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()
    
    async def register_limiter(
        self,
        exchange: str,
        rate: int,
        capacity: int
    ) -> TokenBucket:
        """Register rate limiter for an exchange."""
        async with self._lock:
            if exchange not in self._limiters:
                self._limiters[exchange] = TokenBucket(rate, capacity, exchange)
                logger.info(
                    f"Registered rate limiter for {exchange}: "
                    f"{rate} req/s, capacity {capacity}"
                )
            return self._limiters[exchange]
    
    async def get_limiter(self, exchange: str) -> Optional[TokenBucket]:
        """Get rate limiter for exchange."""
        async with self._lock:
            return self._limiters.get(exchange)
    
    async def acquire(self, exchange: str, tokens: int = 1) -> bool:
        """Acquire tokens for exchange."""
        limiter = await self.get_limiter(exchange)
        if limiter:
            return await limiter.acquire(tokens)
        return True  # No limit if not registered
    
    async def get_all_stats(self) -> Dict[str, Dict]:
        """Get statistics for all limiters."""
        async with self._lock:
            return {
                name: limiter.get_stats()
                for name, limiter in self._limiters.items()
            }


class RateLimitDecorator:
    """Decorator for automatic rate limiting."""
    
    def __init__(self, exchange: str, rate_manager: RateLimitManager, tokens: int = 1):
        self.exchange = exchange
        self.rate_manager = rate_manager
        self.tokens = tokens
    
    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            # Acquire rate limit tokens
            acquired = await self.rate_manager.acquire(self.exchange, self.tokens)
            if not acquired:
                logger.error(f"Rate limit timeout for {self.exchange}")
                raise RuntimeError(f"Rate limit exceeded for {self.exchange}")
            
            return await func(*args, **kwargs)
        
        return wrapper


print("utils/rate_limiter.py created successfully")
print("Features: Token bucket, rate limit manager, per-exchange limiting")
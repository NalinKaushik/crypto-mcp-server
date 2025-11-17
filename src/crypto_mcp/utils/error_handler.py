import asyncio
import logging
from functools import wraps
from typing import Callable, Any, TypeVar, Optional
import time
from enum import Enum


logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Custom Exceptions
class CryptoMCPError(Exception):
    """Base exception for all MCP crypto errors."""
    
    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        self.message = message
        self.severity = severity
        super().__init__(self.message)


class ExchangeConnectionError(CryptoMCPError):
    """Raised when exchange connection fails."""
    
    def __init__(self, message: str, exchange: Optional[str] = None):
        super().__init__(f"Exchange connection error [{exchange}]: {message}")
        self.exchange = exchange


class RateLimitError(CryptoMCPError):
    """Raised when API rate limit exceeded."""
    
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(f"Rate limit exceeded: {message}", ErrorSeverity.HIGH)
        self.retry_after = retry_after


class InvalidPairError(CryptoMCPError):
    """Raised when trading pair format is invalid."""
    
    def __init__(self, pair: str, exchange: Optional[str] = None):
        super().__init__(f"Invalid trading pair '{pair}' on {exchange or 'exchange'}")
        self.pair = pair
        self.exchange = exchange


class TimeoutError(CryptoMCPError):
    """Raised when API request times out."""
    
    def __init__(self, message: str, timeout_seconds: int):
        super().__init__(f"Request timeout after {timeout_seconds}s: {message}", ErrorSeverity.HIGH)
        self.timeout_seconds = timeout_seconds


class ValidationError(CryptoMCPError):
    """Raised when input validation fails."""
    
    def __init__(self, field: str, value: Any, reason: str):
        super().__init__(f"Validation error in '{field}': {value} - {reason}", ErrorSeverity.LOW)
        self.field = field
        self.value = value


class DataError(CryptoMCPError):
    """Raised when data processing fails."""
    
    def __init__(self, message: str, data: Optional[Any] = None):
        super().__init__(f"Data processing error: {message}", ErrorSeverity.MEDIUM)
        self.data = data


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch for retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    logger.debug(f"Attempting {func.__name__} (attempt {attempt + 1}/{max_retries})")
                    return await func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries - 1:
                        logger.error(f"Failed after {max_retries} retries: {str(e)}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {str(e)}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                
                except Exception as e:
                    logger.critical(f"Unexpected error in {func.__name__}: {str(e)}")
                    raise
            
            raise last_exception
        
        return wrapper
    return decorator


def handle_exchange_error(exchange_name: str) -> Callable:
    """
    Decorator to handle and wrap exchange-specific errors.
    
    Args:
        exchange_name: Name of the exchange for error context
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            
            except asyncio.TimeoutError as e:
                raise TimeoutError(
                    f"Request to {exchange_name} timed out",
                    timeout_seconds=10
                ) from e
            
            except ConnectionError as e:
                raise ExchangeConnectionError(
                    f"Failed to connect to {exchange_name}: {str(e)}",
                    exchange=exchange_name
                ) from e
            
            except Exception as e:
                # Check for rate limit indicators
                if "rate" in str(e).lower() or "429" in str(e):
                    raise RateLimitError(
                        f"Rate limited on {exchange_name}: {str(e)}"
                    ) from e
                
                # Check for invalid pair
                if "invalid" in str(e).lower() or "not found" in str(e).lower():
                    raise InvalidPairError(
                        pair=kwargs.get("symbol", "unknown"),
                        exchange=exchange_name
                    ) from e
                
                raise ExchangeConnectionError(
                    f"Error from {exchange_name}: {str(e)}",
                    exchange=exchange_name
                ) from e
        
        return wrapper
    return decorator


def validate_input(**validators: Callable[[str, Any], None]) -> Callable:
    """
    Decorator to validate function inputs before execution.
    
    Args:
        validators: Keyword arguments mapping parameter names to validator functions
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Validate kwargs
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    try:
                        validator(param_name, kwargs[param_name])
                    except Exception as e:
                        raise ValidationError(param_name, kwargs[param_name], str(e))
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class ErrorContextManager:
    """Context manager for error tracking and reporting."""
    
    def __init__(self, operation: str):
        self.operation = operation
        self.start_time = None
        self.errors = []
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        
        if exc_type is not None:
            logger.error(
                f"Operation '{self.operation}' failed after {elapsed:.2f}s: "
                f"{exc_type.__name__}: {str(exc_val)}"
            )
            self.errors.append({
                "type": exc_type.__name__,
                "message": str(exc_val),
                "duration": elapsed
            })
        else:
            logger.info(f"Operation '{self.operation}' completed in {elapsed:.2f}s")
        
        return False  # Don't suppress exceptions
    
    def log_error(self, error: Exception):
        """Log an error without raising."""
        self.errors.append({
            "type": type(error).__name__,
            "message": str(error)
        })
        logger.warning(f"Error in '{self.operation}': {str(error)}")


print("utils/error_handler.py:")
print("=" * 80)
print(error_handler_py[:1500] + "\n... [truncated for display] ...\n")
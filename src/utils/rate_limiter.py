"""
Rate limiter implementation for web scraping.
实现基于令牌桶算法的请求频率限制器。
"""

import asyncio
import time
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for controlling request frequency.
    基于令牌桶算法的请求频率限制器。
    """
    
    def __init__(self, max_tokens: int = 10, refill_rate: float = 1.0):
        """
        Initialize rate limiter.
        
        Args:
            max_tokens: Maximum number of tokens in the bucket
            refill_rate: Tokens added per second
        """
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.tokens = max_tokens
        self.last_refill = time.time()
        self._lock = asyncio.Lock()
        
        logger.info(
            "rate_limiter.initialized",
            max_tokens=max_tokens,
            refill_rate=refill_rate
        )
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from the bucket.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False otherwise
        """
        async with self._lock:
            await self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    "rate_limiter.token_acquired",
                    tokens_requested=tokens,
                    tokens_remaining=self.tokens
                )
                return True
            else:
                logger.warning(
                    "rate_limiter.token_denied",
                    tokens_requested=tokens,
                    tokens_available=self.tokens
                )
                return False
    
    async def wait_for_token(self, tokens: int = 1) -> None:
        """
        Wait until tokens are available.
        
        Args:
            tokens: Number of tokens needed
        """
        while not await self.acquire(tokens):
            wait_time = tokens / self.refill_rate
            logger.info(
                "rate_limiter.waiting",
                wait_time=wait_time,
                tokens_needed=tokens
            )
            await asyncio.sleep(wait_time)
    
    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        if elapsed > 0:
            tokens_to_add = elapsed * self.refill_rate
            self.tokens = min(self.max_tokens, self.tokens + tokens_to_add)
            self.last_refill = now
            
            logger.debug(
                "rate_limiter.refilled",
                tokens_added=tokens_to_add,
                current_tokens=self.tokens
            )
    
    def get_status(self) -> dict:
        """Get current rate limiter status."""
        return {
            "max_tokens": self.max_tokens,
            "current_tokens": self.tokens,
            "refill_rate": self.refill_rate,
            "last_refill": self.last_refill
        }
"""
Tests for rate limiter functionality.
"""

import asyncio
import time
import pytest

from src.utils.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test rate limiter implementation."""
    
    @pytest.mark.asyncio
    async def test_token_acquisition(self):
        """Test basic token acquisition."""
        limiter = RateLimiter(max_tokens=5, refill_rate=1.0)
        
        # Should be able to acquire tokens immediately
        assert await limiter.acquire(1) is True
        assert await limiter.acquire(2) is True
        assert await limiter.acquire(2) is True
        
        # Should be out of tokens now
        assert await limiter.acquire(1) is False
    
    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Test token refill over time."""
        limiter = RateLimiter(max_tokens=2, refill_rate=2.0)  # 2 tokens per second
        
        # Use all tokens
        assert await limiter.acquire(2) is True
        assert await limiter.acquire(1) is False
        
        # Wait for refill
        await asyncio.sleep(1.1)  # Allow time for 2 tokens to refill
        
        # Should have tokens again
        assert await limiter.acquire(2) is True
    
    @pytest.mark.asyncio
    async def test_wait_for_token(self):
        """Test waiting for tokens."""
        limiter = RateLimiter(max_tokens=1, refill_rate=2.0)
        
        # Use the only token
        assert await limiter.acquire(1) is True
        
        # This should wait and eventually succeed
        start_time = time.time()
        await limiter.wait_for_token(1)
        elapsed = time.time() - start_time
        
        # Should have waited approximately 0.5 seconds (1 token / 2 tokens per second)
        assert 0.4 <= elapsed <= 0.7
    
    def test_get_status(self):
        """Test status reporting."""
        limiter = RateLimiter(max_tokens=10, refill_rate=2.5)
        status = limiter.get_status()
        
        assert status["max_tokens"] == 10
        assert status["current_tokens"] == 10
        assert status["refill_rate"] == 2.5
        assert "last_refill" in status
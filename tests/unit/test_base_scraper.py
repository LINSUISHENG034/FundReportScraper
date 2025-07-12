"""
Tests for base scraper functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.scrapers.base import BaseScraper, NetworkError, ParseError
from src.utils.rate_limiter import RateLimiter


class TestBaseScraper(BaseScraper):
    """Test implementation of BaseScraper."""
    
    async def scrape(self, **kwargs):
        """Test implementation of abstract method."""
        return {"test": "data"}


class TestBaseScraperFunctionality:
    """Test base scraper functionality."""
    
    @pytest.fixture
    def scraper(self):
        """Create test scraper instance."""
        return TestBaseScraper(base_url="https://test.example.com")
    
    @pytest.mark.asyncio
    async def test_session_management(self, scraper):
        """Test session creation and cleanup."""
        assert scraper.session is None
        
        await scraper.start_session()
        assert scraper.session is not None
        
        await scraper.close_session()
        assert scraper.session is None
    
    @pytest.mark.asyncio
    async def test_context_manager(self, scraper):
        """Test async context manager."""
        async with scraper as s:
            assert s.session is not None
        
        # Session should be closed after context exit
        assert scraper.session is None
    
    def test_build_url(self, scraper):
        """Test URL building."""
        # Simple path
        url = scraper.build_url("/api/data")
        assert url == "https://test.example.com/api/data"
        
        # With parameters
        url = scraper.build_url("/search", {"q": "test", "page": "1"})
        assert "q=test" in url
        assert "page=1" in url
    
    @pytest.mark.asyncio
    async def test_request_with_rate_limiting(self, scraper):
        """Test request with rate limiting."""
        # Mock rate limiter
        mock_limiter = AsyncMock(spec=RateLimiter)
        scraper.rate_limiter = mock_limiter
        
        # Mock HTTP session
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"test content"
        mock_response.headers = {"content-type": "application/json"}
        
        mock_session = AsyncMock()
        mock_session.request.return_value = mock_response
        scraper.session = mock_session
        
        # Make request
        response = await scraper.request("GET", "/test")
        
        # Verify rate limiting was called
        mock_limiter.wait_for_token.assert_called_once()
        
        # Verify request was made
        mock_session.request.assert_called_once()
        
        assert response == mock_response
    
    @pytest.mark.asyncio
    async def test_request_retry_logic(self, scraper):
        """Test request retry on failures."""
        mock_limiter = AsyncMock(spec=RateLimiter)
        scraper.rate_limiter = mock_limiter
        
        # Mock session with failure then success
        mock_session = AsyncMock()
        
        # First call fails, second succeeds
        first_response = MagicMock()
        first_response.raise_for_status.side_effect = Exception("Network error")
        
        second_response = MagicMock()
        second_response.status_code = 200
        second_response.content = b"success"
        second_response.headers = {"content-type": "text/html"}
        
        mock_session.request.side_effect = [
            Exception("Network error"),  # First attempt fails
            second_response  # Second attempt succeeds
        ]
        
        scraper.session = mock_session
        
        with patch('asyncio.sleep', new_callable=AsyncMock):  # Speed up test
            response = await scraper.request("GET", "/test")
        
        # Should have retried and succeeded
        assert mock_session.request.call_count == 2
        assert response == second_response
    
    @pytest.mark.asyncio
    async def test_request_max_retries_exceeded(self, scraper):
        """Test behavior when max retries are exceeded."""
        mock_limiter = AsyncMock(spec=RateLimiter)
        scraper.rate_limiter = mock_limiter
        
        # Mock session that always fails
        mock_session = AsyncMock()
        mock_session.request.side_effect = Exception("Persistent error")
        scraper.session = mock_session
        
        # Override max retries for faster test
        with patch('src.core.config.settings.scraper.max_retries', 1):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with pytest.raises(NetworkError) as exc_info:
                    await scraper.request("GET", "/test")
                
                assert "Request failed after" in str(exc_info.value)
        
        # Should have attempted max_retries + 1 times
        assert mock_session.request.call_count == 2  # 1 retry + 1 initial = 2
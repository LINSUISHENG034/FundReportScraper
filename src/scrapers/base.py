"""
Base scraper class with common functionality.
提供通用的爬虫基础功能，包括HTTP客户端、错误处理、重试机制等。
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession, ClientResponse

from src.core.config import settings
from src.core.logging import get_logger
from src.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


class ScrapingError(Exception):
    """Base exception for scraping errors."""

    pass


class NetworkError(ScrapingError):
    """Network-related scraping error."""

    pass


class ParseError(ScrapingError):
    """Data parsing error."""

    pass


class BaseScraper(ABC):
    """
    Base scraper class with common functionality.
    基础爬虫类，提供通用的爬取功能。
    """

    def __init__(
        self,
        base_url: str = None,
        rate_limiter: RateLimiter = None,
        session: Optional[ClientSession] = None,
    ):
        """
        Initialize base scraper.

        Args:
            base_url: Base URL for the target website
            rate_limiter: Rate limiter instance
            session: Optional shared httpx.AsyncClient session
        """
        self.base_url = base_url or settings.target.base_url
        self.rate_limiter = rate_limiter or RateLimiter(
            max_tokens=60,  # 60 requests per minute max
            refill_rate=1.0,  # 1 request per second
        )
        self.session = session

        # HTTP configuration
        self.headers = {
            "User-Agent": settings.scraper.user_agent,
            "Accept": "application/json, text/html, application/xhtml+xml, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        self.timeout = aiohttp.ClientTimeout(total=settings.scraper.timeout)

        logger.info(
            "scraper.initialized",
            base_url=self.base_url,
            user_agent=settings.scraper.user_agent[:50] + "...",
            timeout=settings.scraper.timeout,
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()

    async def start_session(self) -> None:
        """Start HTTP session."""
        if self.session is None:
            self.session = ClientSession(
                headers=self.headers,
                timeout=self.timeout,
                connector=aiohttp.TCPConnector(verify_ssl=True),
            )
            logger.info("scraper.session.started")

    async def close_session(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("scraper.session.closed")

    async def request(
        self,
        method: str,
        url: str,
        params: Dict = None,
        data: Dict = None,
        json_data: Dict = None,
        headers: Dict = None,
        **kwargs,
    ) -> ClientResponse:
        """
        Make HTTP request with rate limiting and error handling.

        Args:
            method: HTTP method
            url: Request URL
            params: Query parameters
            data: Form data
            json_data: JSON data
            headers: Additional headers
            **kwargs: Additional request arguments

        Returns:
            HTTP response

        Raises:
            NetworkError: On network or HTTP errors
        """
        if self.session is None:
            await self.start_session()

        # Rate limiting
        await self.rate_limiter.wait_for_token()

        # Prepare request
        full_url = urljoin(self.base_url, url) if not url.startswith("http") else url
        request_headers = {**self.headers}
        if headers:
            request_headers.update(headers)

        request_log = logger.bind(
            method=method, url=full_url, params=params, has_data=bool(data or json_data)
        )

        # Retry logic
        max_retries = settings.scraper.max_retries
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                request_log.info(
                    "scraper.request.start",
                    attempt=attempt + 1,
                    max_retries=max_retries + 1,
                )

                response = await self.session.request(
                    method=method,
                    url=full_url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=request_headers,
                    **kwargs,
                )

                # Read response content
                content = await response.read()

                request_log.info(
                    "scraper.request.success",
                    status_code=response.status,
                    response_size=len(content),
                    attempt=attempt + 1,
                )

                # Check for HTTP errors
                response.raise_for_status()

                # Store content for later access
                response._content = content
                return response

            except aiohttp.ClientResponseError as e:
                last_exception = e
                request_log.warning(
                    "scraper.request.http_error",
                    status_code=e.status,
                    error=str(e),
                    attempt=attempt + 1,
                )

                # Don't retry client errors (4xx)
                if 400 <= e.status < 500:
                    raise NetworkError(f"HTTP {e.status}: {e}")

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                request_log.warning(
                    "scraper.request.network_error", error=str(e), attempt=attempt + 1
                )

            # Wait before retry
            if attempt < max_retries:
                wait_time = min(2**attempt, 30)  # Exponential backoff, max 30s
                request_log.info(
                    "scraper.request.retry_wait",
                    wait_time=wait_time,
                    next_attempt=attempt + 2,
                )
                await asyncio.sleep(wait_time)

        # All retries failed
        raise NetworkError(
            f"Request failed after {max_retries + 1} attempts: {last_exception}"
        )

    async def get(self, url: str, **kwargs) -> ClientResponse:
        """Make GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> ClientResponse:
        """Make POST request."""
        return await self.request("POST", url, **kwargs)

    def build_url(self, path: str, params: Dict = None) -> str:
        """
        Build full URL with optional parameters.

        Args:
            path: URL path
            params: Query parameters

        Returns:
            Full URL
        """
        full_url = urljoin(self.base_url, path)

        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{full_url}?{query_string}"

        return full_url

    @abstractmethod
    async def scrape(self, **kwargs) -> Any:
        """
        Abstract method for scraping implementation.
        Subclasses must implement this method.
        """
        pass

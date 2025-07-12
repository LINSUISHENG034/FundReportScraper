"""
Pytest configuration and fixtures for the fund report scraper.
"""

import os
import tempfile
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import get_settings
from src.core.logging import configure_logging


@pytest.fixture(scope="session", autouse=True)
def configure_test_logging() -> None:
    """Configure logging for tests."""
    configure_logging(log_level="DEBUG", json_logs=False)


@pytest.fixture(scope="session")
def test_settings():
    """Get test-specific settings."""
    # Override settings for testing
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Use test database
    os.environ["DEBUG"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"
    
    settings = get_settings()
    # Clear the cache to get updated settings
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_xbrl_content() -> str:
    """Sample XBRL content for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance">
    <!-- Sample XBRL content for testing -->
    <context id="AsOf2023-12-31">
        <entity>
            <identifier scheme="http://www.csrc.gov.cn">000001</identifier>
        </entity>
        <period>
            <instant>2023-12-31</instant>
        </period>
    </context>
    
    <!-- Asset allocation data -->
    <StockInvestments contextRef="AsOf2023-12-31" unitRef="CNY">1000000000</StockInvestments>
    <BondInvestments contextRef="AsOf2023-12-31" unitRef="CNY">500000000</BondInvestments>
    <CashAndEquivalents contextRef="AsOf2023-12-31" unitRef="CNY">100000000</CashAndEquivalents>
</xbrl>"""


@pytest.fixture
def sample_fund_data() -> dict:
    """Sample fund data for testing."""
    return {
        "fund_code": "000001",
        "fund_name": "华夏成长混合",
        "fund_manager": "张三",
        "report_date": "2023-12-31",
        "report_type": "ANNUAL",
        "net_asset_value": 15600000000.00,
        "total_shares": 12000000000.00,
        "unit_nav": 1.3000,
    }


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    async with AsyncClient() as client:
        yield client


class MockResponse:
    """Mock HTTP response for testing."""
    
    def __init__(self, status_code: int = 200, json_data: dict = None, content: bytes = b""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.content = content
        self.headers = {"content-type": "application/json"}
    
    def json(self):
        return self._json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def mock_http_response():
    """Factory for creating mock HTTP responses."""
    return MockResponse
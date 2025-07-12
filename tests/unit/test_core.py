"""
Test configuration and logging setup.
"""

import pytest

from src.core.config import get_settings
from src.core.logging import configure_logging, get_logger


class TestConfiguration:
    """Test configuration management."""
    
    def test_settings_loading(self, test_settings):
        """Test that settings are loaded correctly."""
        assert test_settings.name == "FundReportScraper"
        assert test_settings.version == "0.1.0"
        assert test_settings.debug is True
        
    def test_database_settings(self, test_settings):
        """Test database configuration."""
        assert test_settings.database.url == "sqlite:///:memory:"
        
    def test_redis_settings(self, test_settings):
        """Test Redis configuration."""
        assert test_settings.redis.url == "redis://localhost:6379/15"


class TestLogging:
    """Test structured logging setup."""
    
    def test_logger_creation(self):
        """Test logger creation and basic functionality."""
        logger = get_logger("test_logger")
        assert logger is not None
        
        # Test context binding
        bound_logger = logger.bind(test_id="123", module="test")
        assert bound_logger is not None
        
    def test_logging_configuration(self, caplog):
        """Test logging configuration."""
        configure_logging(log_level="DEBUG", json_logs=False)
        logger = get_logger("test")
        
        # Test logging at different levels
        logger.info("test message", extra_field="test_value")
        logger.warning("test warning")
        logger.error("test error")
        
        # In a real scenario, we would check the log output format
        # For now, just ensure no exceptions are raised
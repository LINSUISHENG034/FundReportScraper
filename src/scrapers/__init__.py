"""Scrapers package initialization."""

from .base import BaseScraper, ScrapingError, NetworkError, ParseError
from .csrc_fund_scraper import CSRCFundReportScraper

__all__ = [
    "BaseScraper", "ScrapingError", "NetworkError", "ParseError",
    "CSRCFundReportScraper"
]
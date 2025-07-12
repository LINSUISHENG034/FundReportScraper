"""
Fund report scraper for CSRC disclosure platform.
专门用于爬取证监会信息披露平台基金报告的爬虫实现。
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from httpx import Response

from src.core.config import settings
from src.core.logging import get_logger
from src.models.database import ReportType
from src.scrapers.base import BaseScraper, ParseError

logger = get_logger(__name__)


class FundReportScraper(BaseScraper):
    """
    CSRC fund report scraper.
    爬取证监会基金报告的专用爬虫。
    """
    
    def __init__(self):
        super().__init__(base_url=settings.target.base_url)
        self.search_url = settings.target.search_url
        
        logger.info(
            "fund_scraper.initialized",
            search_url=self.search_url
        )
    
    async def get_report_list(
        self,
        year: int,
        report_type: ReportType,
        page: int = 1,
        page_size: int = 100
    ) -> Tuple[List[Dict], bool]:
        """
        Get fund report list from CSRC platform.
        
        Args:
            year: Report year
            report_type: Type of report
            page: Page number (1-based)
            page_size: Number of reports per page
            
        Returns:
            Tuple of (report_list, has_next_page)
            
        Raises:
            ParseError: If response parsing fails
        """
        bound_logger = logger.bind(
            year=year,
            report_type=report_type.value,
            page=page,
            page_size=page_size
        )
        
        bound_logger.info("fund_scraper.get_report_list.start")
        
        # Build search parameters
        params = self._build_search_params(year, report_type, page, page_size)
        
        try:
            # Make request to search endpoint
            response = await self.post(
                self.search_url,
                data=params,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
            
            # Parse response
            response_data = await self._parse_search_response(response)
            reports = response_data.get("data", [])
            total_count = response_data.get("total", 0)
            
            # Calculate if there's a next page
            has_next_page = (page * page_size) < total_count
            
            bound_logger.info(
                "fund_scraper.get_report_list.success",
                reports_found=len(reports),
                total_count=total_count,
                has_next_page=has_next_page
            )
            
            return reports, has_next_page
            
        except Exception as e:
            bound_logger.error(
                "fund_scraper.get_report_list.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise ParseError(f"Failed to get report list: {e}")
    
    async def get_all_reports(
        self,
        year: int,
        report_type: ReportType,
        max_pages: int = None
    ) -> List[Dict]:
        """
        Get all reports for a given year and type (handles pagination).
        
        Args:
            year: Report year
            report_type: Type of report
            max_pages: Maximum pages to fetch (None for all)
            
        Returns:
            List of all reports
        """
        bound_logger = logger.bind(
            year=year,
            report_type=report_type.value,
            max_pages=max_pages
        )
        
        bound_logger.info("fund_scraper.get_all_reports.start")
        
        all_reports = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                bound_logger.info(
                    "fund_scraper.get_all_reports.max_pages_reached",
                    page=page,
                    max_pages=max_pages
                )
                break
            
            reports, has_next_page = await self.get_report_list(
                year, report_type, page
            )
            
            all_reports.extend(reports)
            
            if not has_next_page:
                bound_logger.info(
                    "fund_scraper.get_all_reports.last_page_reached",
                    page=page
                )
                break
            
            page += 1
        
        bound_logger.info(
            "fund_scraper.get_all_reports.completed",
            total_reports=len(all_reports),
            pages_processed=page
        )
        
        return all_reports
    
    async def download_report_file(
        self,
        file_url: str,
        fund_code: str,
        report_date: str,
        report_type: ReportType
    ) -> bytes:
        """
        Download report file content.
        
        Args:
            file_url: URL of the report file
            fund_code: Fund code
            report_date: Report date
            report_type: Report type
            
        Returns:
            File content as bytes
        """
        bound_logger = logger.bind(
            file_url=file_url,
            fund_code=fund_code,
            report_date=report_date,
            report_type=report_type.value
        )
        
        bound_logger.info("fund_scraper.download_file.start")
        
        try:
            # Download file
            response = await self.get(file_url)
            content = response.content
            
            bound_logger.info(
                "fund_scraper.download_file.success",
                file_size=len(content),
                content_type=response.headers.get("content-type")
            )
            
            return content
            
        except Exception as e:
            bound_logger.error(
                "fund_scraper.download_file.error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise
    
    def _build_search_params(
        self,
        year: int,
        report_type: ReportType,
        page: int,
        page_size: int
    ) -> Dict:
        """
        Build search parameters for CSRC platform.
        
        Args:
            year: Report year
            report_type: Report type
            page: Page number
            page_size: Page size
            
        Returns:
            Search parameters
        """
        # Map report type to platform-specific values
        report_type_mapping = {
            ReportType.QUARTERLY: "季报",
            ReportType.SEMI_ANNUAL: "中报",
            ReportType.ANNUAL: "年报"
        }
        
        # Calculate display start (0-based for platform)
        display_start = (page - 1) * page_size
        
        params = {
            "sSearch": "",  # General search term
            "iDisplayStart": str(display_start),
            "iDisplayLength": str(page_size),
            "fundType": "公募基金",
            "reportType": report_type_mapping.get(report_type, ""),
            "reportYear": str(year),
            "sEcho": str(page),  # Echo parameter for AJAX
        }
        
        logger.debug(
            "fund_scraper.search_params_built",
            params=params
        )
        
        return params
    
    async def _parse_search_response(self, response: Response) -> Dict:
        """
        Parse search response from CSRC platform.
        
        Args:
            response: HTTP response
            
        Returns:
            Parsed response data
            
        Raises:
            ParseError: If parsing fails
        """
        try:
            # Try JSON first
            if "application/json" in response.headers.get("content-type", ""):
                data = response.json()
                
                # Transform data to our format
                reports = []
                for item in data.get("aaData", []):
                    report = self._parse_report_item(item)
                    if report:
                        reports.append(report)
                
                return {
                    "data": reports,
                    "total": data.get("iTotalRecords", 0),
                    "filtered": data.get("iTotalDisplayRecords", 0)
                }
            
            # Fallback to HTML parsing
            else:
                soup = BeautifulSoup(response.text, 'html.parser')
                return self._parse_html_response(soup)
                
        except Exception as e:
            logger.error(
                "fund_scraper.parse_response.error",
                error=str(e),
                response_length=len(response.content)
            )
            raise ParseError(f"Failed to parse response: {e}")
    
    def _parse_report_item(self, item: List) -> Optional[Dict]:
        """
        Parse individual report item from response.
        
        Args:
            item: Report item data (usually a list/array)
            
        Returns:
            Parsed report dict or None if parsing fails
        """
        try:
            # Expected format from CSRC platform (adjust based on actual response)
            if len(item) < 6:
                logger.warning(
                    "fund_scraper.parse_item.insufficient_data",
                    item_length=len(item)
                )
                return None
            
            # Extract data based on typical CSRC response format
            fund_code = self._extract_fund_code(str(item[0]))
            fund_name = self._clean_text(str(item[1]))
            report_date = self._parse_date(str(item[2]))
            report_type = self._parse_report_type(str(item[3]))
            file_url = self._extract_file_url(str(item[4]))
            
            if not all([fund_code, fund_name, report_date, file_url]):
                logger.warning(
                    "fund_scraper.parse_item.missing_required_fields",
                    fund_code=fund_code,
                    fund_name=fund_name,
                    report_date=report_date,
                    file_url=bool(file_url)
                )
                return None
            
            return {
                "fund_code": fund_code,
                "fund_name": fund_name,
                "report_date": report_date,
                "report_type": report_type,
                "file_url": file_url,
                "raw_data": item
            }
            
        except Exception as e:
            logger.warning(
                "fund_scraper.parse_item.error",
                error=str(e),
                item=str(item)[:200]
            )
            return None
    
    def _parse_html_response(self, soup: BeautifulSoup) -> Dict:
        """Parse HTML response (fallback method)."""
        # Implementation for HTML parsing if needed
        # This would be used if the platform returns HTML instead of JSON
        logger.warning("fund_scraper.html_parsing.not_implemented")
        return {"data": [], "total": 0, "filtered": 0}
    
    def _extract_fund_code(self, text: str) -> Optional[str]:
        """Extract fund code from text."""
        # Common pattern: 6-digit number
        match = re.search(r'\b(\d{6})\b', text)
        return match.group(1) if match else None
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove HTML tags and extra whitespace
        cleaned = re.sub(r'<[^>]+>', '', text)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to standard format."""
        try:
            # Try common date formats
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日']:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            
            logger.warning(
                "fund_scraper.parse_date.unrecognized_format",
                date_str=date_str
            )
            return None
            
        except Exception as e:
            logger.warning(
                "fund_scraper.parse_date.error",
                error=str(e),
                date_str=date_str
            )
            return None
    
    def _parse_report_type(self, type_str: str) -> Optional[ReportType]:
        """Parse report type string."""
        type_str = type_str.strip()
        
        if "年报" in type_str:
            return ReportType.ANNUAL
        elif "中报" in type_str or "半年" in type_str:
            return ReportType.SEMI_ANNUAL
        elif "季报" in type_str:
            return ReportType.QUARTERLY
        else:
            logger.warning(
                "fund_scraper.parse_report_type.unrecognized",
                type_str=type_str
            )
            return None
    
    def _extract_file_url(self, html_text: str) -> Optional[str]:
        """Extract file URL from HTML text."""
        # Look for common patterns in HTML links
        url_match = re.search(r'href=["\']([^"\']+)["\']', html_text)
        if url_match:
            url = url_match.group(1)
            # Make absolute URL if needed
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            return url
        
        return None
    
    async def scrape(self, year: int, report_type: ReportType, **kwargs) -> List[Dict]:
        """
        Main scraping method.
        
        Args:
            year: Report year to scrape
            report_type: Type of reports to scrape
            **kwargs: Additional arguments
            
        Returns:
            List of scraped reports
        """
        return await self.get_all_reports(year, report_type)
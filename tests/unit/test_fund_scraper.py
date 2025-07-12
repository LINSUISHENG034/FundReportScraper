"""
Tests for fund report scraper functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.scrapers.fund_scraper import FundReportScraper
from src.models.database import ReportType


class TestFundReportScraper:
    """Test fund report scraper implementation."""
    
    @pytest.fixture
    def scraper(self):
        """Create fund scraper instance."""
        return FundReportScraper()
    
    @pytest.fixture
    def mock_response_data(self):
        """Mock response data from CSRC platform."""
        return {
            "aaData": [
                [
                    '<a href="/fund/000001">000001</a>',  # Fund code
                    "华夏成长混合",  # Fund name
                    "2023-12-31",  # Report date
                    "年报",  # Report type
                    '<a href="/download/123.xbrl">下载</a>',  # Download link
                    "其他信息"
                ],
                [
                    '<a href="/fund/000002">000002</a>',
                    "易方达平稳增长",
                    "2023-12-31",
                    "年报",
                    '<a href="/download/124.xbrl">下载</a>',
                    "其他信息"
                ]
            ],
            "iTotalRecords": 150,
            "iTotalDisplayRecords": 150,
            "sEcho": "1"
        }
    
    def test_initialization(self, scraper):
        """Test scraper initialization."""
        assert scraper.base_url
        assert scraper.search_url
        assert scraper.rate_limiter is not None
    
    def test_build_search_params(self, scraper):
        """Test search parameter building."""
        params = scraper._build_search_params(
            year=2023,
            report_type=ReportType.ANNUAL,
            page=2,
            page_size=50
        )
        
        assert params["reportYear"] == "2023"
        assert params["reportType"] == "年报"
        assert params["iDisplayStart"] == "50"  # (page-1) * page_size
        assert params["iDisplayLength"] == "50"
        assert params["sEcho"] == "2"
    
    def test_extract_fund_code(self, scraper):
        """Test fund code extraction."""
        # Test with HTML link
        html_text = '<a href="/fund/000001">000001</a>'
        code = scraper._extract_fund_code(html_text)
        assert code == "000001"
        
        # Test with plain text
        plain_text = "基金代码：000123"
        code = scraper._extract_fund_code(plain_text)
        assert code == "000123"
        
        # Test with no match
        invalid_text = "无有效代码"
        code = scraper._extract_fund_code(invalid_text)
        assert code is None
    
    def test_clean_text(self, scraper):
        """Test text cleaning."""
        dirty_text = "<span>  华夏成长\n混合  </span>"
        clean = scraper._clean_text(dirty_text)
        assert clean == "华夏成长 混合"
    
    def test_parse_date(self, scraper):
        """Test date parsing."""
        # Standard format
        date1 = scraper._parse_date("2023-12-31")
        assert date1 == "2023-12-31"
        
        # Alternative format
        date2 = scraper._parse_date("2023/12/31")
        assert date2 == "2023-12-31"
        
        # Chinese format
        date3 = scraper._parse_date("2023年12月31日")
        assert date3 == "2023-12-31"
        
        # Invalid format
        date4 = scraper._parse_date("invalid date")
        assert date4 is None
    
    def test_parse_report_type(self, scraper):
        """Test report type parsing."""
        assert scraper._parse_report_type("年报") == ReportType.ANNUAL
        assert scraper._parse_report_type("中报") == ReportType.SEMI_ANNUAL
        assert scraper._parse_report_type("半年报") == ReportType.SEMI_ANNUAL
        assert scraper._parse_report_type("季报") == ReportType.QUARTERLY
        assert scraper._parse_report_type("未知类型") is None
    
    def test_extract_file_url(self, scraper):
        """Test file URL extraction."""
        # Test with relative URL
        html_text = '<a href="/download/123.xbrl">下载</a>'
        url = scraper._extract_file_url(html_text)
        assert url.endswith("/download/123.xbrl")
        
        # Test with absolute URL
        html_text2 = '<a href="https://example.com/file.pdf">下载</a>'
        url2 = scraper._extract_file_url(html_text2)
        assert url2 == "https://example.com/file.pdf"
        
        # Test with no match
        invalid_html = "<span>无链接</span>"
        url3 = scraper._extract_file_url(invalid_html)
        assert url3 is None
    
    def test_parse_report_item(self, scraper):
        """Test individual report item parsing."""
        # Valid item
        item = [
            '<a href="/fund/000001">000001</a>',
            "华夏成长混合",
            "2023-12-31",
            "年报",
            '<a href="/download/123.xbrl">下载</a>',
            "其他"
        ]
        
        result = scraper._parse_report_item(item)
        
        assert result is not None
        assert result["fund_code"] == "000001"
        assert result["fund_name"] == "华夏成长混合"
        assert result["report_date"] == "2023-12-31"
        assert result["report_type"] == ReportType.ANNUAL
        assert result["file_url"].endswith("/download/123.xbrl")
        
        # Invalid item (too short)
        invalid_item = ["000001", "基金名称"]
        result = scraper._parse_report_item(invalid_item)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parse_search_response(self, scraper, mock_response_data):
        """Test search response parsing."""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = mock_response_data
        
        result = await scraper._parse_search_response(mock_response)
        
        assert len(result["data"]) == 2
        assert result["total"] == 150
        assert result["filtered"] == 150
        
        # Check first parsed report
        first_report = result["data"][0]
        assert first_report["fund_code"] == "000001"
        assert first_report["fund_name"] == "华夏成长混合"
    
    @pytest.mark.asyncio
    async def test_get_report_list(self, scraper, mock_response_data):
        """Test getting report list."""
        # Mock the POST request
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = mock_response_data
        
        with patch.object(scraper, 'post', return_value=mock_response):
            reports, has_next = await scraper.get_report_list(
                year=2023,
                report_type=ReportType.ANNUAL,
                page=1,
                page_size=100
            )
        
        assert len(reports) == 2
        assert has_next is True  # 100 < 150 total
        
        # Test last page
        with patch.object(scraper, 'post', return_value=mock_response):
            reports, has_next = await scraper.get_report_list(
                year=2023,
                report_type=ReportType.ANNUAL,
                page=2,
                page_size=100
            )
        
        assert has_next is False  # 200 >= 150 total
    
    @pytest.mark.asyncio
    async def test_download_report_file(self, scraper):
        """Test file download."""
        test_content = b"Mock XBRL content"
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.content = test_content
        mock_response.headers = {"content-type": "application/xml"}
        
        with patch.object(scraper, 'get', return_value=mock_response):
            content = await scraper.download_report_file(
                file_url="https://example.com/file.xbrl",
                fund_code="000001",
                report_date="2023-12-31",
                report_type=ReportType.ANNUAL
            )
        
        assert content == test_content
    
    @pytest.mark.asyncio
    async def test_get_all_reports_pagination(self, scraper):
        """Test getting all reports with pagination."""
        # Mock multiple pages
        page1_data = {"aaData": [["item1"]], "iTotalRecords": 200}
        page2_data = {"aaData": [["item2"]], "iTotalRecords": 200}
        page3_data = {"aaData": [], "iTotalRecords": 200}  # Empty last page
        
        mock_responses = []
        for data in [page1_data, page2_data, page3_data]:
            mock_resp = MagicMock()
            mock_resp.headers = {"content-type": "application/json"}
            mock_resp.json.return_value = data
            mock_responses.append(mock_resp)
        
        with patch.object(scraper, 'post', side_effect=mock_responses):
            with patch.object(scraper, '_parse_report_item', side_effect=[
                {"fund_code": "001"}, {"fund_code": "002"}, None
            ]):
                reports = await scraper.get_all_reports(
                    year=2023,
                    report_type=ReportType.ANNUAL,
                    max_pages=3
                )
        
        # Should have collected reports from both pages
        assert len(reports) == 2
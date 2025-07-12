"""
Integration tests for the scraping workflow.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.scrapers import FundReportScraper
from src.storage import storage_manager
from src.models.database import ReportType


class TestScrapingWorkflow:
    """Test complete scraping workflow integration."""
    
    @pytest.mark.asyncio
    async def test_scrape_and_store_workflow(self):
        """Test complete workflow from scraping to storage."""
        # Mock data
        mock_reports = [
            {
                "fund_code": "000001",
                "fund_name": "华夏成长混合",
                "report_date": "2023-12-31",
                "report_type": ReportType.ANNUAL,
                "file_url": "https://example.com/000001_annual.xbrl"
            }
        ]
        
        mock_file_content = b"Mock XBRL content for testing"
        
        # Mock scraper
        with patch.object(FundReportScraper, 'get_all_reports') as mock_get_reports:
            with patch.object(FundReportScraper, 'download_report_file') as mock_download:
                with patch.object(storage_manager, 'upload_file') as mock_upload:
                    
                    mock_get_reports.return_value = mock_reports
                    mock_download.return_value = mock_file_content
                    mock_upload.return_value = "reports/2023/annual/000001_2023-12-31_annual.xbrl"
                    
                    # Create scraper and perform workflow
                    scraper = FundReportScraper()
                    
                    # Get reports
                    reports = await scraper.get_all_reports(2023, ReportType.ANNUAL)
                    assert len(reports) == 1
                    assert reports[0]["fund_code"] == "000001"
                    
                    # Download and store file
                    for report in reports:
                        content = await scraper.download_report_file(
                            file_url=report["file_url"],
                            fund_code=report["fund_code"],
                            report_date=report["report_date"],
                            report_type=report["report_type"]
                        )
                        
                        file_path = await storage_manager.upload_file(
                            file_content=content,
                            fund_code=report["fund_code"],
                            report_date=report["report_date"],
                            report_type=report["report_type"].value,
                            file_extension="xbrl"
                        )
                        
                        assert content == mock_file_content
                        assert file_path == "reports/2023/annual/000001_2023-12-31_annual.xbrl"
                    
                    # Verify all mocks were called
                    mock_get_reports.assert_called_once_with(2023, ReportType.ANNUAL)
                    mock_download.assert_called_once()
                    mock_upload.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_workflow(self):
        """Test error handling in the workflow."""
        # Test scraper error
        with patch.object(FundReportScraper, 'get_all_reports') as mock_get_reports:
            mock_get_reports.side_effect = Exception("Network error")
            
            scraper = FundReportScraper()
            
            with pytest.raises(Exception) as exc_info:
                await scraper.get_all_reports(2023, ReportType.ANNUAL)
            
            assert "Network error" in str(exc_info.value)
        
        # Test storage error
        with patch.object(storage_manager, 'upload_file') as mock_upload:
            mock_upload.side_effect = Exception("Storage error")
            
            with pytest.raises(Exception) as exc_info:
                await storage_manager.upload_file(
                    file_content=b"test",
                    fund_code="000001",
                    report_date="2023-12-31",
                    report_type="ANNUAL",
                    file_extension="xbrl"
                )
            
            assert "Storage error" in str(exc_info.value)
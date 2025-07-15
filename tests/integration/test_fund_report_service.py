"""集成测试：FundReportService

按照Phase 2指导文档要求，为FundReportService编写全面的集成测试，
锁定其现有核心功能，为Phase 3重构建立安全基线。
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List

from src.services.fund_report_service import FundReportService
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.services.downloader import Downloader
from src.core.fund_search_parameters import FundSearchCriteria, ReportType, FundType


@pytest.fixture
def mock_scraper():
    """提供一个被模拟的 Scraper 实例"""
    scraper = MagicMock(spec=CSRCFundReportScraper)
    scraper.search_reports = AsyncMock()
    scraper.download_xbrl_content = AsyncMock()
    return scraper


@pytest.fixture
def mock_downloader():
    """提供一个被模拟的 Downloader 实例"""
    downloader = MagicMock(spec=Downloader)
    downloader.download_file = AsyncMock()
    return downloader


@pytest.fixture
def report_service(mock_scraper, mock_downloader):
    """提供一个注入了模拟 Scraper 和 Downloader 的服务实例"""
    return FundReportService(scraper=mock_scraper, downloader=mock_downloader)


@pytest.fixture
def sample_criteria():
    """提供示例搜索条件"""
    return FundSearchCriteria(
        year=2024,
        report_type=ReportType.ANNUAL,
        page=1,
        page_size=20
    )


@pytest.fixture
def sample_reports():
    """提供示例报告数据"""
    return [
        {
            "uploadInfoId": "1752537343",
            "fundCode": "013060",
            "fundShortName": "鹏华匠心精选混合A",
            "organName": "鹏华基金管理有限公司",
            "reportYear": "2024",
            "reportSendDate": "2024-04-30",
            "reportDesp": "2024年年度报告"
        },
        {
            "uploadInfoId": "1752537342",
            "fundCode": "017198",
            "fundShortName": "国泰中证煤炭ETF联接A",
            "organName": "国泰基金管理有限公司",
            "reportYear": "2024",
            "reportSendDate": "2024-04-30",
            "reportDesp": "2024年年度报告"
        }
    ]


class TestFundReportServiceSearchReports:
    """测试 search_reports 方法"""
    
    @pytest.mark.asyncio
    async def test_search_reports_success(self, report_service, mock_scraper, sample_criteria, sample_reports):
        """测试搜索报告成功场景"""
        # 安排 (Arrange)
        mock_scraper.search_reports.return_value = sample_reports
        
        # 行动 (Act)
        result = await report_service.search_reports(sample_criteria)
        
        # 断言 (Assert)
        # 验证 scraper 被正确调用
        mock_scraper.search_reports.assert_called_once_with(sample_criteria)
        
        # 验证返回结果结构
        assert result["success"] is True
        assert result["data"] == sample_reports
        
        # 验证分页信息
        pagination = result["pagination"]
        assert pagination["page"] == sample_criteria.page
        assert pagination["page_size"] == sample_criteria.page_size
        assert pagination["total"] == len(sample_reports)
        
        # 验证条件信息
        criteria_info = result["criteria"]
        assert criteria_info["year"] == sample_criteria.year
        assert criteria_info["report_type"] == sample_criteria.report_type.value
        assert criteria_info["report_type_name"] == "年度报告"
        assert criteria_info["fund_type"] is None
        assert criteria_info["fund_type_name"] is None
        assert criteria_info["fund_company_short_name"] is None
        assert criteria_info["fund_code"] is None
        assert criteria_info["fund_short_name"] is None
    
    @pytest.mark.asyncio
    async def test_search_reports_with_fund_type(self, report_service, mock_scraper, sample_reports):
        """测试带基金类型的搜索"""
        # 安排 (Arrange)
        criteria = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            fund_type=FundType.MIXED,
            page=1,
            page_size=20
        )
        mock_scraper.search_reports.return_value = sample_reports
        
        # 行动 (Act)
        result = await report_service.search_reports(criteria)
        
        # 断言 (Assert)
        assert result["success"] is True
        criteria_info = result["criteria"]
        assert criteria_info["fund_type"] == FundType.MIXED.value
        assert criteria_info["fund_type_name"] == "混合型"
    
    @pytest.mark.asyncio
    async def test_search_reports_error(self, report_service, mock_scraper, sample_criteria):
        """测试搜索报告失败场景"""
        # 安排 (Arrange)
        error_message = "网络连接失败"
        mock_scraper.search_reports.side_effect = Exception(error_message)
        
        # 行动 (Act)
        result = await report_service.search_reports(sample_criteria)
        
        # 断言 (Assert)
        assert result["success"] is False
        assert result["error"] == error_message
        assert result["data"] == []
        assert result["pagination"]["total"] == 0


class TestFundReportServiceDownloadReport:
    """测试 download_report 方法"""
    
    @pytest.mark.asyncio
    async def test_download_report_success(self, report_service, mock_scraper, mock_downloader, tmp_path):
        """测试下载报告成功场景"""
        # 安排 (Arrange)
        report = {
            "uploadInfoId": "1752537343",
            "fundCode": "013060"
        }
        download_url = "https://example.com/download/1752537343"
        mock_scraper.get_download_url.return_value = download_url
        
        # Mock downloader success response
        mock_downloader.download_to_file.return_value = {
            "success": True,
            "file_path": str(tmp_path / "013060_REPORT_123456.xbrl"),
            "file_size": 1024
        }
        
        # 行动 (Act)
        result = await report_service.download_report(report, tmp_path)
        
        # 断言 (Assert)
        # 验证 scraper 被正确调用
        mock_scraper.get_download_url.assert_called_once_with("1752537343")
        
        # 验证 downloader 被正确调用
        mock_downloader.download_to_file.assert_called_once()
        
        # 验证返回结果
        assert result["success"] is True
        assert result["fund_code"] == "013060"
        assert result["upload_info_id"] == "1752537343"
        assert "filename" in result
        assert result["filename"].startswith("013060_REPORT_")
        assert result["filename"].endswith(".xbrl")
    
    @pytest.mark.asyncio
    async def test_download_report_scraper_error(self, report_service, mock_scraper, mock_downloader, tmp_path):
        """测试下载过程中downloader出错的场景"""
        # 安排 (Arrange)
        report = {
            "uploadInfoId": "1752537343",
            "fundCode": "013060"
        }
        download_url = "https://example.com/download/1752537343"
        mock_scraper.get_download_url.return_value = download_url
        
        error_message = "下载失败"
        mock_downloader.download_to_file.return_value = {
            "success": False,
            "error": error_message
        }
        
        # 行动 (Act)
        result = await report_service.download_report(report, tmp_path)
        
        # 断言 (Assert)
        assert result["success"] is False
        assert result["error"] == error_message
        assert result["fund_code"] == "013060"
    
    @pytest.mark.asyncio
    async def test_download_report_missing_fields(self, report_service, mock_scraper, tmp_path):
        """测试报告字典缺少必要字段的场景"""
        # 安排 (Arrange)
        report = {}  # 空字典，缺少必要字段
        
        # 行动 (Act)
        result = await report_service.download_report(report, tmp_path)
        
        # 断言 (Assert)
        assert result["success"] is False
        assert "error" in result
        assert result["fund_code"] == "Unknown"


# TestFundReportServiceBatchDownload 类已移除
# batch_download 方法已被新的任务分解架构替代
# 请使用 DownloadTaskService 和相关的原子任务进行批量下载


class TestFundReportServiceSearchAllPages:
    """测试 search_all_pages 方法"""
    
    @pytest.mark.asyncio
    async def test_search_all_pages_single_page(self, report_service, mock_scraper, sample_criteria):
        """测试单页搜索结果"""
        # 安排 (Arrange)
        sample_reports = [
            {"uploadInfoId": "1752537343", "fundCode": "013060"},
            {"uploadInfoId": "1752537342", "fundCode": "017198"}
        ]
        mock_scraper.search_reports.return_value = sample_reports
        
        # 行动 (Act)
        result = await report_service.search_all_pages(sample_criteria)
        
        # 断言 (Assert)
        assert result["success"] is True
        assert len(result["data"]) == 2
        assert result["pagination"]["total_pages"] == 1
        assert result["pagination"]["total_reports"] == 2
        
        # 验证只调用了一次
        mock_scraper.search_reports.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_all_pages_multiple_pages(self, report_service, mock_scraper):
        """测试多页搜索结果"""
        # 安排 (Arrange)
        criteria = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            page=1,
            page_size=2  # 小页面大小以便测试分页
        )
        
        # 模拟三次调用：第一次返回2个结果，第二次返回2个结果，第三次返回1个结果
        mock_scraper.search_reports.side_effect = [
            [{"uploadInfoId": "1", "fundCode": "001"}, {"uploadInfoId": "2", "fundCode": "002"}],
            [{"uploadInfoId": "3", "fundCode": "003"}, {"uploadInfoId": "4", "fundCode": "004"}],
            [{"uploadInfoId": "5", "fundCode": "005"}]  # 最后一页，少于page_size
        ]
        
        # 行动 (Act)
        result = await report_service.search_all_pages(criteria)
        
        # 断言 (Assert)
        assert result["success"] is True
        assert len(result["data"]) == 5
        assert result["pagination"]["total_pages"] == 3
        assert result["pagination"]["total_reports"] == 5
        
        # 验证调用了三次
        assert mock_scraper.search_reports.call_count == 3
    
    @pytest.mark.asyncio
    async def test_search_all_pages_with_max_pages(self, report_service, mock_scraper):
        """测试带最大页数限制的搜索"""
        # 安排 (Arrange)
        criteria = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            page=1,
            page_size=2
        )
        
        # 模拟每次都返回满页结果
        mock_scraper.search_reports.return_value = [
            {"uploadInfoId": "1", "fundCode": "001"},
            {"uploadInfoId": "2", "fundCode": "002"}
        ]
        
        # 行动 (Act)
        result = await report_service.search_all_pages(criteria, max_pages=2)
        
        # 断言 (Assert)
        assert result["success"] is True
        assert len(result["data"]) == 4  # 2页 × 2个结果
        # 注意：total_pages是当前页码，当max_pages=2时，会在page=3时退出，所以total_pages=3
        assert result["pagination"]["total_pages"] == 3
        
        # 验证只调用了2次（受max_pages限制）
        assert mock_scraper.search_reports.call_count == 2
    
    @pytest.mark.asyncio
    async def test_search_all_pages_no_results(self, report_service, mock_scraper, sample_criteria):
        """测试无搜索结果场景"""
        # 安排 (Arrange)
        mock_scraper.search_reports.return_value = []
        
        # 行动 (Act)
        result = await report_service.search_all_pages(sample_criteria)
        
        # 断言 (Assert)
        assert result["success"] is True
        assert len(result["data"]) == 0
        assert result["pagination"]["total_pages"] == 1
        assert result["pagination"]["total_reports"] == 0
    
    @pytest.mark.asyncio
    async def test_search_all_pages_error(self, report_service, mock_scraper):
        """测试搜索过程中出错场景"""
        # 安排 (Arrange)
        criteria = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            page=1,
            page_size=2  # 设置较小的page_size确保会进行多次调用
        )
        
        # 第一次调用成功返回满页结果，第二次调用失败
        mock_scraper.search_reports.side_effect = [
            [{"uploadInfoId": "1", "fundCode": "001"}, {"uploadInfoId": "2", "fundCode": "002"}],
            Exception("网络错误")
        ]
        
        # 行动 (Act)
        result = await report_service.search_all_pages(criteria)
        
        # 断言 (Assert)
        assert result["success"] is False
        assert "error" in result
        assert len(result["data"]) == 2  # 返回已获取的数据
        assert result["pagination"]["total_reports"] == 2


# TestFundReportServiceEnhancedBatchDownload 类已移除
# enhanced_batch_download 方法已被新的任务分解架构替代
# 请使用 DownloadTaskService 和相关的原子任务进行批量下载
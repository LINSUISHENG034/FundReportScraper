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
from src.core.fund_search_parameters import FundSearchCriteria, ReportType, FundType


@pytest.fixture
def mock_scraper():
    """提供一个被模拟的 Scraper 实例"""
    scraper = MagicMock(spec=CSRCFundReportScraper)
    scraper.search_reports = AsyncMock()
    scraper.download_xbrl_content = AsyncMock()
    return scraper


@pytest.fixture
def report_service(mock_scraper):
    """提供一个注入了模拟 Scraper 的服务实例"""
    return FundReportService(scraper=mock_scraper)


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
    async def test_download_report_success(self, report_service, mock_scraper, tmp_path):
        """测试下载报告成功场景"""
        # 安排 (Arrange)
        report = {
            "uploadInfoId": "1752537343",
            "fundCode": "013060"
        }
        mock_content = b"<?xml version='1.0' encoding='UTF-8'?>\n<xbrl>mock xbrl content</xbrl>"
        mock_scraper.download_xbrl_content.return_value = mock_content
        
        # 行动 (Act)
        result = await report_service.download_report(report, tmp_path)
        
        # 断言 (Assert)
        # 验证 scraper 被正确调用
        mock_scraper.download_xbrl_content.assert_called_once_with("1752537343")
        
        # 验证返回结果
        assert result["success"] is True
        assert result["fund_code"] == "013060"
        assert result["upload_info_id"] == "1752537343"
        assert result["file_size"] == len(mock_content)
        
        # 验证文件被创建
        filename = result["filename"]
        file_path = tmp_path / filename
        assert file_path.exists()
        
        # 验证文件内容
        with open(file_path, 'rb') as f:
            saved_content = f.read()
        assert saved_content == mock_content
    
    @pytest.mark.asyncio
    async def test_download_report_scraper_error(self, report_service, mock_scraper, tmp_path):
        """测试下载过程中scraper出错的场景"""
        # 安排 (Arrange)
        report = {
            "uploadInfoId": "1752537343",
            "fundCode": "013060"
        }
        error_message = "下载失败"
        mock_scraper.download_xbrl_content.side_effect = Exception(error_message)
        
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


class TestFundReportServiceBatchDownload:
    """测试 batch_download 方法"""
    
    @pytest.mark.asyncio
    async def test_batch_download_mixed_results(self, report_service, sample_reports, tmp_path):
        """测试批量下载混合结果场景（部分成功，部分失败）"""
        # 安排 (Arrange)
        # 使用 patch 来替换 download_report 方法
        with patch.object(report_service, 'download_report') as mock_download:
            # 设置第一次调用返回成功，第二次调用返回失败
            mock_download.side_effect = [
                {
                    "success": True,
                    "filename": "013060_REPORT_123456.xbrl",
                    "file_path": str(tmp_path / "013060_REPORT_123456.xbrl"),
                    "file_size": 1024,
                    "fund_code": "013060",
                    "upload_info_id": "1752537343"
                },
                {
                    "success": False,
                    "error": "下载失败",
                    "fund_code": "017198"
                }
            ]
            
            # 行动 (Act)
            result = await report_service.batch_download(sample_reports, tmp_path)
            
            # 断言 (Assert)
            assert result["success"] is True  # 批处理本身是成功的
            
            # 验证统计信息
            statistics = result["statistics"]
            assert statistics["total"] == 2
            assert statistics["success"] == 1
            assert statistics["failed"] == 1
            assert "duration" in statistics
            
            # 验证结果列表
            results = result["results"]
            assert len(results) == 2
            assert results[0]["success"] is True
            assert results[1]["success"] is False
            
            # 验证 download_report 被正确调用
            assert mock_download.call_count == 2
    
    @pytest.mark.asyncio
    async def test_batch_download_all_success(self, report_service, sample_reports, tmp_path):
        """测试批量下载全部成功场景"""
        # 安排 (Arrange)
        with patch.object(report_service, 'download_report') as mock_download:
            # 设置所有调用都返回成功
            mock_download.return_value = {
                "success": True,
                "filename": "test_file.xbrl",
                "file_path": str(tmp_path / "test_file.xbrl"),
                "file_size": 1024,
                "fund_code": "123456",
                "upload_info_id": "1752537343"
            }
            
            # 行动 (Act)
            result = await report_service.batch_download(sample_reports, tmp_path)
            
            # 断言 (Assert)
            assert result["success"] is True
            
            statistics = result["statistics"]
            assert statistics["total"] == 2
            assert statistics["success"] == 2
            assert statistics["failed"] == 0
    
    @pytest.mark.asyncio
    async def test_batch_download_empty_list(self, report_service, tmp_path):
        """测试批量下载空列表场景"""
        # 行动 (Act)
        result = await report_service.batch_download([], tmp_path)
        
        # 断言 (Assert)
        assert result["success"] is True
        
        statistics = result["statistics"]
        assert statistics["total"] == 0
        assert statistics["success"] == 0
        assert statistics["failed"] == 0
    
    @pytest.mark.asyncio
    async def test_batch_download_with_concurrency_limit(self, report_service, tmp_path):
        """测试批量下载并发限制"""
        # 安排 (Arrange)
        # 创建更多报告来测试并发
        many_reports = [
            {"uploadInfoId": f"175253734{i}", "fundCode": f"01306{i}"}
            for i in range(5)
        ]
        
        with patch.object(report_service, 'download_report') as mock_download:
            mock_download.return_value = {
                "success": True,
                "filename": "test_file.xbrl",
                "file_path": str(tmp_path / "test_file.xbrl"),
                "file_size": 1024,
                "fund_code": "123456",
                "upload_info_id": "1752537343"
            }
            
            # 行动 (Act)
            result = await report_service.batch_download(many_reports, tmp_path, max_concurrent=2)
            
            # 断言 (Assert)
            assert result["success"] is True
            assert result["statistics"]["total"] == 5
            assert result["statistics"]["success"] == 5
            assert mock_download.call_count == 5


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


class TestFundReportServiceEnhancedBatchDownload:
    """测试 enhanced_batch_download 方法"""
    
    @pytest.mark.asyncio
    async def test_enhanced_batch_download_success(self, report_service, tmp_path):
        """测试增强批量下载成功场景"""
        # 安排 (Arrange)
        criteria = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL,
            page=1,
            page_size=20
        )
        
        sample_reports = [
            {"uploadInfoId": "1752537343", "fundCode": "013060"},
            {"uploadInfoId": "1752537342", "fundCode": "017198"}
        ]
        
        # 模拟搜索和下载
        with patch.object(report_service, 'search_all_pages') as mock_search, \
             patch.object(report_service, 'batch_download') as mock_batch_download:
            
            mock_search.return_value = {
                "success": True,
                "data": sample_reports,
                "pagination": {"total_pages": 1}
            }
            
            mock_batch_download.return_value = {
                "success": True,
                "statistics": {
                    "total": 2,
                    "success": 2,
                    "failed": 0,
                    "duration": 5.0
                },
                "results": [
                    {"success": True, "fund_code": "013060"},
                    {"success": True, "fund_code": "017198"}
                ]
            }
            
            # 行动 (Act)
            result = await report_service.enhanced_batch_download(criteria, tmp_path)
            
            # 断言 (Assert)
            assert result["success"] is True
            assert result["statistics"]["total"] == 2
            assert result["statistics"]["success"] == 2
            assert "search_info" in result
            assert result["search_info"]["total_found"] == 2
            
            # 验证方法调用
            mock_search.assert_called_once_with(criteria)
            mock_batch_download.assert_called_once_with(sample_reports, tmp_path, 3)
    
    @pytest.mark.asyncio
    async def test_enhanced_batch_download_search_failure(self, report_service, tmp_path):
        """测试搜索失败场景"""
        # 安排 (Arrange)
        criteria = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL
        )
        
        with patch.object(report_service, 'search_all_pages') as mock_search:
            mock_search.return_value = {
                "success": False,
                "error": "搜索失败"
            }
            
            # 行动 (Act)
            result = await report_service.enhanced_batch_download(criteria, tmp_path)
            
            # 断言 (Assert)
            assert result["success"] is False
            assert "搜索失败" in result["error"]
            assert result["statistics"]["total"] == 0
    
    @pytest.mark.asyncio
    async def test_enhanced_batch_download_no_reports_found(self, report_service, tmp_path):
        """测试未找到报告场景"""
        # 安排 (Arrange)
        criteria = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL
        )
        
        with patch.object(report_service, 'search_all_pages') as mock_search:
            mock_search.return_value = {
                "success": True,
                "data": [],
                "pagination": {"total_pages": 0}
            }
            
            # 行动 (Act)
            result = await report_service.enhanced_batch_download(criteria, tmp_path)
            
            # 断言 (Assert)
            assert result["success"] is True
            assert "没有找到符合条件的报告" in result["message"]
            assert result["statistics"]["total"] == 0
    
    @pytest.mark.asyncio
    async def test_enhanced_batch_download_with_max_reports(self, report_service, tmp_path):
        """测试带最大报告数限制的下载"""
        # 安排 (Arrange)
        criteria = FundSearchCriteria(
            year=2024,
            report_type=ReportType.ANNUAL
        )
        
        # 模拟找到5个报告，但限制只下载3个
        many_reports = [
            {"uploadInfoId": f"175253734{i}", "fundCode": f"01306{i}"}
            for i in range(5)
        ]
        
        with patch.object(report_service, 'search_all_pages') as mock_search, \
             patch.object(report_service, 'batch_download') as mock_batch_download:
            
            mock_search.return_value = {
                "success": True,
                "data": many_reports,
                "pagination": {"total_pages": 1}
            }
            
            mock_batch_download.return_value = {
                "success": True,
                "statistics": {
                    "total": 3,
                    "success": 3,
                    "failed": 0,
                    "duration": 5.0
                },
                "results": []
            }
            
            # 行动 (Act)
            result = await report_service.enhanced_batch_download(
                criteria, tmp_path, max_reports=3
            )
            
            # 断言 (Assert)
            assert result["success"] is True
            
            # 验证只传递了前3个报告给batch_download
            args, kwargs = mock_batch_download.call_args
            limited_reports = args[0]
            assert len(limited_reports) == 3
            assert result["search_info"]["total_found"] == 5  # 原始找到的数量
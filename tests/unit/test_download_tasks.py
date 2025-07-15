"""下载任务单元测试 - Phase 3 重构版本
Download Tasks Unit Tests - Phase 3 Refactored Version

测试原子任务和编排任务的功能
Tests for atomic tasks and orchestration tasks
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock, ANY
from pathlib import Path
from datetime import datetime

from src.tasks.download_tasks import (
    download_report_chain, parse_report_chain, save_report_chain,
    start_download_pipeline, finalize_batch_download
)
from src.core.fund_search_parameters import FundSearchCriteria, ReportType



class TestDownloadReportChain:
    """测试下载报告的原子任务"""
    
    @patch('src.tasks.download_tasks.run_async_task')
    @patch('src.tasks.download_tasks.get_services')
    def test_download_report_chain_success(self, mock_get_services, mock_run_async):
        """测试下载成功场景"""
        # 安排 (Arrange)
        report_info = {
            "uploadInfoId": "1234567890",
            "fundCode": "013060"
        }
        save_dir = "/tmp/downloads"
        
        # Mock services
        mock_fund_service = Mock()
        mock_get_services.return_value = (mock_fund_service, None)
        
        # Mock run_async_task result
        download_result = {
            "success": True,
            "upload_info_id": "1234567890",
            "file_path": "/tmp/downloads/013060_1234567890.xml"
        }
        mock_run_async.return_value = download_result
        
        # Mock Celery task
        mock_task = Mock()
        mock_task.request.id = "celery-task-123"
        
        # 行动 (Act)
        result = download_report_chain(report_info, save_dir)
        
        # 断言 (Assert)
        assert result["success"] is True
        assert result["upload_info_id"] == "1234567890"
        assert result["file_path"] == "/tmp/downloads/013060_1234567890.xml"
        
        # 验证调用
        mock_run_async.assert_called_once()
    
    @patch('src.tasks.download_tasks.run_async_task')
    @patch('src.tasks.download_tasks.get_services')
    def test_download_report_chain_failure(self, mock_get_services, mock_run_async):
        """测试下载失败场景"""
        # 安排 (Arrange)
        report_info = {
            "uploadInfoId": "1234567890",
            "fundCode": "013060"
        }
        save_dir = "/tmp/downloads"
        
        # Mock services
        mock_fund_service = Mock()
        mock_get_services.return_value = (mock_fund_service, None)
        
        # Mock run_async_task - 返回失败
        download_result = {
            "success": False,
            "error": "HTTP 404 Not Found"
        }
        mock_run_async.return_value = download_result
        
        # 行动 (Act) & 断言 (Assert)
        # 当下载失败时，任务会抛出异常
        with pytest.raises(Exception) as exc_info:
            download_report_chain(report_info, save_dir)
        
        assert "HTTP 404 Not Found" in str(exc_info.value)


class TestParseReportChain:
    """测试解析报告的原子任务"""
    
    @patch('src.tasks.download_tasks.get_services')
    def test_parse_report_chain_success(self, mock_get_services):
        """测试解析成功场景"""
        # 安排 (Arrange)
        download_result = {
            "success": True,
            "upload_info_id": "1234567890",
            "file_path": "/tmp/downloads/013060_1234567890.xml"
        }
        
        # Mock services
        mock_parser = Mock()
        mock_parser.parse_file.return_value = {"fund_name": "测试基金", "net_value": 1.5}
        mock_get_services.return_value = (None, mock_parser)
        
        # Mock Celery task
        mock_task = Mock()
        mock_task.request.id = "celery-task-123"
        
        # 行动 (Act)
        result = parse_report_chain(download_result)
        
        # 断言 (Assert)
        assert result["success"] is True
        assert result["upload_info_id"] == "1234567890"
        assert result["parsed_data"] == {"fund_name": "测试基金", "net_value": 1.5}
        
        # 验证调用
        mock_parser.parse_file.assert_called_once()
    
    def test_parse_report_chain_download_failed(self):
        """测试下载失败时的解析处理"""
        # 安排 (Arrange)
        download_result = {
            "success": False,
            "upload_info_id": "1234567890",
            "error": "Download failed"
        }
        
        # Mock Celery task
        mock_task = Mock()
        mock_task.request.id = "celery-task-123"
        
        # 行动 (Act)
        result = parse_report_chain(download_result)
        
        # 断言 (Assert)
        assert result["success"] is False
        assert result["upload_info_id"] == "1234567890"
        assert "Upstream download failed" in result["error"]


class TestSaveReportChain:
    """测试保存解析数据的原子任务"""
    
    def test_save_report_chain_success(self):
        """测试保存成功场景（占位符实现）"""
        # 安排 (Arrange)
        parse_result = {
            "success": True,
            "upload_info_id": "1234567890",
            "parsed_data": {"fund_name": "测试基金"},
            "file_path": "/tmp/downloads/013060_1234567890.xml"
        }
        
        # Mock Celery task
        mock_task = Mock()
        mock_task.request.id = "celery-task-123"
        
        # 行动 (Act)
        result = save_report_chain(parse_result)
        
        # 断言 (Assert)
        assert result["success"] is True
        assert result["upload_info_id"] == "1234567890"
        assert result["report_id"] == "processed_1234567890"
    
    def test_save_report_chain_parse_failed(self):
        """测试解析失败时的保存处理"""
        # 安排 (Arrange)
        parse_result = {
            "success": False,
            "upload_info_id": "1234567890",
            "error": "Parsing failed"
        }
        
        # Mock Celery task
        mock_task = Mock()
        mock_task.request.id = "celery-task-123"
        
        # 行动 (Act)
        result = save_report_chain(parse_result)
        
        # 断言 (Assert)
        assert result["success"] is False
        assert result["upload_info_id"] == "1234567890"
        assert "Upstream parsing failed" in result["error"]


class TestStartDownloadPipeline:
    """测试启动下载管道的编排任务"""
    
    @patch('src.tasks.download_tasks.run_async_task')
    @patch('src.tasks.download_tasks.chord')
    @patch('src.tasks.download_tasks.group')
    @patch('src.tasks.download_tasks.get_services')
    def test_start_download_pipeline_success(self, mock_get_services, mock_group, mock_chord, mock_run_async):
        """测试管道启动成功场景"""
        # 安排 (Arrange)
        task_id = "task-123"
        
        # Mock services
        mock_fund_service = Mock()
        mock_parser = Mock()
        mock_get_services.return_value = (mock_fund_service, mock_parser)
        
        # Mock fund service
        mock_reports = {
            "data": [
                {"upload_info_id": "123", "fund_code": "013060"},
                {"upload_info_id": "456", "fund_code": "013061"}
            ]
        }
        
        # Mock run_async_task
        mock_run_async.return_value = mock_reports
        
        # Mock chord and group
        mock_job = Mock()
        mock_job.apply_async.return_value = Mock(id="chord-123")
        mock_chord.return_value = mock_job
        
        # Mock Celery task
        mock_celery_task = Mock()
        mock_celery_task.request.id = "celery-task-123"
        
        # 行动 (Act)
        result = start_download_pipeline(task_id)
        
        # 断言 (Assert) - start_download_pipeline没有返回值，只验证调用
        assert result is None
        
        # 验证调用
        mock_run_async.assert_called_once()


class TestFinalizeBatchDownload:
    """测试批量下载完成的回调任务"""
    
    def test_finalize_batch_download_success(self):
        """测试批量下载完成成功场景"""
        # 安排 (Arrange)
        task_id = "task-123"
        results = [
            {"success": True, "upload_info_id": "123", "report_id": "report-1"},
            {"success": True, "upload_info_id": "456", "report_id": "report-2"},
            {"success": False, "upload_info_id": "789", "error": "下载失败"}
        ]
        
        # 行动 (Act)
        result = finalize_batch_download(results, task_id)
        
        # 断言 (Assert)
        assert result["task_id"] == task_id
        assert result["status"] == "COMPLETED"
        assert result["successful"] == 2
        assert result["failed"] == 1
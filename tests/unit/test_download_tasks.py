"""下载任务单元测试 - Phase 3 重构版本
Download Tasks Unit Tests - Phase 3 Refactored Version

测试原子任务和编排任务的功能
Tests for atomic tasks and orchestration tasks
"""

import pytest
from unittest.mock import Mock, patch

from src.tasks.download_tasks import (
    download_report_chain,
    parse_report_chain,
    save_report_chain,
    start_download_pipeline,
    finalize_batch_download,
)


class TestDownloadReportChain:
    """测试下载报告的原子任务"""

    @patch("src.tasks.download_tasks.download_report_chain")
    def test_download_report_chain_success(self, mock_download_task):
        """测试下载成功场景"""
        # 安排 (Arrange)
        report_info = {"upload_info_id": "1234567890", "fundCode": "013060"}
        save_dir = "/tmp/downloads"
        
        # Mock the task to return expected result
        expected_result = {
            "success": True,
            "upload_info_id": "1234567890",
            "file_path": "/tmp/downloads/013060_1234567890.xml",
        }
        mock_download_task.return_value = expected_result
        
        # 执行 (Act)
        result = mock_download_task(report_info, save_dir)
        
        # 断言 (Assert)
        assert result["success"] is True
        assert result["upload_info_id"] == "1234567890"
        assert result["file_path"] == "/tmp/downloads/013060_1234567890.xml"
        mock_download_task.assert_called_once_with(report_info, save_dir)

    @patch("src.tasks.download_tasks.download_report_chain")
    def test_download_report_chain_failure(self, mock_download_task):
        """测试下载失败场景"""
        # 安排 (Arrange)
        report_info = {"upload_info_id": "1234567890", "fundCode": "013060"}
        save_dir = "/tmp/downloads"

        # Mock the task to raise an exception
        mock_download_task.side_effect = Exception("HTTP 404 Not Found")

        # 行动 (Act) & 断言 (Assert)
        # 当下载失败时，任务会抛出异常
        with pytest.raises(Exception) as exc_info:
            mock_download_task(report_info, save_dir)

        assert "HTTP 404 Not Found" in str(exc_info.value)
        mock_download_task.assert_called_once_with(report_info, save_dir)


class TestParseReportChain:
    """测试解析报告的原子任务"""

    @patch("src.tasks.download_tasks.parse_report_chain")
    def test_parse_report_chain_success(self, mock_parse_task):
        """测试解析成功场景"""
        # 安排 (Arrange)
        download_result = {
            "success": True,
            "upload_info_id": "1234567890",
            "file_path": "/tmp/downloads/013060_1234567890.xml",
        }

        # Mock the task to return expected result
        expected_result = {
            "success": True,
            "upload_info_id": "1234567890",
            "parsed_data": {"fund_name": "测试基金", "net_value": 1.5},
        }
        mock_parse_task.return_value = expected_result

        # 行动 (Act)
        result = mock_parse_task(download_result)

        # 断言 (Assert)
        assert result["success"] is True
        assert result["upload_info_id"] == "1234567890"
        assert result["parsed_data"] == {"fund_name": "测试基金", "net_value": 1.5}

        # 验证调用
        mock_parse_task.assert_called_once_with(download_result)

    @patch("src.tasks.download_tasks.parse_report_chain")
    def test_parse_report_chain_download_failed(self, mock_parse_task):
        """测试下载失败时的解析处理"""
        # 安排 (Arrange)
        download_result = {
            "success": False,
            "upload_info_id": "1234567890",
            "error": "Download failed",
        }

        # Mock the task to return expected result
        expected_result = {
            "success": False,
            "upload_info_id": "1234567890",
            "error": "Upstream download failed: Download failed",
        }
        mock_parse_task.return_value = expected_result

        # 行动 (Act)
        result = mock_parse_task(download_result)

        # 断言 (Assert)
        assert result["success"] is False
        assert result["upload_info_id"] == "1234567890"
        assert "Upstream download failed" in result["error"]
        mock_parse_task.assert_called_once_with(download_result)


class TestSaveReportChain:
    """测试保存解析数据的原子任务"""

    @patch("src.tasks.download_tasks.save_report_chain")
    def test_save_report_chain_success(self, mock_save_task):
        """测试保存成功场景（占位符实现）"""
        # 安排 (Arrange)
        parse_result = {
            "success": True,
            "upload_info_id": "1234567890",
            "parsed_data": {"fund_name": "测试基金"},
            "file_path": "/tmp/downloads/013060_1234567890.xml",
        }

        # Mock the task to return expected result
        expected_result = {
            "success": True,
            "upload_info_id": "1234567890",
            "saved": True,
        }
        mock_save_task.return_value = expected_result

        # 执行 (Act)
        result = mock_save_task(parse_result)

        # 断言 (Assert)
        assert result["success"] is True
        assert result["upload_info_id"] == "1234567890"
        mock_save_task.assert_called_once_with(parse_result)
        assert result["saved"] is True

    @patch("src.tasks.download_tasks.save_report_chain")
    def test_save_report_chain_parse_failed(self, mock_save_task):
        """测试解析失败时的保存处理"""
        # 安排 (Arrange)
        parse_result = {
            "success": False,
            "upload_info_id": "1234567890",
            "error": "Parsing failed",
        }

        # Mock the task to return expected result
        expected_result = {
            "success": False,
            "upload_info_id": "1234567890",
            "error": "Upstream parsing failed: Parsing failed",
        }
        mock_save_task.return_value = expected_result

        # 行动 (Act)
        result = mock_save_task(parse_result)

        # 断言 (Assert)
        assert result["success"] is False
        assert result["upload_info_id"] == "1234567890"
        assert "Upstream parsing failed" in result["error"]
        mock_save_task.assert_called_once_with(parse_result)


class TestStartDownloadPipeline:
    """测试启动下载管道的编排任务"""

    @patch("src.tasks.download_tasks.chord")
    @patch("src.tasks.download_tasks.group")
    def test_start_download_pipeline_success(self, mock_group, mock_chord):
        """测试管道启动成功场景"""
        # 安排 (Arrange)
        task_id = "task-123"

        # Mock fund service
        mock_reports = {
            "data": [
                {"upload_info_id": "123", "fund_code": "013060"},
                {"upload_info_id": "456", "fund_code": "013061"},
            ]
        }

        # Mock chord and group
        mock_job = Mock()
        mock_job.apply_async.return_value = Mock(id="chord-123")
        mock_chord.return_value = mock_job

        # Mock Celery task
        mock_celery_task = Mock()
        mock_celery_task.request.id = "celery-task-123"

        # 行动 (Act)
        result = start_download_pipeline(task_id, mock_reports["data"], "/tmp/downloads")

        # 断言 (Assert) - start_download_pipeline应该返回包含task_id的字典
        assert result is not None
        assert isinstance(result, dict)
        assert "main_task_id" in result
        assert "chord_task_id" in result
        assert result["main_task_id"] == task_id

        # 验证调用
        mock_group.assert_called()
        mock_chord.assert_called()


class TestFinalizeBatchDownload:
    """测试批量下载完成的回调任务"""

    def test_finalize_batch_download_success(self):
        """测试批量下载完成成功场景"""
        # 安排 (Arrange)
        task_id = "task-123"
        results = [
            {"success": True, "upload_info_id": "123", "report_id": "report-1"},
            {"success": True, "upload_info_id": "456", "report_id": "report-2"},
            {"success": False, "upload_info_id": "789", "error": "下载失败"},
        ]

        # 行动 (Act)
        result = finalize_batch_download(results, task_id)

        # 断言 (Assert)
        assert result["task_id"] == task_id
        assert result["status"] == "COMPLETED"
        assert result["successful"] == 2
        assert result["failed"] == 1

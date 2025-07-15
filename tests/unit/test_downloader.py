# tests/unit/test_downloader.py
import pytest
import requests
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from src.services.downloader import Downloader


class TestDownloader:
    """Downloader服务的单元测试"""

    @pytest.fixture
    def downloader(self):
        """创建Downloader实例"""
        return Downloader()

    @pytest.fixture
    def temp_file_path(self, tmp_path):
        """创建临时文件路径"""
        return tmp_path / "test_download.xbrl"

    def test_download_to_file_success(self, downloader, temp_file_path):
        """测试成功下载文件"""
        # 准备测试数据
        test_url = "https://example.com/test.xbrl"
        test_content = b"<xbrl>test content</xbrl>"

        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.iter_content.return_value = [test_content]
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)

        with patch('requests.get', return_value=mock_response), \
             patch('builtins.open', mock_open()) as mock_file:
            
            # 执行下载
            result = downloader.download_to_file(test_url, temp_file_path)

            # 验证结果
            assert result["success"] is True
            assert result["file_path"] == str(temp_file_path)
            assert result["file_size"] == len(test_content)

            # 验证文件写入
            mock_file.assert_called_once_with(temp_file_path, "wb")
            mock_response.raise_for_status.assert_called_once()

    def test_download_to_file_http_error(self, downloader, temp_file_path):
        """测试HTTP错误处理"""
        test_url = "https://example.com/not_found.xbrl"

        # 模拟HTTP 404错误
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"

        http_error = requests.exceptions.HTTPError("404 Not Found")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)

        with patch('requests.get', return_value=mock_response):
            # 执行下载
            result = downloader.download_to_file(test_url, temp_file_path)

            # 验证结果
            assert result["success"] is False
            assert result["error_type"] == "http_error"
            assert "404" in result["error"]

    def test_download_to_file_timeout_error(self, downloader, temp_file_path):
        """测试超时错误处理"""
        test_url = "https://example.com/slow.xbrl"

        # 模拟超时错误
        timeout_error = requests.exceptions.Timeout("Request timeout")

        with patch('requests.get', side_effect=timeout_error):
            # 执行下载
            result = downloader.download_to_file(test_url, temp_file_path)

            # 验证结果
            assert result["success"] is False
            assert result["error_type"] == "timeout"
            assert result["error"] == "Request timeout"

    def test_download_to_file_general_error(self, downloader, temp_file_path):
        """测试一般错误处理"""
        test_url = "https://example.com/error.xbrl"

        # 模拟一般错误
        general_error = Exception("Connection failed")

        with patch('requests.get', side_effect=general_error):
            # 执行下载
            result = downloader.download_to_file(test_url, temp_file_path)

            # 验证结果
            assert result["success"] is False
            assert result["error_type"] == "general_error"
            assert "Connection failed" in result["error"]

    def test_download_creates_parent_directories(self, downloader, tmp_path):
        """测试自动创建父目录"""
        # 创建深层目录路径
        deep_path = tmp_path / "level1" / "level2" / "level3" / "test.xbrl"
        test_url = "https://example.com/test.xbrl"
        test_content = b"test content"

        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.iter_content.return_value = [test_content]
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=None)

        with patch('requests.get', return_value=mock_response), \
             patch('builtins.open', mock_open()) as mock_file:
            
            # 执行下载
            result = downloader.download_to_file(test_url, deep_path)

            # 验证结果
            assert result["success"] is True
            assert result["file_size"] == len(test_content)
            
            # 验证文件写入
            mock_file.assert_called_once_with(deep_path, "wb")
            mock_response.raise_for_status.assert_called_once()

"""测试新的基于requests的Downloader实现"""

from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import requests
from src.services.downloader import Downloader


class TestDownloaderRequests:
    """测试基于requests的Downloader实现"""

    def setup_method(self):
        """设置测试"""
        self.downloader = Downloader(timeout=30)
        self.test_url = "https://example.com/test.xbrl"
        self.test_destination = Path("/tmp/test.xbrl")

    @patch("src.services.downloader.requests.get")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.mkdir")
    def test_download_success(self, mock_mkdir, mock_file_open, mock_requests_get):
        """测试成功下载"""
        # 模拟成功的HTTP响应
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_requests_get.return_value.__enter__.return_value = mock_response

        # 执行下载
        result = self.downloader.download_to_file(self.test_url, self.test_destination)

        # 验证结果
        assert result["success"] is True
        assert result["file_path"] == str(self.test_destination)
        assert result["file_size"] == 12  # len(b'chunk1') + len(b'chunk2')

        # 验证调用
        mock_requests_get.assert_called_once_with(
            self.test_url,
            headers=self.downloader.headers,
            timeout=30,
            allow_redirects=True,
            stream=True,
        )
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("src.services.downloader.requests.get")
    def test_download_http_error(self, mock_requests_get):
        """测试HTTP错误处理"""
        # 模拟HTTP错误
        mock_response = Mock()
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_requests_get.return_value.__enter__.return_value = mock_response

        # 执行下载
        result = self.downloader.download_to_file(self.test_url, self.test_destination)

        # 验证结果
        assert result["success"] is False
        assert result["error_type"] == "http_error"
        assert "404" in result["error"]

    @patch("src.services.downloader.requests.get")
    def test_download_timeout_error(self, mock_requests_get):
        """测试超时错误处理"""
        # 模拟超时错误
        mock_requests_get.side_effect = requests.exceptions.Timeout()

        # 执行下载
        result = self.downloader.download_to_file(self.test_url, self.test_destination)

        # 验证结果
        assert result["success"] is False
        assert result["error_type"] == "timeout"
        assert "timeout" in result["error"].lower()

    @patch("src.services.downloader.requests.get")
    def test_download_request_exception(self, mock_requests_get):
        """测试请求异常处理"""
        # 模拟请求异常
        mock_requests_get.side_effect = requests.exceptions.ConnectionError(
            "Connection failed"
        )

        # 执行下载
        result = self.downloader.download_to_file(self.test_url, self.test_destination)

        # 验证结果
        assert result["success"] is False
        assert result["error_type"] == "request_exception"
        assert "Connection failed" in result["error"]

    def test_downloader_initialization(self):
        """测试Downloader初始化"""
        downloader = Downloader(timeout=60)
        assert downloader.timeout == 60
        assert "User-Agent" in downloader.headers

    def test_downloader_default_timeout(self):
        """测试默认超时设置"""
        downloader = Downloader()
        assert downloader.timeout == 120  # 默认值

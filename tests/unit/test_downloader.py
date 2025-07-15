# tests/unit/test_downloader.py
import pytest
import httpx
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from src.services.downloader import Downloader


class TestDownloader:
    """Downloader服务的单元测试"""
    
    @pytest.fixture
    def mock_http_client(self):
        """创建模拟的HTTP客户端"""
        return AsyncMock(spec=httpx.AsyncClient)
    
    @pytest.fixture
    def downloader(self, mock_http_client):
        """创建Downloader实例"""
        return Downloader(mock_http_client)
    
    @pytest.fixture
    def temp_file_path(self, tmp_path):
        """创建临时文件路径"""
        return tmp_path / "test_download.xbrl"
    
    @pytest.mark.asyncio
    async def test_download_to_file_success(self, downloader, mock_http_client, temp_file_path):
        """测试成功下载文件"""
        # 准备测试数据
        test_url = "https://example.com/test.xbrl"
        test_content = b"<xbrl>test content</xbrl>"
        
        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.content = test_content
        mock_response.raise_for_status = Mock()
        mock_http_client.get.return_value = mock_response
        
        # 执行下载
        result = await downloader.download_to_file(test_url, temp_file_path)
        
        # 验证结果
        assert result["success"] is True
        assert result["file_path"] == str(temp_file_path)
        assert result["file_size"] == len(test_content)
        
        # 验证文件已保存
        assert temp_file_path.exists()
        assert temp_file_path.read_bytes() == test_content
        
        # 验证HTTP客户端调用
        mock_http_client.get.assert_called_once_with(test_url, follow_redirects=True)
        mock_response.raise_for_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_download_to_file_http_error(self, downloader, mock_http_client, temp_file_path):
        """测试HTTP错误处理"""
        test_url = "https://example.com/not_found.xbrl"
        
        # 模拟HTTP 404错误
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        
        http_error = httpx.HTTPStatusError(
            "404 Not Found",
            request=Mock(),
            response=mock_response
        )
        mock_http_client.get.return_value = mock_response
        mock_response.raise_for_status.side_effect = http_error
        
        # 执行下载
        result = await downloader.download_to_file(test_url, temp_file_path)
        
        # 验证结果
        assert result["success"] is False
        assert result["error_type"] == "http_error"
        assert "404" in result["error"]
        
        # 验证文件未创建
        assert not temp_file_path.exists()
    
    @pytest.mark.asyncio
    async def test_download_to_file_timeout_error(self, downloader, mock_http_client, temp_file_path):
        """测试超时错误处理"""
        test_url = "https://example.com/slow.xbrl"
        
        # 模拟超时错误
        timeout_error = httpx.TimeoutException("Request timeout")
        mock_http_client.get.side_effect = timeout_error
        
        # 执行下载
        result = await downloader.download_to_file(test_url, temp_file_path)
        
        # 验证结果
        assert result["success"] is False
        assert result["error_type"] == "timeout"
        assert result["error"] == "Request timeout"
        
        # 验证文件未创建
        assert not temp_file_path.exists()
    
    @pytest.mark.asyncio
    async def test_download_to_file_general_error(self, downloader, mock_http_client, temp_file_path):
        """测试一般错误处理"""
        test_url = "https://example.com/error.xbrl"
        
        # 模拟一般错误
        general_error = Exception("Connection failed")
        mock_http_client.get.side_effect = general_error
        
        # 执行下载
        result = await downloader.download_to_file(test_url, temp_file_path)
        
        # 验证结果
        assert result["success"] is False
        assert result["error_type"] == "general_error"
        assert "Connection failed" in result["error"]
        
        # 验证文件未创建
        assert not temp_file_path.exists()
    
    @pytest.mark.asyncio
    async def test_download_creates_parent_directories(self, downloader, mock_http_client, tmp_path):
        """测试自动创建父目录"""
        # 创建深层目录路径
        deep_path = tmp_path / "level1" / "level2" / "level3" / "test.xbrl"
        test_url = "https://example.com/test.xbrl"
        test_content = b"test content"
        
        # 模拟HTTP响应
        mock_response = Mock()
        mock_response.content = test_content
        mock_response.raise_for_status = Mock()
        mock_http_client.get.return_value = mock_response
        
        # 执行下载
        result = await downloader.download_to_file(test_url, deep_path)
        
        # 验证结果
        assert result["success"] is True
        assert deep_path.exists()
        assert deep_path.read_bytes() == test_content
        
        # 验证父目录已创建
        assert deep_path.parent.exists()
    
    def test_download_to_file_sync_success(self, tmp_path):
        """测试同步下载成功"""
        # 创建Downloader实例（同步版本不需要http_client参数）
        downloader = Downloader(None)
        
        # 使用httpx.Client的mock
        test_url = "https://httpbin.org/json"  # 使用真实但简单的URL进行测试
        temp_file_path = tmp_path / "sync_test.json"
        
        # 由于这是同步方法且涉及真实网络请求，我们需要mock httpx.Client
        with patch('src.services.downloader.httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = b'{"test": "data"}'
            mock_response.raise_for_status = Mock()
            
            mock_client.get.return_value = mock_response
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client
            
            # 执行同步下载
            result = downloader.download_to_file_sync(test_url, temp_file_path)
            
            # 验证结果
            assert result["success"] is True
            assert result["file_path"] == str(temp_file_path)
            assert temp_file_path.exists()
    
    def test_download_to_file_sync_http_error(self, tmp_path):
        """测试同步下载HTTP错误"""
        downloader = Downloader(None)
        test_url = "https://example.com/not_found.json"
        temp_file_path = tmp_path / "sync_error_test.json"
        
        with patch('src.services.downloader.httpx.Client') as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.reason_phrase = "Not Found"
            
            http_error = httpx.HTTPStatusError(
                "404 Not Found",
                request=Mock(),
                response=mock_response
            )
            mock_client.get.return_value = mock_response
            mock_response.raise_for_status.side_effect = http_error
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=None)
            mock_client_class.return_value = mock_client
            
            # 执行同步下载
            result = downloader.download_to_file_sync(test_url, temp_file_path)
            
            # 验证结果
            assert result["success"] is False
            assert result["error_type"] == "http_error"
            assert "404" in result["error"]
            assert not temp_file_path.exists()
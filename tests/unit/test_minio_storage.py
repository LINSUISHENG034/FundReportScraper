"""
Tests for MinIO storage functionality.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.storage.minio_client import MinIOStorage, StorageError


class TestMinIOStorage:
    """Test MinIO storage implementation."""
    
    @pytest.fixture
    def storage(self):
        """Create storage instance with mocked client."""
        with patch('src.storage.minio_client.Minio') as mock_minio:
            mock_client = MagicMock()
            mock_minio.return_value = mock_client
            
            storage = MinIOStorage()
            storage.client = mock_client
            return storage
    
    def test_generate_file_path(self, storage):
        """Test file path generation."""
        # Annual report
        path = storage.generate_file_path(
            fund_code="000001",
            report_date="2023-12-31",
            report_type="ANNUAL",
            file_extension="xbrl"
        )
        assert path == "reports/2023/annual/000001_2023-12-31_annual.xbrl"
        
        # Quarterly report
        path = storage.generate_file_path(
            fund_code="000002",
            report_date="2023-03-31",
            report_type="QUARTERLY",
            file_extension="pdf"
        )
        assert path == "reports/2023/q1/000002_2023-03-31_quarterly.pdf"
        
        # Semi-annual report
        path = storage.generate_file_path(
            fund_code="000003",
            report_date="2023-06-30",
            report_type="SEMI_ANNUAL",
            file_extension="html"
        )
        assert path == "reports/2023/semi_annual/000003_2023-06-30_semi_annual.html"
    
    def test_get_content_type(self, storage):
        """Test content type determination."""
        assert storage._get_content_type("xbrl") == "application/xml"
        assert storage._get_content_type("pdf") == "application/pdf"
        assert storage._get_content_type("html") == "text/html"
        assert storage._get_content_type("unknown") == "application/octet-stream"
    
    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_new_bucket(self, storage):
        """Test bucket creation when it doesn't exist."""
        storage.client.bucket_exists.return_value = False
        storage.client.make_bucket.return_value = None
        
        await storage.ensure_bucket_exists()
        
        storage.client.bucket_exists.assert_called_once_with(storage.bucket_name)
        storage.client.make_bucket.assert_called_once_with(storage.bucket_name)
    
    @pytest.mark.asyncio
    async def test_ensure_bucket_exists_existing_bucket(self, storage):
        """Test when bucket already exists."""
        storage.client.bucket_exists.return_value = True
        
        await storage.ensure_bucket_exists()
        
        storage.client.bucket_exists.assert_called_once_with(storage.bucket_name)
        storage.client.make_bucket.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self, storage):
        """Test successful file upload."""
        test_content = b"test file content"
        
        # Mock successful operations
        storage.client.bucket_exists.return_value = True
        storage.client.put_object.return_value = None
        
        file_path = await storage.upload_file(
            file_content=test_content,
            fund_code="000001",
            report_date="2023-12-31",
            report_type="ANNUAL",
            file_extension="xbrl"
        )
        
        assert file_path == "reports/2023/annual/000001_2023-12-31_annual.xbrl"
        storage.client.put_object.assert_called_once()
        
        # Check put_object call arguments
        call_args = storage.client.put_object.call_args
        assert call_args[1]["bucket_name"] == storage.bucket_name
        assert call_args[1]["object_name"] == file_path
        assert call_args[1]["length"] == len(test_content)
        assert call_args[1]["content_type"] == "application/xml"
    
    @pytest.mark.asyncio
    async def test_upload_file_with_custom_content_type(self, storage):
        """Test upload with custom content type."""
        test_content = b"test content"
        custom_type = "application/custom"
        
        storage.client.bucket_exists.return_value = True
        storage.client.put_object.return_value = None
        
        await storage.upload_file(
            file_content=test_content,
            fund_code="000001",
            report_date="2023-12-31",
            report_type="ANNUAL",
            file_extension="custom",
            content_type=custom_type
        )
        
        call_args = storage.client.put_object.call_args
        assert call_args[1]["content_type"] == custom_type
    
    @pytest.mark.asyncio
    async def test_download_file_success(self, storage):
        """Test successful file download."""
        test_content = b"downloaded content"
        
        # Mock response object
        mock_response = MagicMock()
        mock_response.read.return_value = test_content
        storage.client.get_object.return_value = mock_response
        
        content = await storage.download_file("test/path/file.xbrl")
        
        assert content == test_content
        storage.client.get_object.assert_called_once_with(
            bucket_name=storage.bucket_name,
            object_name="test/path/file.xbrl"
        )
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_file_exists_true(self, storage):
        """Test file exists check when file is present."""
        storage.client.stat_object.return_value = MagicMock()
        
        exists = await storage.file_exists("test/file.xbrl")
        
        assert exists is True
        storage.client.stat_object.assert_called_once_with(
            bucket_name=storage.bucket_name,
            object_name="test/file.xbrl"
        )
    
    @pytest.mark.asyncio
    async def test_file_exists_false(self, storage):
        """Test file exists check when file is not present."""
        from minio.error import S3Error
        storage.client.stat_object.side_effect = S3Error(
            "NoSuchKey", "The specified key does not exist.", "test", "host", "path"
        )
        
        exists = await storage.file_exists("test/nonexistent.xbrl")
        
        assert exists is False
    
    @pytest.mark.asyncio
    async def test_delete_file_success(self, storage):
        """Test successful file deletion."""
        storage.client.remove_object.return_value = None
        
        result = await storage.delete_file("test/file.xbrl")
        
        assert result is True
        storage.client.remove_object.assert_called_once_with(
            bucket_name=storage.bucket_name,
            object_name="test/file.xbrl"
        )
    
    @pytest.mark.asyncio
    async def test_delete_file_error(self, storage):
        """Test file deletion with error."""
        from minio.error import S3Error
        storage.client.remove_object.side_effect = S3Error(
            "AccessDenied", "Access denied", "test", "host", "path"
        )
        
        result = await storage.delete_file("test/file.xbrl")
        
        assert result is False
    
    def test_get_file_url(self, storage):
        """Test presigned URL generation."""
        expected_url = "https://example.com/presigned-url"
        storage.client.presigned_get_object.return_value = expected_url
        
        url = storage.get_file_url("test/file.xbrl", expires=3600)
        
        assert url == expected_url
        storage.client.presigned_get_object.assert_called_once()
        
        # Check arguments
        call_args = storage.client.presigned_get_object.call_args
        assert call_args[1]["bucket_name"] == storage.bucket_name
        assert call_args[1]["object_name"] == "test/file.xbrl"
    
    @pytest.mark.asyncio
    async def test_upload_file_s3_error(self, storage):
        """Test upload with S3 error."""
        from minio.error import S3Error
        
        storage.client.bucket_exists.return_value = True
        storage.client.put_object.side_effect = S3Error(
            "AccessDenied", "Access denied", "test", "host", "path"
        )
        
        with pytest.raises(StorageError) as exc_info:
            await storage.upload_file(
                file_content=b"test",
                fund_code="000001",
                report_date="2023-12-31",
                report_type="ANNUAL",
                file_extension="xbrl"
            )
        
        assert "S3 upload error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_file_s3_error(self, storage):
        """Test download with S3 error."""
        from minio.error import S3Error
        
        storage.client.get_object.side_effect = S3Error(
            "NoSuchKey", "Key not found", "test", "host", "path"
        )
        
        with pytest.raises(StorageError) as exc_info:
            await storage.download_file("test/nonexistent.xbrl")
        
        assert "S3 download error" in str(exc_info.value)
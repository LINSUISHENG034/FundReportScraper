# src/services/downloader.py
import httpx
from pathlib import Path
from src.core.logging import get_logger

logger = get_logger(__name__)


class Downloader:
    """
    核心下载器服务
    专门负责文件下载的独立服务，支持错误处理和重试逻辑
    """
    
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def download_to_file(self, url: str, destination: Path) -> dict:
        """
        从给定的URL下载内容并保存到目标文件。
        包含错误处理和日志记录。
        
        Args:
            url: 下载URL
            destination: 目标文件路径
            
        Returns:
            dict: 下载结果，包含success状态和相关信息
        """
        bound_logger = logger.bind(url=url, destination=str(destination))
        bound_logger.info("downloader.download.start")
        
        try:
            response = await self.http_client.get(url, follow_redirects=True)
            response.raise_for_status()  # 针对 4xx/5xx 错误抛出异常

            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)

            bound_logger.info(
                "downloader.download.success",
                file_size=len(response.content)
            )
            
            return {
                "success": True,
                "file_path": str(destination),
                "file_size": len(response.content)
            }
            
        except httpx.HTTPStatusError as e:
            bound_logger.error(
                "downloader.download.http_error",
                status_code=e.response.status_code
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
                "error_type": "http_error"
            }
            
        except httpx.TimeoutException as e:
            bound_logger.error(
                "downloader.download.timeout_error",
                error=str(e)
            )
            return {
                "success": False,
                "error": "Request timeout",
                "error_type": "timeout"
            }
            
        except Exception as e:
            bound_logger.error(
                "downloader.download.general_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": str(e),
                "error_type": "general_error"
            }

    def download_to_file_sync(self, url: str, destination: Path) -> dict:
        """
        同步版本的下载方法，用于Celery任务
        
        Args:
            url: 下载URL
            destination: 目标文件路径
            
        Returns:
            dict: 下载结果，包含success状态和相关信息
        """
        bound_logger = logger.bind(url=url, destination=str(destination))
        bound_logger.info("downloader.download_sync.start")
        
        try:
            with httpx.Client(follow_redirects=True, timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()

                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(response.content)

                bound_logger.info(
                    "downloader.download_sync.success",
                    file_size=len(response.content)
                )
                
                return {
                    "success": True,
                    "file_path": str(destination),
                    "file_size": len(response.content)
                }
                
        except httpx.HTTPStatusError as e:
            bound_logger.error(
                "downloader.download_sync.http_error",
                status_code=e.response.status_code
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
                "error_type": "http_error"
            }
            
        except httpx.TimeoutException as e:
            bound_logger.error(
                "downloader.download_sync.timeout_error",
                error=str(e)
            )
            return {
                "success": False,
                "error": "Request timeout",
                "error_type": "timeout"
            }
            
        except Exception as e:
            bound_logger.error(
                "downloader.download_sync.general_error",
                error=str(e),
                error_type=type(e).__name__
            )
            return {
                "success": False,
                "error": str(e),
                "error_type": "general_error"
            }
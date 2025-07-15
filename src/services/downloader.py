import requests
from pathlib import Path
from src.core.logging import get_logger
from src.core.config import settings

logger = get_logger(__name__)


class Downloader:
    """
    核心下载器服务 (基于 requests)
    专门负责文件下载的独立服务。
    使用 requests 库，以在 gevent 环境中获得最佳兼容性和稳定性。
    """

    def __init__(self, timeout: int = 120):
        """
        初始化下载器。
        Args:
            timeout: 请求超时时间（秒）。
        """
        self.timeout = timeout
        self.headers = {
            'User-Agent': settings.scraper.user_agent
        }

    def download_to_file(self, url: str, destination: Path) -> dict:
        """
        从给定的URL下载内容并保存到目标文件。
        
        Args:
            url: 下载URL
            destination: 目标文件路径
            
        Returns:
            dict: 下载结果，包含success状态和相关信息
        """
        bound_logger = logger.bind(url=url, destination=str(destination))
        bound_logger.info("downloader.download.start")

        try:
            # 使用 requests.get 进行同步下载
            # gevent 会自动处理这里的阻塞IO，使其变为非阻塞
            with requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True, stream=True) as response:
                response.raise_for_status()  # 针对 4xx/5xx 错误抛出异常

                destination.parent.mkdir(parents=True, exist_ok=True)
                
                # 使用 stream=True 和 iter_content 避免一次性将大文件读入内存
                with open(destination, 'wb') as f:
                    file_size = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        file_size += len(chunk)

                bound_logger.info(
                    "downloader.download.success",
                    file_size=file_size
                )
                
                return {
                    "success": True,
                    "file_path": str(destination),
                    "file_size": file_size
                }

        except requests.exceptions.HTTPError as e:
            bound_logger.error(
                "downloader.download.http_error",
                status_code=e.response.status_code
            )
            return {
                "success": False,
                "error": f"HTTP Error: {e.response.status_code}",
                "error_type": "http_error"
            }
            
        except requests.exceptions.Timeout:
            bound_logger.error("downloader.download.timeout_error")
            return {
                "success": False,
                "error": "Request timeout",
                "error_type": "timeout"
            }
            
        except requests.exceptions.RequestException as e:
            bound_logger.error(
                "downloader.download.request_exception",
                error=str(e)
            )
            return {
                "success": False,
                "error": f"Request failed: {e}",
                "error_type": "request_exception"
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

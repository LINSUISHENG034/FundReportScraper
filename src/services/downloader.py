import aiohttp
import asyncio
from pathlib import Path
from src.core.logging import get_logger

logger = get_logger(__name__)


class Downloader:
    """
    核心下载器服务 (基于 aiohttp)
    专门负责文件下载的独立服务，使用 aiohttp 以更好地兼容 gevent 环境。
    """

    def __init__(self, timeout: int = 30):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        }

    async def download_to_file(self, url: str, destination: Path) -> dict:
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
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url, allow_redirects=True) as response:
                    response.raise_for_status()  # 针对 4xx/5xx 错误抛出异常

                    destination.parent.mkdir(parents=True, exist_ok=True)
                    content = await response.read()
                    destination.write_bytes(content)

                    bound_logger.info(
                        "downloader.download.success",
                        file_size=len(content)
                    )
                    
                    return {
                        "success": True,
                        "file_path": str(destination),
                        "file_size": len(content)
                    }

        except aiohttp.ClientResponseError as e:
            bound_logger.error(
                "downloader.download.http_error",
                status_code=e.status,
                message=e.message
            )
            return {
                "success": False,
                "error": f"HTTP {e.status}: {e.message}",
                "error_type": "http_error"
            }
            
        except asyncio.TimeoutError:
            bound_logger.error("downloader.download.timeout_error")
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

# Phase 4.3: Downloader Refactoring Plan (requests)

## 1. Objective

To definitively resolve the persistent timeout errors in the Celery E2E download workflow by replacing the underlying network library in the download stack from `aiohttp` to `requests`.

## 2. Diagnosis

Our extensive debugging has conclusively shown that the root cause of the timeout issue is a fundamental incompatibility between the `aiohttp` library (designed for `asyncio`) and the `gevent` execution pool used by our Celery workers on Windows.

- **Evidence**: The `debug_download_flow.py` script, which runs the download services in a pure `asyncio` context, works perfectly. The E2E test, which runs the same services under a `gevent` worker, consistently fails.

- **Solution**: We will replace `aiohttp` with the `requests` library in our `Downloader` service. `requests` is a synchronous library that is made fully cooperative and non-blocking by `gevent`'s monkey-patching, making it the industry-standard and most stable choice for networking in a `gevent` environment.

## 3. Implementation Steps

### Step 1: Refactor `src/services/downloader.py`

This is the core of the refactoring. The `Downloader` service must be changed from an asynchronous `aiohttp`-based implementation to a synchronous `requests`-based one.

**Action**: Replace the entire content of `src/services/downloader.py` with the following code.

```python
# src/services/downloader.py

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
```

### Step 2: Adjust `src/services/fund_report_service.py`

Because `downloader.download_to_file` is now a synchronous method, the `download_report` method in `FundReportService` which calls it must also become synchronous.

**Action**: Modify the `download_report` method in `src/services/fund_report_service.py`.

**Change `async def download_report` to `def download_report`**:

```python
# In src/services/fund_report_service.py

# BEFORE
async def download_report(self, report: Dict, save_dir: Path) -> Dict:
    # ...

# AFTER
def download_report(self, report: Dict, save_dir: Path) -> Dict:
    # ...
```
The body of the method does not need to change, only the signature.

### Step 3: Simplify `src/tasks/download_tasks.py`

The Celery task `download_report_chain` was using a helper (`run_async_task`) to call the asynchronous download service. Now that the service is synchronous, we can simplify the task significantly.

**Action**: Modify the `download_report_chain` task and remove the now-unused `_async_download_logic` function in `src/tasks/download_tasks.py`.

**3.1: Remove the `_async_download_logic` function entirely.**

**3.2: Modify the `download_report_chain` task and the `get_services` function.**

```python
# In src/tasks/download_tasks.py

# --- BEFORE ---

# async def get_services():
#     """..."""
#     downloader = Downloader()
#     session = aiohttp.ClientSession(...)
#     scraper = CSRCFundReportScraper(session=session)
#     fund_report_service = FundReportService(scraper, downloader)
#     parser = XBRLParser()
#     return fund_report_service, parser, session

# async def _async_download_logic(report_info: Dict, save_dir: str) -> Dict:
#     fund_report_service, _, session = await get_services()
#     try:
#         download_result = await fund_report_service.download_report(...)
#         return download_result
#     finally:
#         if session:
#             await session.close()

# @celery_app.task(...)
# def download_report_chain(self, report_info: Dict, save_dir: str) -> Dict:
#     # ...
#     download_result = run_async_task(
#         _async_download_logic,
#         report_info=report_info,
#         save_dir=save_dir
#     )
#     # ...

# --- AFTER ---

def get_services_sync():
    """
    (同步)集中创建和提供服务实例。
    """
    downloader = Downloader()
    # aiohttp.ClientSession is no longer needed for the downloader
    # It might still be needed for the scraper if it's not refactored.
    # For this plan, we assume scraper still needs an async session.
    scraper_session = aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=120.0),
        headers={'User-Agent': settings.scraper.user_agent}
    )
    scraper = CSRCFundReportScraper(session=scraper_session)
    fund_report_service = FundReportService(scraper=scraper, downloader=downloader)
    parser = XBRLParser()
    
    # Return the session so it can be closed later
    return fund_report_service, parser, scraper_session

@celery_app.task(bind=True, autoretry_for=(requests.exceptions.RequestException,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def download_report_chain(self, report_info: Dict, save_dir: str) -> Dict:
    """
    原子任务：下载单个报告。
    这是任务链的第一步。现在是同步执行。
    """
    bound_logger = logger.bind(upload_info_id=report_info.get("upload_info_id"), celery_task_id=self.request.id)
    bound_logger.info("download_report_chain.start")
    
    fund_report_service, _, scraper_session = get_services_sync()
    
    try:
        # Directly call the synchronous service method
        download_result = fund_report_service.download_report(
            report=report_info,
            save_dir=Path(save_dir)
        )
    finally:
        # Ensure the scraper's session is closed if it was created
        if scraper_session:
            # We need to run the async close in an event loop
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(scraper_session.close())
                else:
                    loop.run_until_complete(scraper_session.close())
            except Exception as e:
                bound_logger.warning("failed_to_close_scraper_session", error=str(e))

    if not download_result.get("success"):
        # The exception for autoretry is now requests.exceptions.RequestException
        # We still raise a generic exception to be safe.
        raise Exception(f"Download failed: {download_result.get('error')}")
        
    return download_result
```
*Note*: The logic to close the `scraper_session` is a bit complex because we are in a synchronous Celery task. The provided code shows a safe way to handle it. The `get_services` function also needs to be refactored to be synchronous.

## 4. Verification

After implementing the changes above, please perform the following verification steps:

1.  **Unit Test**: Create a `pytest` test for the new `Downloader` service in `tests/unit/test_downloader.py`. Use the `@pytest.mark.vcr` decorator to record and replay the HTTP request to avoid hitting the real network on every test run. This will validate the `requests` implementation in isolation.

2.  **End-to-End Test**: Run the `scripts/verification/verify_e2e_download.py` script. This is the ultimate test. It should now complete successfully without any timeout errors.

Once these steps are completed and verified, the issue will be resolved.

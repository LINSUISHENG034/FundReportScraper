# Phase 1.5 - `gevent` 兼容性修复计划

## 1. 背景与问题分析

在代码审查和端到端（E2E）测试中，我们发现了一个持续存在的 `Request timeout` 错误。该错误仅在通过 Celery Worker 执行下载任务时出现，而直接运行 MVP 测试脚本 (`reference/validated_implementations/enhanced_batch_download.py`) 则可以成功下载。

**根本原因分析**：

经过深入排查，问题根源被定位为 **`httpx` 异步库与 Celery Worker 使用的 `gevent` 并发模型之间存在兼容性问题**。`gevent` 通过 monkey-patching（猴子补丁）来修改标准库以实现协作式并发，而 `httpx` 的原生 `asyncio` 实现与此机制在特定场景下会发生冲突，导致网络请求被挂起，最终引发超时。

成功的 MVP 脚本使用的是 `aiohttp` 库，该库与 `gevent` 的兼容性更好，这一事实为我们的问题诊断提供了决定性证据。

## 2. 修复目标

**将所有在 Celery Worker 中涉及网络请求的服务，其底层的 HTTP 客户端统一为 `aiohttp` 库**，从而彻底解决 `gevent` 兼容性问题，确保下载工作流的稳定与正确。

## 3. 详细重构步骤

请开发团队严格按照以下步骤顺序执行。

### 第一步：重构 Downloader 服务

**目标**：将核心下载器 `Downloader` 的实现从 `httpx` 切换为 `aiohttp`。

**文件**: `src/services/downloader.py`

**操作**: 使用以下代码完全覆盖现有文件内容。

```python
# docs/refactoring/PHASE_1_REPAIR_PLAN.md
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
        """
        bound_logger = logger.bind(url=url, destination=str(destination))
        bound_logger.info("downloader.download.start")

        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                async with session.get(url, allow_redirects=True) as response:
                    response.raise_for_status()

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
            bound_logger.error("downloader.download.http_error", status_code=e.status, message=e.message)
            return {"success": False, "error": f"HTTP {e.status}: {e.message}", "error_type": "http_error"}
        except asyncio.TimeoutError:
            bound_logger.error("downloader.download.timeout_error")
            return {"success": False, "error": "Request timeout", "error_type": "timeout"}
        except Exception as e:
            bound_logger.error("downloader.download.general_error", error=str(e), error_type=type(e).__name__)
            return {"success": False, "error": str(e), "error_type": "general_error"}

```

### 第二步：重构 Scraper 服务

**目标**：将 `CSRCFundReportScraper` 及其基类 `BaseScraper` 的实现从 `httpx` 切换为 `aiohttp`。

**文件 1**: `src/scrapers/base.py`

**操作**:
1.  将 `httpx.AsyncClient` 替换为 `aiohttp.ClientSession`。
2.  修改 `get` 方法以适应 `aiohttp` 的用法。

**文件 2**: `src/scrapers/csrc_fund_scraper.py`

**操作**:
1.  修改 `__init__` 方法的 `session` 类型提示。
2.  修改 `search_reports` 方法，使用 `aiohttp.ClientSession` 发起请求并处理响应。

*（注：为简化计划，此处省略具体代码块，开发团队应参照 `Downloader` 的修改模式，将 `httpx` 调用替换为等效的 `aiohttp` 调用。）*

### 第三步：更新服务初始化逻辑

**目标**：在 FastAPI 和 Celery 的入口处，正确地创建和注入基于 `aiohttp` 的新服务。

**文件 1**: `src/main.py`

**操作**: 修改 `lifespan` 函数，创建和管理 `aiohttp.ClientSession`，并用它来初始化 `CSRCFundReportScraper`。`Downloader` 应无参数初始化。

**示例修改**:
```python
# src/main.py
import aiohttp
# ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ...
    app.state.http_client = aiohttp.ClientSession()
    # ...
    scraper = CSRCFundReportScraper(session=app.state.http_client)
    downloader = Downloader() # 无需传入 client
    app.state.fund_report_service = FundReportService(scraper=scraper, downloader=downloader)
    # ...
    await app.state.http_client.close()
    # ...
```

**文件 2**: `src/tasks/download_tasks.py`

**操作**: 修改 `get_services` 函数，使其不再创建 `httpx` 客户端，并正确初始化服务。

**示例修改**:
```python
# src/tasks/download_tasks.py
import aiohttp
# ...

def get_services():
    # ...
    # 注意：此处为简化示例，每次调用都创建新 session。
    # 在高并发场景下，应考虑 session 的复用策略。
    session = aiohttp.ClientSession()
    downloader = Downloader()
    scraper = CSRCFundReportScraper(session=session)
    fund_report_service = FundReportService(scraper, downloader)
    # ...
    return fund_report_service, parser
```

## 4. 依赖验证

请确保 `pyproject.toml` 文件中包含 `aiohttp` 依赖。

```toml
[tool.poetry.dependencies]
# ...
aiohttp = "^3.12.14"
# ...
```

## 5. 最终验证流程

1.  **停止所有服务**：确保所有 `fastapi` 和 `celery` 进程都已停止。
2.  **启动 FastAPI 服务器**：`poetry run python src/main.py`
3.  **启动 Celery Worker**：`poetry run celery -A src.core.celery_app.app worker --loglevel=info -P gevent`
4.  **运行验证脚本**：`poetry run python scripts/verification/verify_phase4_e2e_download.py`

**预期结果**：

*   验证脚本输出 `SUCCESS: Verification complete. All files found.`
*   `data/downloads/` 目录下成功生成报告文件（如 `004899_19052421.xml`）。
*   Celery Worker 日志中不再出现 `Request timeout` 错误，而是显示下载成功的日志。

---
**架构师确认**

请开发团队在完成上述修改和内部测试后，通知我进行最终的把关验证。

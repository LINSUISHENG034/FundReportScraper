# 重构计划：Phase 3 指导文档 - Celery Worker 与下载模块

**目标：** 彻底重构后台任务处理系统，用一个解耦的、可扩展的、基于任务链的健壮系统，替换当前高度耦合的巨型任务。

**核心方法论：** 严格遵循单一职责原则，将复杂的下载、解析、保存流程分解为一系列独立的、可测试的、可复用的组件和任务。

---

### **Windows 兼容性特别说明 (Windows Compatibility Note)**

根据团队前期的宝贵经验总结 (`docs/technical/celery_windows_compatibility_fix.md`)，Celery 的默认 `prefork` 并发池在 Windows 上不受支持。

本项目中的下载任务是典型的高并发 I/O 密集型场景，因此，**在本次重构中，我们必须使用 `gevent` 并发池。**

**关键操作指令:**
1.  **安装依赖:**
    ```bash
    pip install gevent
    ```
2.  **启动 Worker:**
    *   在启动 Celery Worker 时，必须明确指定 `--pool=gevent` 参数。推荐使用较高的并发数（如 `--concurrency=50`）以发挥其性能优势。
    ```bash
    celery -A src.core.celery_app worker --pool=gevent --concurrency=50 -l info
    ```

本指导文档中设计的 `celery.chord` 任务流与 `gevent` 池完全兼容，是实现高效、健壮的后台任务处理的最佳实践。

---

## 任务列表

### 任务 3.1: 创建核心下载器服务 (Downloader Service)

*   **目的：** 抽象出所有与“下载”相关的逻辑，创建一个专用的、可复用的服务。

1.  **创建服务文件:**
    *   在 `src/services/` 目录下创建新文件 `downloader.py`。

2.  **实现 `Downloader` 类:**
    *   提供以下代码框架作为参考：

    ```python
    # src/services/downloader.py
    import httpx
    from pathlib import Path
    from src.core.logging import get_logger

    logger = get_logger(__name__)

    class Downloader:
        def __init__(self, http_client: httpx.AsyncClient):
            self.http_client = http_client

        async def download_to_file(self, url: str, destination: Path):
            """
            从给定的URL下载内容并保存到目标文件。
            包含错误处理和日志记录。
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
            except httpx.HTTPStatusError as e:
                bound_logger.error(
                    "downloader.download.http_error",
                    status_code=e.response.status_code
                )
                raise  # 重新抛出异常，让调用者处理
            except Exception as e:
                bound_logger.error(
                    "downloader.download.general_error",
                    error=str(e)
                )
                raise

    ```

3.  **创建单元测试:**
    *   在 `tests/unit/` 目录下创建 `test_downloader.py`。
    *   使用 `pytest-httpx` 模拟各种网络场景（成功、404、500、超时），对 `Downloader` 进行全面的单元测试。

---

### 任务 3.2: 重构 `FundReportService`

*   **目的：** 剥离其下载职责，使其专注于业务流程。

1.  **修改 `__init__` 方法:**
    *   为 `FundReportService` 注入新的 `Downloader` 依赖。

2.  **重写 `download_report` 方法:**
    *   移除所有 `httpx` 和文件写入逻辑。
    *   新的实现应该只负责：
        a.  根据报告信息构造下载 URL。
        b.  确定文件保存路径。
        c.  调用 `self.downloader.download_to_file()` 方法。

3.  **清理代码:**
    *   **彻底删除** `batch_download`、`enhanced_batch_download` 和所有 `_sync` 后缀的模拟方法。这些逻辑将被新的 Celery 任务流取代。

---

### 任务 3.3: 任务分解与 Celery Canvas 编排

*   **目的：** 将巨型任务分解为一系列独立的、可链接的 Celery 任务。

1.  **重写 `src/tasks/download_tasks.py`:**
    *   删除旧的 `download_fund_report_task` 及其所有辅助函数。

2.  **创建原子任务 (Atomic Tasks):**
    *   `download_single_report(report_info: dict, save_dir: str)`:
        *   接收报告元数据和保存目录。
        *   调用 `FundReportService` 和 `Downloader` 下载单个文件。
        *   **返回文件路径**以供下一个任务使用。
        *   配置 Celery 的自动重试机制 (`autoretry_for`) 以处理网络错误。
    *   `parse_single_report(file_path: str)`:
        *   接收一个文件路径。
        *   调用 `XBRLParser` 解析文件。
        *   **返回解析后的数据字典**。
    *   `save_parsed_data(parsed_data: dict)`:
        *   接收解析后的数据。
        *   调用 `FundDataService` 将其存入数据库。
        *   **返回保存后的报告ID**。

3.  **创建编排与收尾任务:**
    *   `start_download_pipeline(task_id: str)`:
        *   这是总入口任务，由 API 层调用。
        *   它负责从数据库加载主任务信息，获取报告列表，然后使用 `celery.chord` 构建并启动任务流。
    *   `finalize_batch_download(results: list, task_id: str)`:
        *   这是 `chord` 的回调任务。
        *   它接收所有子任务链的最终结果（一个包含所有报告ID的列表）。
        *   负责统计成功与失败，并更新主 `DownloadTask` 的最终状态。

4.  **Celery Chord 编排示例:**

    ```python
    # src/tasks/download_tasks.py (伪代码)
    from celery import chord, group
    from src.services import get_downloader, get_fund_report_service # 假设有工厂函数

    @celery_app.task
    def download_single_report(report_info, save_dir):
        # ...下载逻辑...
        return str(file_path) # 返回文件路径

    @celery_app.task
    def parse_single_report(file_path):
        # ...解析逻辑...
        return parsed_data # 返回解析数据

    @celery_app.task
    def save_parsed_data(parsed_data):
        # ...保存逻辑...
        return report_id # 返回数据库ID

    @celery_app.task(bind=True)
    def finalize_batch_download(self, results, task_id):
        # ...统计成功/失败，更新主任务状态...
        # results 是一个列表，包含了所有 save_parsed_data 任务的返回值
        successful_count = len(results)
        # ...更新数据库...

    @celery_app.task
    def start_download_pipeline(task_id):
        # 1. 从数据库获取任务详情和报告列表
        reports_to_download = ...

        # 2. 为每个报告创建一个由“下载->解析->保存”组成的任务链
        task_chain = download_single_report.s(save_dir) | parse_single_report.s() | save_parsed_data.s()

        # 3. 将所有任务链组合成一个 group
        pipeline_group = group(
            task_chain.clone([report]) for report in reports_to_download
        )

        # 4. 使用 chord 编排，在 group 全部完成后调用 finalize 回调
        chord(pipeline_group)(finalize_batch_download.s(task_id=task_id))
    ```

---

### 任务 3.4: 更新 API 层调用

*   **目的：** 将下载请求的入口点连接到新的任务流水线。

1.  **修改 `src/api/routes/downloads.py`:**
    *   找到创建下载任务的那个端点。
    *   在成功创建 `DownloadTask` 记录到数据库后，修改其调用 Celery 任务的代码。
    *   将 `old_task.delay(task_id)` 修改为 `start_download_pipeline.delay(task_id)`。

---

### **验收标准 (Acceptance Criteria)**

1.  `src/services/downloader.py` 和 `tests/unit/test_downloader.py` 被创建且测试通过。
2.  `FundReportService` 不再包含任何直接的下载逻辑或 `_sync` 方法。
3.  `src/tasks/download_tasks.py` 被重构为多个小任务，并使用 `celery.chord` 进行编排。
4.  API 层现在调用新的 `start_download_pipeline` 任务来启动下载流程。
5.  整个下载-解析-保存的流程可以成功运行，并且数据库中的 `DownloadTask` 状态能够被正确更新。

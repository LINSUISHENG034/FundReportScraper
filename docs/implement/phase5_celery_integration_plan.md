# Phase 5 开发计划：引入Celery任务队列

**目标：将核心数据处理流水线从 FastAPI 的 `BackgroundTasks` 迁移到强大、可扩展的 Celery 任务队列，构建生产级的异步处理架构。**

## 📋 Phase 4 成果与挑战

-   **成果**: 我们成功实现了“下载-解析-存储”的完整数据处理逻辑。
-   **挑战**: 我们反复遇到后台任务静默失败、依赖注入和会话管理困难的问题。这证明了轻量级的 `BackgroundTasks` 已无法承载我们日益复杂的后台处理需求。

## 🎯 Phase 5 核心目标

**用正确的工具解决正确的问题。** 我们将引入行业标准的任务队列系统 Celery + Redis，一劳永逸地解决后台任务的隔离性、健壮性和扩展性问题。

1.  **架构升级**: 将 Celery 和 Redis 集成到我们的技术栈中。
2.  **任务迁移**: 将 `execute_download_task` 的完整逻辑迁移为一个独立的 Celery 任务。
3.  **API改造**: 修改下载接口，使其不再直接执行逻辑，而是将任务派发到 Celery 队列。
4.  **本地验证**: 建立完整的本地开发环境，验证新的异步任务流程。

## 💡 设计原则

1.  **彻底隔离**: Celery Worker 作为独立进程运行，拥有自己的内存空间和依赖，与 FastAPI Web 服务彻底分离。
2.  **可靠通信**: 使用 Redis 作为消息代理（Broker），确保任务的可靠派发和接收。
3.  **面向失败**: 利用 Celery 的重试机制，使任务在遇到临时性错误（如网络波动）时能自动恢复。
4.  **可监控性**: 为未来使用 Flower 等工具监控任务执行状态奠定基础。

## 🏗️ 实施步骤

### 步骤 5.1: 环境准备与依赖安装 (高优先级)

**目标**: 准备好运行 Celery 的所有必要条件。

**任务**:
1.  **安装 Redis**: 在您的本地开发环境中安装并运行 Redis 服务。最简单的方式是使用 Docker：
    ```bash
    docker run -d -p 6379:6379 --name fund-redis redis:latest
    ```
2.  **安装 Python 库**: 在项目的虚拟环境中安装 Celery 和 Redis 的 Python 客户端。
    ```bash
    D:\Users\LINSUISHENG034\anaconda3\envs\fund-scraper\python.exe -m pip install "celery[redis]"
    ```

**验收标准**:
- [ ] 本地 Redis 服务正在运行，可以通过 `redis-cli ping` 得到 `PONG` 回复。
- [ ] `celery` 和 `redis` 库已成功安装到虚拟环境中。

### 步骤 5.2: 配置 Celery 应用 (高优先级)

**目标**: 创建并配置 Celery 实例，使其连接到 Redis。

**任务**:
1.  在 `src/core/` 目录下创建新文件 `celery_app.py`。
2.  在该文件中，编写如下代码来初始化 Celery：
    ```python
    from celery import Celery
    from src.core.config import settings

    # 将 Redis URL 从 settings 中获取
    redis_url = settings.redis_url # 例如: "redis://localhost:6379/0"

    celery_app = Celery(
        "fund_scraper_tasks",
        broker=redis_url,
        backend=redis_url, # 使用 Redis 作为结果存储后端
        include=["src.tasks.download_tasks"] # 指定任务所在的模块
    )

    celery_app.conf.update(
        task_track_started=True, # 追踪任务开始状态
        result_expires=3600, # 任务结果一小时后过期
    )
    ```
3.  在 `src/core/config.py` 中添加 `redis_url` 配置项。

**验收标准**:
- [ ] `src/core/celery_app.py` 文件已创建并包含正确的配置。
- [ ] `src/core/config.py` 中已添加 `redis_url`。

### 步骤 5.3: 创建 Celery 任务 (高优先级)

**目标**: 将我们的核心数据处理逻辑封装成一个可被 Celery 调度的任务。

**任务**:
1.  在 `src/` 目录下创建新文件夹 `tasks/`。
2.  在 `src/tasks/` 目录下创建新文件 `download_tasks.py`。
3.  将 `src/api/routes/downloads.py` 中的 `execute_download_task` 函数的**完整内部���辑**复制到 `download_tasks.py` 中。
4.  修改该函数，为其添加 `@celery_app.task` 装饰器，并进行必要的改造：
    ```python
    import httpx
    from pathlib import Path
    from datetime import datetime
    from src.core.celery_app import celery_app
    from src.core.logging import get_logger
    # ... 其他必要的导入 ...

    logger = get_logger(__name__)

    @celery_app.task(bind=True, name="tasks.download_fund_report")
    def download_fund_report_task(self, task_id: str):
        """
        下载并处理单个基金报告的 Celery 任务
        """
        bound_logger = logger.bind(task_id=task_id, celery_task_id=self.request.id)
        bound_logger.info("celery.task.start")

        # 此处是 execute_download_task 的完整逻辑
        # 包括：创建数据库会话、创建所有服务实例、更新状态、下载、解析、存储等
        # ...
    ```

**验收标准**:
- [ ] `src/tasks/download_tasks.py` 文件已创建。
- [ ] `execute_download_task` 的逻辑已完整迁移，并被 `@celery_app.task` 装饰。

### 步骤 5.4: 改造 API 以派发任务 (高优先级)

**目标**: 让 API 端点变得轻快，只负责派发任务，不参与实际执行。

**任务**:
1.  打开 `src/api/routes/downloads.py`。
2.  从该文件中**彻底删除** `execute_download_task` 函数的定义。
3.  导入新的 Celery 任务：`from src.tasks.download_tasks import download_fund_report_task`。
4.  修改 `create_download_task` 函数的实现：
    ```python
    @router.post("", response_model=DownloadTaskCreateResponse, status_code=202)
    async def create_download_task(
        request: DownloadTaskCreateRequest,
        # 移除 BackgroundTasks
        task_service: DownloadTaskService = Depends(get_download_task_service)
    ) -> DownloadTaskCreateResponse:
        # ... (创建数据库任务记录的逻辑保持不变) ...
        await task_service.create_task(task)

        # 将原来的 add_task 修改为 delay
        download_fund_report_task.delay(task_id)

        return DownloadTaskCreateResponse(success=True, message="下载任务已创建", task_id=task_id)
    ```

**验收标准**:
- [ ] `downloads.py` 中的 `create_download_task` 不再使用 `BackgroundTasks`。
- [ ] `create_download_task` 现在通过调用 `.delay()` 来派发 Celery 任务。

### 步骤 5.5: 本地运行与验证

**目标**: 在本地完整地运行“API服务 + Celery Worker”构成的系统，并验证其功能。

**任务**:
1.  **启动 FastAPI 服务** (在第一个终端窗口中):
    ```bash
    D:\Users\LINSUISHENG034\anaconda3\envs\fund-scraper\python.exe -m uvicorn src.main:app
    ```
2.  **启动 Celery Worker** (在**第二个**终端窗口中):
    ```bash
    # 确保当前目录是项目根目录 F:\Projects\FundReportScraper
    D:\Users\LINSUISHENG034\anaconda3\envs\fund-scraper\python.exe -m celery -A src.core.celery_app worker --loglevel=info
    ```
3.  **执行功能验证**: 运行我们之前使用的 Python 测试脚本 (`run_phase4_test.py` 和 `step3_check_status.py`)，完成“搜索->创建->查询”的完整流程。

**验收标准**:
- [ ] FastAPI 服务和 Celery Worker 都能无错误地启动。
- [ ] 调用创建任务接口后，能在 Celery Worker 的终端窗口中看到任务被接收和执行的日志。
- [ ] 最终查询任务状态，其状态为 `COMPLETED`，进度为 100%。
- [ ] 数据库中成功写入了解析后的数据。

## 🚀 Phase 5 预期成果

完成本次升级后，我们的后端系统将达到一个全新的高度：
- ✅ **生产级架构**: 拥有了与大型互联网公司同款的、基于任务队列的分布式处理能力。
- ✅ **高可靠性**: 任务处理与 API 服务分离，API 的抖动不影响后台任务，反之亦然。
- ✅ **高可扩展性**: 未来可以通过增加 Worker 数量轻松应对更高的并发和负载。
- ✅ **彻底解��历史遗留问题**: 所有关于后台任务的会话管理、依赖注入和静默失败问题都将成为历史。

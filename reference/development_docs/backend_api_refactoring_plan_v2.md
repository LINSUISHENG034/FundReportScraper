# 后端重构实施计划 V2

**基于异步任务和RESTful设计的API架构演进指南**

## 📋 实施背景

我们已成功完成 **Phase 0 (架构解耦)** 和 **Phase 1 (核心模块集成)**。当前系统具备了以下坚实基础：

- ✅ **稳固的架构**: 统一的应用入口、清晰的服务层、简化的爬虫层和正确的依赖注入。
- ✅ **验证的核心功能**: 已通过集成测试验证了基于6个精确参数的报告搜索能力。
- ✅ **可靠的下载能力**: 解决了HTTP 302重定向问题，确保了文件可以被成功下载。

## 🎯 V2 实施目标

在现有功能正确性的基础上，**将API层从“一体化”调用模式重构为“任务分离”的异步任务模式**。设计并实现一套符合RESTful风格、对使用者友好、可扩展性强的生产级API接口。

## 💡 V2 设计原则

1.  **用户体验优先**: API的设计应充分考虑调用者的使用场景，避免长时等待和HTTP超时。
2.  **责任单一**: 每个API端点只做一件事（如“搜索”或“创建下载任务”），不做捆绑。
3.  **异步任务**: 对于耗时操作（如批量下载），采用“立即响应，后台执行”的异步任务模式。
4.  **状态可查**: 所有异步任务都必须提供一个查询其状态和进度的途径。

## 🏗️ 实施步骤

### Phase 2: API层重构 - 异步任务模式 (优先级：最高)

**目标**: 将API从简单的功能调用接口，升级为生产级的异步任务管理接口。

#### 2.1 设计思路：从“一体化”到“任务分离”

我们将把“搜索”和“下载”两个动作彻底解耦，使用者将通过三步完成一次完整的批量下载任务：

1.  **搜索**: 调用搜索接口，获取报告列表。
2.  **创建任务**: 从列表中选取需要下载的报告，调用下载接口创建一个后台下载任务。
3.  **查询状态**: 根据上一步返回的任务ID，轮询任务状态接口，获取实时进度。

#### 2.2 API端点设计 (v2)

**重新设计文件**: `src/api/routes/downloads.py` (新建), `src/api/routes/reports.py` (新建或重构)

**1. `GET /api/v1/reports` (搜索报告)**

-   **职责**: 强大的报告搜索功能，支持全参数筛选和分页。
-   **请求**: 使用**查询参数 (Query Parameters)** 接收所有6个搜索条件 (`year`, `report_type`, `fund_type`, `fund_company_short_name`, etc.)。
-   **响应 (成功)**: `200 OK`，返回带分页信息的JSON对象，其中`data`字段是一个报告列表。列表中的每个报告对象必须包含唯一的 `upload_info_id`。
    ```json
    {
      "success": true,
      "pagination": { "page": 1, "page_size": 20, "total_items": 6, "total_pages": 1 },
      "data": [
        { "upload_info_id": "...", "fund_code": "...", "fund_short_name": "...", ... },
        ...
      ]
    }
    ```

**2. `POST /api/v1/downloads` (创建批量下载任务)**

-   **职责**: 创建一个后台批量下载任务，**立即返回**，不执行实际下载。
-   **请求体 (Body)**: 接收一个包含多个 `upload_info_id` 的列表。
    ```json
    {
      "report_ids": ["...", "...", "..."],
      "save_dir": "data/my_downloads" 
    }
    ```
-   **核心逻辑**:
    1.  在数据库中创建一个新的 `DownloadTask` 记录，状态为 `PENDING`。
    2.  (未来) 将任务信息推送到 Celery 队列。
    3.  **立即返回 `202 Accepted`**，表示服务器已接受请求但尚未完成处理。
-   **响应 (成功)**: `202 Accepted`，返回包含新创建任务ID的JSON对象。
    ```json
    {
      "success": true,
      "message": "下载任务已创建",
      "task_id": "some-unique-task-uuid"
    }
    ```

**3. `GET /api/v1/downloads/{task_id}` (查询下载任务状态)**

-   **职责**: 根据任务ID获��特定下载任务的当前状态和进度。
-   **请求**: `task_id` 作为路径参数。
-   **响应 (成功)**: `200 OK`，返回任务的详细信息。
    ```json
    {
      "success": true,
      "task_status": {
        "task_id": "...",
        "status": "IN_PROGRESS",
        "created_at": "...",
        "progress": {
          "total": 50,
          "completed": 25,
          "failed": 2,
          "percentage": 50.0
        },
        "results": {
          "completed_ids": ["..."],
          "failed_ids": [{"id": "...", "error": "..."}]
        }
      }
    }
    ```

#### 2.3 Pydantic模型设计 (v2)

为新的API端点创建对应的输入（Request）和输出（Response）模型，确保类型安全和数据验证。

-   `ReportSearchResponse`
-   `DownloadTaskCreateRequest`
-   `DownloadTaskCreateResponse`
-   `DownloadTaskStatusResponse`

### Phase 3: 测试和验证 (V2)

**目标**: 确保新的API层功能正确，性能可靠。

-   **单元测试**: 为服务层中处理任务创建、状态更新的逻辑编写单元测试。
-   **集成测试**: 创建 `tests/integration/test_async_download_flow.py`，模拟完整的“搜索->创建任务->查询状态”流程。
-   **负载测试 (可选)**: 模拟高并发创建下载任务的场景。

## 📊 V2 实施检查清单

### Phase 2 检查项
- [ ] 创建新的API路由模块 (`reports.py`, `downloads.py`)。
- [ ] 实现 `GET /api/v1/reports` 搜索接口，并提供分页。
- [ ] 实现 `POST /api/v1/downloads` 任务创建接口，能正确创建数据库记录并返回 `202` 和 `task_id`。
- [ ] 实现 `GET /api/v1/downloads/{task_id}` 状态查询接口。
- [ ] 为新接口编写对应的 Pydantic 模型。
- [ ] (当前阶段) 下载逻辑可以在 `POST` 接口中通过 `BackgroundTasks` 临时实现，为未来迁移到 Celery 做准备。

### Phase 3 检查项
- [ ] 为新的API流程编写完整的集成测试。
- [ ] 验证端到端流程的数据一致性。

## 🚀 V2 预期成果

完成V2实施后，项目将具备：
- ✅ **生产级的API接口**: 清晰、解耦、符合RESTful规范。
- ✅ **异步任务处理能力**: 能够处理耗时操作而无需客户端长时间等待。
- ✅ **优秀的用户体验**: 调用者可以清晰地了解任务的创建、执行和结果。
- ✅ **强大的可扩展性**: 为未来引入消息队列（如Celery）和更复杂的任务管理功能奠定了完美的架构基础。

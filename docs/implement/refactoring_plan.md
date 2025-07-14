# 项目重构计划

## 1. 背景

当前项目已实现核心的XBRL报告下载与解析功能，但存在文档管理不善、模块错位、代码缺失等问题。为提升代码质量、可维护性和可扩展性，特制定本重构计划。

## 2. 重构目标

1.  **统一日志**：集成 `structlog`，实现结构化、可配置、路径统一的日志系统。
2.  **强化测试**：集成 `pytest`，为核心模块和API编写单元测试与集成测试，确保代码质量。
3.  **代码清理**：去除无意义的 "V2" 关键字，优化代码结构，提升可读性。
4.  **提升健壮性**：通过重构和测试，增强系统的稳定性和可靠性。

## 3. 代码审查发现

-   **日志系统**: `structlog` 已初步引入，但配置分散，未形成统一标准。
-   **V2 关键字**: 在API路由 (`reports_v2.py`) 和应用入口 (`main.py`) 中存在硬编码的 "V2"，应予以移除。
-   **测试缺失**: 项目完全没有自动化测试，这是重构过程中最大的风险点。
-   **配置管理**: `core/config.py` 提供了一个良好的基础，但可进一步整合日志等配置。
-   **代码结构**: 核心模块划分清晰，但依赖关系可以进一步解耦。

## 4. 重构实施计划

### 第一阶段：环境与基础架构搭建 (Setup Infrastructure)

**任务1：统一日志系统 (Integrate `structlog`)**

-   [ ] 在 `core/config.py` 中增加 `LoggingSettings`，管理日志级别、日志文件路径 (`logs/app.log`)、JSON格式开关等。
-   [ ] 重构 `core/logging.py`，使其从 `settings.logging` 读取配置，初始化 `structlog`。
-   [ ] 移除 `main.py` 中独立的 `configure_logging` 调用，改为在应用启动时统一配置。
-   [ ] 确保所有模块通过 `get_logger(__name__)` 获取的 logger 实例都遵循统一配置。
-   [ ] 创建 `logs` 目录，并将其添加到 `.gitignore` 文件中。

**任务2：集成测试框架 (Integrate `pytest`)**

-   [ ] 在 `pyproject.toml` 的 `[tool.poetry.group.dev.dependencies]` 中添加 `pytest`, `pytest-asyncio`, `httpx`。
-   [ ] 创建 `tests/` 目录。
-   [ ] 创建 `tests/conftest.py`，提供通用的测试固件 (fixtures)，如 `event_loop`, `async_client` 等。
-   [ ] 编写第一个单元测试 `tests/core/test_fund_search_parameters.py`，验证 `FundSearchCriteria` 的逻辑。

### 第二阶段：API 与核心逻辑重构 (Refactor API & Core Logic)

**任务3：去除 "V2" 关键字 (Remove "V2" Keyword)**

-   [ ] 将 `src/api/routes/reports_v2.py` 重命名为 `src/api/routes/reports.py`。
-   [ ] 修改 `src/api/routes/reports.py`：
    -   更新路由前缀：`APIRouter(prefix="/api/v1/reports", tags=["报告搜索"])`。
    -   移除响应模型和路由函数名中的 "V2"。
-   [ ] 修改 `src/main.py`：
    -   更新导入语句：`from src.api.routes import reports, downloads`。
    -   更新路由注册：`app.include_router(reports.router)`。
    -   更新 `downloads` 路由的 `tags` 为 `["下载任务"]`。

**任务4：API 接口测试**

-   [ ] 创建 `tests/api/test_reports_api.py`。
-   [ ] 编写测试用例，覆盖 `search_reports` 接口的各种场景：
    -   必填参数验证（年份、报告类型）。
    -   可选参数功能测试。
    -   分页参数测试。
    -   无效参数（如错误的报告类型）的异常处理测试。
-   [ ] 在测试中 Mock `FundReportService`，隔离服务层依赖。

### 第三阶段：服务与数据层优化 (Optimize Services & Data Layer)

**任务5：服务层与数据解析测试**

-   [ ] 创建 `tests/services/test_fund_report_service.py`，为 `FundReportService` 编写单元测试。
-   [ ] 创建 `tests/parsers/test_xbrl_parser.py`，为 `XBRLParser` 编写单元测试。
    -   准备多个真实的HTML报告样本文件，存放于 `tests/fixtures/reports/`。
    -   测试 `parse_file` 方法能否正确提取关键信息（基金代码、净值、持仓等）。

### 第四阶段：文档与清理 (Documentation & Cleanup)

**任务6：更新文档与代码清理**

-   [ ] 更新 `README.md`，说明如何运行测试、如何配置日志。
-   [ ] 全局搜索并移除所有 `print()` 调试语句。
-   [ ] 审查并删除重构后不再使用的代码或文件。

## 5. 风险评估与应对

-   **风险**: 在没有测试覆盖的情况下进行重构，容易引入新 Bug 或破坏现有功能。
-   **应对**: 严格遵循本计划，**先搭建测试框架并为即将修改的模块编写测试**，再进行重构。小步提交，频繁回归测试。
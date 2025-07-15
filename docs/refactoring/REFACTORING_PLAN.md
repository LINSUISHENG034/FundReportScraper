# 项目重构路线图 (Project Refactoring Roadmap)

本文档是项目重构工作的核心指导文件，旨在恢复代码的健康、可维护性和可扩展性。所有重构活动都必须严格遵循此路线图。

---

## 核心原则

1.  **原地重构 (In-Place Refactoring):** 在现有项目结构内进行重构，不进行大规模文件迁移。这可以保留 Git 历史，降低风险。
2.  **自下而上 (Bottom-Up Approach):** 从最底层的核心组件（Scraper, Parser）开始，逐层向上修复和测试，确保每一步都建立在可靠的基础之上。
3.  **测试驱动 (Test-Driven):** 所有重构必须由测试引导。先为现有功能编写测试以锁定其行为，然后进行修改，直至新代码通过所有测试。
4.  **遵循规范 (Adherence to Standards):** 严格遵循本文档中定义的技术栈和开发要求，特别是 `Structlog` 的使用和 `Pytest` 的测试覆盖率要求。

---

## 重构路线图 (Refactoring Roadmap)

### 阶段〇：环境与基准 (Environment & Baseline)

-   **负责人:** 首席开发 (Gemini)
-   **任务:**
    1.  **依赖审计:** 审查 `pyproject.toml`，确保 `structlog`, `pytest`, `pytest-cov`, `httpx`, `arelle` 等关键依赖已声明且版本适当。
    2.  **CI/CD 检查:** 审查 `.github/workflows/ci.yml`，确保自动化测试、Linting (代码风格检查) 流程已就位或可以被快速修复。
    3.  **初步分析:** 深入阅读 `src/scrapers/csrc_fund_scraper.py` 和 `src/parsers/xbrl_parser.py` 的现有代码，为阶段一的单元测试编写提供输入。
-   **产出:** 一份关于当前环境健康状况的评估，以及对核心模块代码的初步理解。

### 阶段一：核心组件单元测试与修复 (Unit Test & Fix Core Components)

-   **负责人:** 开发团队 (在首席开发指导下)
-   **任务 (可并行进行):**
    1.  **Scraper模块 (`csrc_fund_scraper.py`):**
        -   在 `tests/unit/` 创建 `test_csrc_fund_scraper.py`。
        -   **编写测试用例:** 模拟 `httpx` 的响应，覆盖成功、失败、超时、数据格式错误等场景。
        -   **修复代码:** 运行测试并修复 scraper，直至所有单元测试通过。
    2.  **Parser模块 (`xbrl_parser.py`):**
        -   在 `tests/unit/` 创建 `test_xbrl_parser.py`。
        -   在 `tests/fixtures/` 目录下准备真实的XBRL样本文件作为测试数据。
        -   **编写测试用例:** 测试 parser 能否正确解析样本文件并提取关键字段。
        -   **修复代码:** 运行测试并修复 parser，直至所有单元测试通过。
-   **产出:** 两个功能可靠、100% 经过单元测试验证的底层模块。

### 阶段二：服务层集成测试与修复 (Integration Test & Fix Service Layer)

-   **负责人:** 开发团队
-   **任务:**
    1.  在 `tests/integration/` 创建 `test_fund_report_service.py`。
    2.  **编写集成测试:** 测试 `fund_report_service.py` 能否正确调用 `Scraper` 和 `Parser`，完成“下载->解析->存储”的完整流程。此阶段需真实调用已修复的底层模块，但可以模拟数据库和文件存储的交互。
    3.  **修复代码:** 修复 `src/services/fund_report_service.py` 中的业务逻辑，确保其能正确协调底层模块。
-   **产出:** 一个通过集成测试、能正确串联核心工作流的服务层。

### 阶段三：Celery Worker 与下载模块重构 (Refactor Celery Worker & Download Module)

-   **负责人:** 开发团队 (在首席开发指导下)
-   **目标:** 将当前高度耦合、难以测试的下载任务，重构为一条清晰、健壮、可扩展的分布式任务流水线。
-   **核心方法论:**
    1.  **单一职责原则 (Single Responsibility Principle):** 每个模块和任务只做一件事。
    2.  **依赖倒置原则 (Dependency Inversion Principle):** 面向接口编程，而不是具体实现。
    3.  **任务链模式 (Task Chaining Pattern):** 使用 Celery Canvas 将大型任务分解为一系列小而专注的步骤。
-   **任务:**
    1.  **核心下载器抽象 (Downloader Abstraction):**
        -   在 `src/services/` 目录下创建新文件 `downloader.py`，定义一个只负责文件下载的 `Downloader` 类。
        -   `Downloader` 应包含完整的网络请求、错误处理和重试逻辑。
        -   为其编写独立的单元测试 `tests/unit/test_downloader.py`。
    2.  **服务层重构 (Service Layer Refactoring):**
        -   修改 `FundReportService`，为其注入新的 `Downloader` 依赖。
        -   剥离 `FundReportService` 的下载职责，使其专注于业务流程，并移除所有 `_sync` 后缀的模拟方法。
    3.  **Celery 任务分解与编排 (Task Decomposition & Orchestration):**
        -   重写 `src/tasks/download_tasks.py`。
        -   将巨型任务分解为多个原子任务：`download_single_report`, `parse_single_report`, `save_parsed_data`。
        -   使用 `celery.chord` 编排任务流，并创建一个 `finalize_batch_download` 回调任务来统一处理结果。
    4.  **错误处理与状态管理 (Error Handling & State Management):**
        -   在原子任务上配置 Celery 的自动重试机制 (`autoretry_for`)。
        -   利用 Celery 的内置状态传递，不再手动管理数据库中的任务状态。
-   **产出:** 一个具备高容错性、可水平扩展、职责清晰的后台任务处理系统。

### 阶段四：API层端到端测试与统一 (E2E Test & Unify API Layer)

-   **负责人:** 开发团队
-   **任务:**
    1.  在 `tests/integration/` 创建 `test_reports_api.py`。
    2.  **为v1和v2编写测试:** 分别为 `reports.py` 和 `reports_v2.py` 中的端点编写测试，锁定其现有行为。
    3.  **合并逻辑:** 将 `reports_v2.py` 的功能合并到 `reports.py` 中，消除冗余和 `_v2` 后缀。
    4.  **运行测试:** 确保合并后的 `reports.py` 能通过先前为v1和v2编写的所有测试。
    5.  **清理:** 确认无误后，安全删除 `src/api/routes/reports_v2.py` 文件。
-   **产出:** 一个接口统一、经过端到端测试的API层。

### 阶段五：全局标准化 (Global Standardization)

-   **负责人:** 开发团队
-   **任务:**
    1.  **日志系统:** 在 `src/core/logging.py` 中完成 `Structlog` 的最终配置。在整个 `src/` 目录中，用 `structlog` 调用替换所有 `print()` 和 `logging` 调用。
    2.  **代码风格:** 对整个项目运行 `black` 和 `flake8`，确保风格一致。
    3.  **最终验证:** 运行完整的测试套件 (`pytest --cov=src`)，检查最终的测试覆盖率，目标 >80%。
-   **产出:** 一个代码风格统一、日志记录规范、测试覆盖率达标的健康项目。

---

---

## 监控与验证 (Monitoring & Validation)

将通过以下方式监控重构进展：

-   **代码审查 (Code Review):** 审查每个阶段提交的 Pull Request，确保其符合本路线图的要求。
-   **CI/CD 报告:** 关注自动化流程的测试和覆盖率报告，将其作为阶段性成功的关键指标。
-   **定期同步:** 与团队进行简短的每日站会，沟通进度、识别障碍并确保方向正确。

# 重构计划：Phase 2 指导文档 - 服务层集成测试

**目标：** 为 `FundReportService` 编写一套全面的集成测试，锁定其现有核心功能，为下一阶段（Phase 3）的大规模重构建立安全基线。

**核心方法论：**
1.  **锁定行为 (Locking Behavior):** 我们不关心当前实现是否完美，只关心它的输入和输出。测试的目的是精确地记录下“当前它是如何工作的”。
2.  **依赖隔离 (Dependency Isolation):** 在测试中，我们将隔离外部依赖（特别是网络请求和数据库），使用 `pytest` 的 `monkeypatch` 和 `mocker` 功能来模拟 `Scraper` 和 `Parser` 的行为。
3.  **面向协定 (Contract-Oriented):** 测试应验证 `FundReportService` 是否遵守了其与外部调用者（API层）和内部依赖（Scraper层）之间的隐式“协定”。

---

## 任务列表

### 任务 2.1: 测试环境搭建

1.  **创建测试文件:**
    *   在 `tests/integration/` 目录下创建新文件 `test_fund_report_service.py`。

2.  **设置 `pytest` 夹具 (Fixtures):**
    *   在 `test_fund_report_service.py` 中，创建一个 `pytest` 夹具，用于提供一个被模拟（mocked）的 `CSRCFundReportScraper` 实例。
    *   这将允许我们在不发出真实API请求的情况下测试服务层。

    ```python
    # tests/integration/test_fund_report_service.py
    import pytest
    from unittest.mock import AsyncMock, MagicMock
    from src.services.fund_report_service import FundReportService
    from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper

    @pytest.fixture
    def mock_scraper():
        """提供一个被模拟的 Scraper 实例"""
        scraper = MagicMock(spec=CSRCFundReportScraper)
        scraper.search_reports = AsyncMock()
        scraper.download_xbrl_content = AsyncMock()
        return scraper

    @pytest.fixture
    def report_service(mock_scraper):
        """提供一个注入了模拟 Scraper 的服务实例"""
        return FundReportService(scraper=mock_scraper)
    ```

### 任务 2.2: 为 `search_reports` 方法编写测试

*   **目标:** 验证服务层能否正确处理来自 Scraper 的数据并将其格式化为标准的API响应。
*   **测试用例 `test_search_reports_success`:**
    1.  **安排 (Arrange):**
        *   定义一个 `FundSearchCriteria` 实例。
        *   定义一个模拟的 Scraper 返回数据（一个报告字典的列表）。
        *   设置 `mock_scraper.search_reports.return_value` 为上述模拟数据。
    2.  **行动 (Act):**
        *   调用 `await report_service.search_reports(criteria)`。
    3.  **断言 (Assert):**
        *   断言 `mock_scraper.search_reports` 被以正确的 `criteria` 参数调用了一次。
        *   断言返回结果的 `success` 字段为 `True`。
        *   断言返回结果的 `data` 字段与模拟数据一致。
        *   断言 `pagination` 和 `criteria` 字段被正确填充。

### 任务 2.3: 为 `download_report` 方法编写测试

*   **目标:** 验证服务层能否正确调用 Scraper 下载内容，并将其保存到本地文件系统。
*   **测试用例 `test_download_report_success`:**
    1.  **安排 (Arrange):**
        *   定义一个模拟的报告字典（包含 `uploadInfoId` 和 `fundCode`）。
        *   定义模拟的二进制文件内容（例如 `b"xbrl content"`）。
        *   设置 `mock_scraper.download_xbrl_content.return_value` 为上述模拟内容。
        *   使用 `pytest` 内置的 `tmp_path` 夹具来获取一个临时的、真实的目录路径。
    2.  **行动 (Act):**
        *   调用 `await report_service.download_report(report, tmp_path)`。
    3.  **断言 (Assert):**
        *   断言 `mock_scraper.download_xbrl_content` 被以正确的 `uploadInfoId` 调用。
        *   断言返回结果的 `success` 字段为 `True`。
        *   断言在 `tmp_path` 目录下成功创建了一个文件。
        *   读取该文件，断言其内容与模拟的二进制内容一致。

### 任务 2.4: 为 `batch_download` 方法编写测试

*   **目标:** 验证服务层能否正确地并发执行多个下载任务，并准确统计结果。
*   **测试用例 `test_batch_download_mixed_results`:**
    1.  **安排 (Arrange):**
        *   创建两个模拟报告字典。
        *   使用 `monkeypatch` 或 `mocker` 来替换 `FundReportService.download_report` 方法。
        *   让被替换的方法在第一次调用时返回成功字典，在第二次调用时返回失败字典。
    2.  **行动 (Act):**
        *   调用 `await report_service.batch_download(reports, tmp_path)`。
    3.  **断言 (Assert):**
        *   断言返回结果的 `success` 字段为 `True`（批处理本身是成功的）。
        *   断言 `statistics` 字典中的 `total` 为 2，`success` 为 1，`failed` 为 1。
        *   断言 `results` 列表包含一个成功的结果和一个失败的结果。

---

### **验收标准 (Acceptance Criteria)**

1.  `tests/integration/test_fund_report_service.py` 文件被创建并包含上述所有测试用例。
2.  所有测试用例都必须通过 `pytest` 执行，不得有任何失败。
3.  测试覆盖率 (`pytest --cov=src/services/fund_report_service.py`) 显著提升，为后续重构提供保障。

完成以上任务后，`FundReportService` 的行为将被一套可靠的集成测试“锁定”，为 Phase 3 的重构工作铺平道路。

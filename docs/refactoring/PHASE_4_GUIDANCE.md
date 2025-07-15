# 重构计划：Phase 4 指导文档 - API 层测试与统一

**目标：** 消除 API 层的代码冗余，为核心搜索接口建立端到端的测试覆盖，确保其稳定性和可靠性。

**核心发现：** 经过审查，`src/api/routes/reports_v2.py` 是 `reports.py` 的一个精确副本，不存在任何功能差异。因此，本阶段的任务是**代码清理**而非功能合并。

---

## 任务列表

### 任务 4.1: 为 `reports.py` 编写集成测试

*   **目的：** 为现有的 v1 API 建立一个坚实的测试安全网。这是删除冗余代码前的必要前提。

1.  **创建测试文件:**
    *   在 `tests/integration/` 目录下创建新文件 `test_reports_api.py`。

2.  **编写测试用例:**
    *   使用 `fastapi.testclient.TestClient` 来模拟对 API 的真实请求。
    *   测试必须覆盖以下场景：
        *   **成功搜索：**
            *   只使用必填参数 (`year`, `report_type`) 进行一次成功的搜索。
            *   使用所有可选参数进行一次成功的搜索。
        *   **参数校验：**
            *   提供一个无效的 `report_type`，断言 API 返回 400 错误。
            *   提供一个无效的 `fund_type`，断言 API 返回 400 错误。
            *   提供一个无效的日期范围（开始日期晚于结束日期），断言 API 返回 400 错误。
        *   **辅助端点：**
            *   测试 `GET /api/reports/types` 端点，断言其成功返回且数据结构正确。
            *   测试 `GET /api/reports/fund-types` 端点，断言其成功返回且数据结构正确。

3.  **测试代码示例:**

    ```python
    # tests/integration/test_reports_api.py
    from fastapi.testclient import TestClient
    from src.main import app  # 假设你的FastAPI实例在main.py中

    client = TestClient(app)

    def test_search_reports_success():
        """测试基本搜索成功"""
        response = client.get("/api/reports?year=2024&report_type=FB010010")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "pagination" in data

    def test_search_reports_invalid_report_type():
        """测试无效的报告类型"""
        response = client.get("/api/reports?year=2024&report_type=INVALID_TYPE")
        assert response.status_code == 400
        assert "无效的报告类型" in response.json()["detail"]

    # ... 其他测试用例 ...
    ```

---

### 任务 4.2: 清理冗余代码

*   **目的：** 移除重复的 v2 API，统一代码库。

1.  **删除文件:**
    *   在确保 `test_reports_api.py` 中的所有测试都通过后，**安全地删除** `src/api/routes/reports_v2.py` 文件。

2.  **更新主应用:**
    *   打开 `src/main.py` 文件。
    *   找到包含 `from src.api.routes import reports_v2` 的行并**删除它**。
    *   找到包含 `app.include_router(reports_v2.router)` 的行并**删除它**。

---

### 任务 4.3: 最终验证

*   **目的：** 确保清理工作没有对系统造成任何破坏。

1.  **再次运行测试:**
    *   在完成代码清理后，再次运行完整的 `pytest` 测试套件。
    *   **必须确保所有测试仍然通过。**

---

### **验收标准 (Acceptance Criteria)**

1.  `tests/integration/test_reports_api.py` 被创建，并包含对 `reports.py` 端点的充分测试。
2.  `src/api/routes/reports_v2.py` 文件被**彻底删除**。
3.  `src/main.py` 不再包含任何对 `reports_v2` 的引用。
4.  在完成所有修改后，项目完整的 `pytest` 测试套件**必须 100% 通过**。

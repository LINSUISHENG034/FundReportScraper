# 任务：重构 Parser 模块 (`src/parsers/xbrl_parser.py`)

**目标：** 开发一个健壮、精确、可维护的HTML报告解析器，并通过严格的单元测试来保证其质量。

**核心方法论：** 测试驱动开发 (TDD)

---

### **第一部分：重写单元测试 (`tests/unit/test_xbrl_parser.py`)**

这是重构的第一步，也是最重要的基础。我们将先定义“成功”的标准。

*   **任务 1.1：清理旧测试**
    *   删除 `test_xbrl_parser.py` 中所有现存的 `test_*` 函数。我们从一张白纸开始。

*   **任务 1.2：定义期望数据结构**
    *   为 `tests/fixtures/` 目录中的**至少5个**有代表性的报告文件，手动创建精确的“期望结果”数据。
    *   选择的样本应覆盖不同报告类型，例如：
        *   `013060_ANNUAL_1752537343.xbrl` (年报)
        *   `004899_2025Q1_1752539409.xbrl` (季报)
        *   `003016_SEMI_ANNUAL_1752539909.xbrl` (半年报)
        *   另外选择 2-3 个其他文件以确保多样性。
    *   为每个文件创建一个 `expected_data` 字典，其结构应与 `ParsedFundData` 模型一致。**示例如下：**

    ```python
    # tests/unit/test_xbrl_parser.py

    from decimal import Decimal
    from datetime import date

    # 示例：为 013060_ANNUAL_1752537343.xbrl 创建的期望数据
    expected_data_013060 = {
        "fund_code": "013060",
        "fund_name": "国投瑞银招财混合A",
        "report_period_end": date(2024, 12, 31),
        "net_asset_value": Decimal("1.1088"),
        "total_net_assets": Decimal("25888441.88"),
        "top_holdings_count": 10,
        "first_top_holding_name": "贵州茅台", # 假设第一个重仓股是这个
        "asset_allocations_count": 5, # 假设有5类资产配置
        # ... 其他需要精确验证的核心字段
    }

    # ... 为其他4个以上的文件创建类似的期望数据字典
    ```

*   **任务 1.3：实现参数化测试 (`parametrize`)**
    *   创建唯一的测试函数 `test_parse_fund_report_fully()`。
    *   使用 `@pytest.mark.parametrize` 为上述每个样本文件及其对应的 `expected_data` 创建一个测试实例。

    ```python
    # tests/unit/test_xbrl_parser.py
    import pytest
    from pathlib import Path
    # ...

    FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"

    @pytest.mark.parametrize(
        "filename, expected_data",
        [
            ("013060_ANNUAL_1752537343.xbrl", expected_data_013060),
            # ... 为其他文件添加条目
        ]
    )
    def test_parse_fund_report_fully(parser, filename, expected_data):
        # 任务1.4 将在这里实现
        pass
    ```

*   **任务 1.4：编写精确断言**
    *   在 `test_parse_fund_report_fully` 函数体内，完成以下逻辑：
        1.  调用 `parser.parse_file()`。
        2.  **必须** 使用 `assert` 对返回结果的关键字段与 `expected_data` 中的值进行**精确比较**。
        3.  断言应覆盖：
            *   核心字段 (e.g., `assert result.fund_code == expected_data["fund_code"]`)。
            *   列表长度 (e.g., `assert len(result.top_holdings) == expected_data["top_holdings_count"]`)。
            *   列表内具体内容 (e.g., `assert result.top_holdings[0]['security_name'] == expected_data["first_top_holding_name"]`)。

    *   此时运行测试，它**应该会失败**。这是 TDD 的正常步骤。

---

### **第二部分：重构解析器 (`src/parsers/xbrl_parser.py`)**

现在，我们的目标是修改解析器代码，让上面定义的严格测试**全部通过**。

*   **任务 2.1：废弃旧逻辑**
    *   删除或重构所有依赖“在整个文档文本上跑正则”的解析方法。

*   **任务 2.2：实现智能表格解析器**
    *   这是本次重构的**技术核心**。创建一个通用的、可复用的表格解析辅助函数，例如 `_parse_table_with_smart_header(table_tag, column_mappings)`。
    *   **步骤 A - 动态表头映射**：
        *   该函数必须先找到表头行 (`<th>` 标签）。
        *   遍历表头单元格，创建一个“列名 -> 列索引”的字典。例如 `{'证券代码': 0, '证券名称': 1, ...}`。
        *   这个映射必须是灵活的，能处理列顺序变化。
    *   **步骤 B - 识别别名**：
        *   `column_mappings` 参数应支持别名，例如 `{'security_name': ['证券名称', '股票名称'], 'market_value': ['公允价值', '市值(元)']}`。解析时，任何一个别名都应被识别。
    *   **步骤 C - 按名提取**：
        *   遍历数据行 (`<td>` 标签)。
        *   使用上一步生成的“列名 -> 列索引”字典来准确提取数据，**严禁使用硬编码的列索引**（如 `cells[1]`）。
    *   **步骤 D - 返回结构化数据**：
        *   函数应返回一个字典列表，例如 `[{'security_name': '贵州茅台', 'market_value': Decimal('10000')}, ...]`。

*   **任务 2.3：应用智能解析器**
    *   重构 `_parse_top_holdings`, `_parse_asset_allocation`, `_parse_industry_allocation` 等方法，让它们调用新建的 `_parse_table_with_smart_header` 辅助函数来完成工作。

*   **任务 2.4：迭代修复**
    *   反复运行 `pytest`。根据失败的断言，逐步调试和完善解析器逻辑，直到第一批（5个）测试用例全部通过。

---

### **第三部分：验收与完成**

*   **任务 3.1：扩大测试覆盖**
    *   为 `tests/fixtures/` 中更多的文件（建议至少再增加5个）补充 `expected_data` 和 `parametrize` 条目，并确保它们也能通过测试。

*   **任务 3.2：代码清理**
    *   移除代码中所有的 `print()` 调试语句。
    *   确保代码有清晰的注释和文档字符串。
    *   运行 `black` 和 `flake8` 确保代码风格一致。

### **验收标准 (Acceptance Criteria)**

**当且仅当以下所有条件都满足时，Phase 1 重构任务才被视为最终完成：**

1.  `test_xbrl_parser.py` 中**不存在**循环遍历文件、缺乏精确断言的旧测试。
2.  `test_xbrl_parser.py` **必须**使用 `@pytest.mark.parametrize` 对**至少10个**以上不同的样本文件进行测试。
3.  每一个参数化测试实例都**必须**有精确的、非空的 `expected_data`，并对返回结果进行严格断言。
4.  `xbrl_parser.py` 中的表格解析逻辑**必须**基于动态的、智能的表头识别，**严禁**任何固定列索引的使用。
5.  最终提交的代码**必须 100% 通过** `pytest` 测试，不得有任何失败或跳过的用例。
6.  代码中**不得包含**任何用于调试的 `print` 语句。

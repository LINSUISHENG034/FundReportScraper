# 重构阶段一：核心组件单元测试与修复 - 技术指导

**负责人:** 开发团队
**总指导:** Gemini

---

本文档为重构路线图的 **阶段一** 提供详细的技术实施指导。开发团队应严格遵循此文档来完成对 `Scraper` 和 `Parser` 两个核心模块的单元测试与修复工作。

## 1. Scraper 模块 (`src/scrapers/csrc_fund_scraper.py`)

### 1.1 目标

通过编写全面的单元测试，确保 `CSRCFundReportScraper` 能够稳定、可靠地构建API请求并解析响应。测试必须完全独立于外部网络。

### 1.2 测试文件

-   **创建文件:** `tests/unit/test_csrc_fund_scraper.py`

### 1.3 核心测试任务

#### 1.3.1 测试 `_build_ao_data` 方法 (最重要)

此方法是请求逻辑的核心。必须保证它能精确生成API所需的 `aoData` 结构。

-   **策略:** 直接调用该私有方法，断言其返回值。
-   **测试用例:**
    -   测试基础调用（年份、报告类型）。
    -   测试所有可选参数（基金代码、公司名称等）被正确填充。
    -   测试分页参数 (`page`, `page_size`) 是否正确计算了 `iDisplayStart` 和 `iDisplayLength`。
    -   测试特殊报告类型（如 `FUND_PROFILE`）是否正确处理了 `reportYear` 字段（应为空）。

```python
# 示例 (在 tests/unit/test_csrc_fund_scraper.py 中)
from src.scrapers.csrc_fund_scraper import CSRCFundReportScraper
from src.core.fund_search_parameters import ReportType

def test_build_ao_data_pagination():
    scraper = CSRCFundReportScraper()
    # 调用私有方法进行测试
    ao_data = scraper._build_ao_data(year=2024, report_type=ReportType.ANNUAL, page=3, page_size=50)
    
    display_start = next((item for item in ao_data if item['name'] == 'iDisplayStart'), None)
    display_length = next((item for item in ao_data if item['name'] == 'iDisplayLength'), None)
    
    assert display_start is not None
    assert display_start['value'] == 100  # (3 - 1) * 50
    assert display_length is not None
    assert display_length['value'] == 50
```

#### 1.3.2 测试 `get_report_list` 方法

-   **策略:** 使用 `pytest-mock` 的 `mocker` 来模拟 `httpx.AsyncClient` 的行为。
-   **测试用例:**
    -   **成功场景:**
        -   模拟 `response.json()` 返回一个包含 `aaData` 和 `iTotalRecords` 的字典。
        -   断言方法返回的报告列表长度和内容正确。
        -   断言 `has_next_page` 标志在不同 `iTotalRecords` 下的计算正确。
    -   **失败场景:**
        -   模拟 `httpx` 抛出异常 (如 `httpx.RequestError`)，断言 `get_report_list` 会捕获并抛出自定义的 `ParseError`。
        -   模拟 API 返回非200状态码。
        -   模拟 API 返回无效的JSON数据。

```python
# 示例
import pytest
from httpx import Response, RequestError
from src.scrapers.base import ParseError

@pytest.mark.asyncio
asnyc def test_get_report_list_success(mocker):
    # 准备模拟数据
    mock_response_json = {
        "iTotalRecords": 1,
        "aaData": [
            {"uploadInfoId": "123", "fundCode": "000001", ...}
        ]
    }
    # 模拟 AsyncClient 的 get 方法
    mock_get = mocker.patch("httpx.AsyncClient.get", return_value=Response(200, json=mock_response_json))
    
    scraper = CSRCFundReportScraper(session=httpx.AsyncClient())
    reports, has_next = await scraper.get_report_list(2024, ReportType.ANNUAL)
    
    assert len(reports) == 1
    assert reports[0]['fund_code'] == "000001"
    assert not has_next

@pytest.mark.asyncio
asnyc def test_get_report_list_http_error(mocker):
    mocker.patch("httpx.AsyncClient.get", side_effect=RequestError("Connection failed"))
    scraper = CSRCFundReportScraper(session=httpx.AsyncClient())
    
    with pytest.raises(ParseError, match="获取报告列表失败"):
        await scraper.get_report_list(2024, ReportType.ANNUAL)
```

#### 1.3.3 测试 `download_xbrl_content` 方法

-   **策略:** 与上面类似，模拟 `httpx.AsyncClient.get` 的行为。
-   **测试用例:**
    -   **成功场景:** 模拟 `get` 方法返回一个包含文件内容的 `Response` 对象 (`response.content`)。断言方法返回正确的字节流。
    -   **失败场景:** 模拟404或500错误，断言方法会抛出异常。

---

## 2. Parser 模块 (`src/parsers/xbrl_parser.py`)

### 2.1 目标

确保 `XBRLParser` (实际上是HTML解析器) 能够从真实的、多样化的HTML报告样本中准确提取所有需要的数据字段。

### 2.2 测试文件

-   **创建文件:** `tests/unit/test_xbrl_parser.py`

### 2.3 核心测试任务

#### 2.3.1 准备测试数据 (关键步骤)

-   **位置:** `tests/fixtures/`
-   **要求:**
    1.  下载至少 **3-5份** 不同基金公司、不同报告类型（年报、Q1季报、半年报）的真实HTML报告文件。
    2.  将这些文件命名为易于识别的名称，例如 `fund_A_2023_annual.html`, `fund_B_2024_q1.html`。
    3.  确保这些样本文件包含了所有需要解析的表格：资产配置、前十大持仓、行业分布。

#### 2.3.2 测试 `parse_file` 方法

-   **策略:** 这是对解析器的端到端测试。使用 `pytest.mark.parametrize` 为每个 fixture 文件创建一个测试用例。
-   **测试用例:**
    -   针对每一个 `fixture` 文件，调用 `parser.parse_file()`。
    -   对返回的 `ParsedFundData` 对象的**每一个重要字段**进行精确断言。

```python
# 示例 (在 tests/unit/test_xbrl_parser.py 中)
import pytest
from pathlib import Path
from decimal import Decimal
from src.parsers.xbrl_parser import XBRLParser

FIXTURE_DIR = Path(__file__).parent.parent / 'fixtures'

@pytest.mark.parametrize(
    "filename, expected_code, expected_nav, expected_holdings_count",
    [
        ("fund_A_2023_annual.html", "000123", Decimal("1.2345"), 10),
        ("fund_B_2024_q1.html", "543210", Decimal("2.5432"), 10),
        # ... 为每个 fixture 文件添加一行
    ]
)
def test_parse_fund_reports(filename, expected_code, expected_nav, expected_holdings_count):
    file_path = FIXTURE_DIR / filename
    parser = XBRLParser()
    
    result = parser.parse_file(file_path)
    
    assert result is not None
    assert result.fund_code == expected_code
    assert result.net_asset_value == expected_nav
    assert len(result.top_holdings) == expected_holdings_count
    # ... 对其他关键字段进行断言
```

#### 2.3.3 测试健壮性

-   **测试用例:**
    -   测试传入一个不存在的文件路径时，`parse_file` 返回 `None`。
    -   创建一个空的 fixture 文件，测试 `parse_file` 能处理这种情况而不会崩溃。

### 2.4 修复与重构

在运行测试后，几乎可以肯定当前简化的表格解析逻辑会失败。开发团队需要：

1.  **分析失败的测试:** 仔细查看是哪个 fixture 文件、哪个字段的解析出了问题。
2.  **改进解析逻辑:** 增强 `_extract_*_from_table` 方法。可能需要更智能地识别表头（`<th>`），然后根据表头来定位数据列，而不是依赖固定的列索引。
3.  **迭代:** **修复 -> 运行测试 -> 修复**，直到所有测试用例都通过。

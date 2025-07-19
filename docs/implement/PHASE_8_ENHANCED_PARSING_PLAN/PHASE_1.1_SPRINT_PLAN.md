# `ArelleParser` 阶段1.1 精确冲刺开发指南

**核心目标**：彻底解决“核心数据映射缺失”与“元数据硬编码”两大问题，使`ArelleParser`能够完整、准确地解析出一份财报的核心投资组合数据。

---

### **开发者须知**

**重要提示**：本指南中所有的XBRL元素编码均来源于`reference/XBRL分类标准框架/模板最新版本/`目录下的官方技术规范文档。如果在实际解析过程中遇到编码不匹配、维度无法解析等问题，请**务必**第一时间查阅该目录下的原始文档，以官方定义为准。这些文档是解决解析歧义的最终依据。

---

### **任务一：重构`concept_mappings`，使用精确编码**

**说明**: 当前的映射规则基于模糊的文本匹配，既不高效也不可靠。我们必须切换到基于官方文档的精确编码进行映射。

**行动**:
请开发团队使用以下精确编码重构`src/parsers/arelle_parser.py`中的`self.concept_mappings`字典。

```python
# 建议的重构后映射字典
self.concept_mappings = {
    # §2.1 基金基本情况
    "fund_code": ["0012"],
    "fund_name": ["0009", "0011"], # 基金名称, 基金简称
    "fund_manager": ["0186"],

    # §3.1 主要财务指标
    "net_asset_value": ["0506"], # 期末基金份额净值
    "total_net_assets": ["0505"], # 期末基金资产净值
    "period_profit": ["0497"], # 本期利润

    # §4.1 报告元数据 (从文档页眉和标题推断)
    "report_period_start": ["2023"], # 报告期开始 (注意: 这是文档中的占位符, 实际XBRL标签可能为 dei:DocumentPeriodStartDate)
    "report_period_end": ["2024"], # 报告期结束 (注意: 这是文档中的占位符, 实际XBRL标签可能为 dei:DocumentPeriodEndDate)
    "report_type_name": ["0002"], # 报告名称, 如 "XXXX证券投资基金XXXX年第X季度报告"

    # §8.1 期末基金资产组合情况 (大类资产配置)
    "asset_equity": ["1051"], # 权益投资-股票
    "asset_bond": ["1063"], # 固定收益投资-债券
    "asset_cash": ["1086"], # 银行存款和结算备付金合计
    "asset_total": ["1090"], # 合计

    # §8.2 按行业分类的股票投资组合
    "industry_table": "Table-8.2", # 自定义标识符，用于触发特定表格解析逻辑
    "industry_name": [], # 留空，因为行业名称是维度信息，不是事实
    "industry_fair_value": list(range(1100, 1170, 2)) + [2968, 2971, 2974, 2977, 2980, 2983, 2986, 2989, 2992, 2995, 2998, 3001, 3004, 3007, 3010, 3013], # 所有行业的公允价值编码
    "industry_percentage": list(range(1101, 1171, 2)) + [2969, 2972, 2975, 2978, 2981, 2984, 2987, 2990, 2993, 2996, 2999, 3002, 3005, 3008, 3011, 3014], # 所有行业的净值比例编码

    # §8.3 前十名股票投资明细
    "holdings_table": "Table-8.3.1", # 自定义标识符
    "holding_rank": ["1375"],
    "holding_code": ["1376"],
    "holding_name": ["1379"],
    "holding_shares": ["1382"],
    "holding_fair_value": ["1383"],
    "holding_percentage": ["1384"],
}
```

### **任务二：实现基于上下文（Context）的表格数据解析**

**说明**: 投资组合（持仓、行业分配）在XBRL中是以表格（Table）和维度（Dimension）的形式存在的。同一行的数据（如一支股票的代码、名称、市值）会共享一个相似的`contextID`。我们必须实现逻辑来分组和重构这些行项目。

**行动**:
1.  **修改`_map_facts_to_report`**: 在主映射函数中，识别出属于表格的数据。可以检查事实的`contextID`是否包含特定的维度信息来触发不同的解析逻辑。

2.  **实现`_map_top_holdings`**:
    *   **目标**: 解析"§8.3.1 前十名股票投资明细"。
    *   **逻辑**:
        1.  创建一个空字典 `holdings_by_row = {}`。
        2.  遍历所有Arelle事实（facts）。
        3.  如果一个事实的`concept`是持仓相关编码（`1376`, `1379`, `1382`, `1383`, `1384`），从其`contextID`中提取出唯一的行标识符（通常是contextID中的序列号或维度成员）。
        4.  使用此行标识符作为`holdings_by_row`的键，将事实的值存入对应的行数据字典中。例如：`holdings_by_row['row_1']['security_code'] = 'xxxxxx'`。
        5.  遍历完成后，`holdings_by_row`字典的每一个值都是一个完整的行项目。
        6.  将`holdings_by_row`中的每个行项目字典转换为一个`HoldingData`模型实例。
    *   **返回**: `List[HoldingData]`

3.  **实现`_map_industry_allocations`**:
    *   **目标**: 解析"§8.2 报告期末按行业分类的境内股票投资组合"。
    *   **逻辑**:
        1.  此表格的结构是“代码-行业类别-公允价值-占比”。在XBRL中，"行业类别"本身是一个维度。
        2.  遍历所有事实，当`concept`是行业公允价值编码（如`1100`）或占比编码（如`1101`）时，从`contextID`中提取出行业维度信息（如`IndustryDimension=制造业`）。
        3.  根据行业维度信息来聚合数据，将同一行业的公允价值和占比数据组合起来。
        4.  将聚合后的数据转换为`IndustryAllocationData`模型实例。
    *   **返回**: `List[IndustryAllocationData]`

4.  **实现`_map_asset_allocations`**:
    *   **目标**: 解析"§8.1 期末基金资产组合情况"。
    *   **逻辑**: 这是一个简单的键值对表格，可以直接根据编码（`1051`, `1063`, `1086`）查找对应的值，并填充到`AssetAllocationData`模型中。
    *   **返回**: `List[AssetAllocationData]`

### **任务三：动态解析报告元数据**

**说明**: 必须消除所有关于报告元数据的硬编码。

**行动**:
1.  **修改`_map_metadata`**:
    *   查找`concept`为`2024`（或`dei:DocumentPeriodEndDate`）的事实，解析其`value`作为`report_period_end`。
    *   查找`concept`为`2023`（或`dei:DocumentPeriodStartDate`）的事实，解析其`value`作为`report_period_start`。
    *   查找`concept`为`0002`的事实，根据其`value`（如“2024年第2季度报告”）通过关键词匹配（"年度"、"中期"、"季度"）来动态确定`ReportType`。

---

### **最终验收标准（修订版）**

阶段1.1被视为完成，当且仅当：
1.  `arelle_parser.py`中的`concept_mappings`已全部更新为精确的数字编码。
2.  `_map_top_holdings`, `_map_industry_allocations`, `_map_asset_allocations`方法已实现，并通过单元测试验证能够正确解析表格数据。
3.  `_map_metadata`方法能够从XBRL事实中动态解析报告期和报告类型，无任何硬编码。
4.  **演示**：开发负责人需能现场演示，使用`tests/fixtures/`中的一个XBRL文件，通过`ArelleParser`解析后，打印出的`ComprehensiveFundReport`对象**完整且准确地**包含了其所有的资产配置、前十大持仓、行业配置信息，并且报告元数据与源文件完全一致。

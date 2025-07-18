# 阶段一：基础建设 - 详细任务列表 (Phase 1: Foundational Components)

**目标**: 搭建新解析引擎的核心骨架，实现对XBRL分类标准和报告上下文的程序化理解能力。本阶段不要求完成端到端的数据提取，但需为后续阶段打下坚实的基础。

**预计周期**: 2个工作日

---

### **任务 1.1: `TaxonomyManager` (分类标准管理器) 的设计与实现**

- **负责人**: 开发团队A
- **目标**: 创建一个能够加载并查询XBRL分类标准元数据的服务。
- **详细要求**:
    1.  **初始化**: 类在初始化时，应能接收分类标准所在的根目录路径（`reference/XBRL分类标准框架/`）。
    2.  **加载功能**: 实现一个 `load_taxonomy()` 方法，该方法能递归扫描指定目录下的所有 `.xsd` 文件，并使用XML解析库（推荐 `lxml`）解析它们。
    3.  **数据结构**: 将解析出的元素（`xs:element`）存储在内存中的一个字典里，键为元素的 `id` 或 `name` 属性（如 `cfi:FinancialAssetsAtFairValueThroughProfitOrLoss`），值为一个包含其元数据的对象或字典。
    4.  **元数据提取**: 至少需要提取每个元素的以下信息：
        - `id`: 唯一标识符。
        - `name`: 元素名称。
        - `type`: 数据类型（如 `xbrli:monetaryItemType`）。
        - `substitutionGroup`: 替换组，用于理解元素关系。
        - `abstract`: 是否为抽象元素。
        - **(关键)** `label`: 从关联的标签文件 (`*_lab.xml`) 中提取该元素对应的中文标签（如“交易性金融资产”）。
    5.  **查询接口**: 提供一个 `get_element_details(element_id: str) -> Optional[Dict]` 方法，根据元素ID返回其所有元数据。
- **验收标准**:
    - 能够成功加载 `reference/XBRL分类标准框架/` 目录下的所有 `.xsd` 文件而不抛出异常。
    - 调用 `get_element_details('cfi:Assets')` 能返回包含其`id`, `name`, `type`, `label`（“资产总计”）等信息的完整数据。
    - 单元测试覆盖率不低于90%。

---

### **任务 1.2: `XBRLContext` (XBRL上下文解析器) 的设计与实现**

- **负责人**: 开发团队B
- **目标**: 创建一个能够解析XBRL报告中所有上下文（`context`）并提供查询功能。
- **详细要求**:
    1.  **输入**: 模块应能接收一个已解析的 `BeautifulSoup` 或 `lxml` 对象作为输入。
    2.  **上下文提取**: 遍历文档，找到所有的 `<xbrli:context>` 元素。
    3.  **数据结构**: 将每个 `context` 的信息存储在一个字典中，键为 `context` 的 `id` 属性值（如 `c-1`），值为一个包含其详细信息的对象或字典。
    4.  **信息解析**: 必须精确解析出每个 `context` 中的以下信息：
        - `entity`: 报告实体，特别是 `identifier`（基金代码）。
        - `period`: 报告期间，需要能处理 `instant`（瞬时）和 `duration`（时段，包含 `startDate` 和 `endDate`）两种情况。
        - `scenario`: 场景信息，特别是包含 `explicitMember` 的维度信息（这在后续阶段解析表格数据时至关重要）。
    5.  **查询接口**: 提供一个 `get_context_details(context_id: str) -> Optional[Dict]` 方法，根据上下文ID返回其所有解析后的信息。
- **验收标准**:
    - 能够正确解析 `tests/fixtures/` 中任一年度报告样本的所有 `context` 元素。
    - 调用 `get_context_details` 查询一个表示年度报告的 `context` ID，能准确返回基金代码和正确的起止日期。
    - 单元测试覆盖率不低于90%。

---

### **任务 1.3: `FactExtractor` (事实提取器) 的设计与实现**

- **负责人**: 开发团队C
- **目标**: 创建一个能够从XBRL报告中提取所有事实（Facts）的工具。
- **详细要求**:
    1.  **输入**: 模块应能接收一个已解析的 `BeautifulSoup` 或 `lxml` 对象作为输入。
    2.  **事实识别**: 遍历文档，识别所有包含 `contextRef` 属性的XML标签。这些就是“事实”。
    3.  **数据结构**: 返回一个事实列表，列表中的每个元素都是一个包含该事实所有信息的对象或字典。
    4.  **信息提取**: 对于每个事实，必须提取以下信息：
        - `name`: 事实的标签名（如 `cfi:Assets`）。
        - `value`: 事实的文本值。
        - `contextRef`: 关联的上下文ID。
        - `unitRef`: 关联的单位ID（如 `CNY`）。
        - `decimals`: 数值的精度。
- **验收标准**:
    - 能够提取出 `tests/fixtures/` 中任一年度报告样本的所有事实，数量应与文件中带有 `contextRef` 的标签数一致。
    - 提取出的事实列表中，每个事实都包含 `name`, `value`, `contextRef`, `unitRef` 等关键属性。
    - 单元测试覆盖率不低于90%。

---

### **阶段一交付成果**:
- 三个功能完整、经过充分测试的基础Python模块 (`taxonomy_manager.py`, `xbrl_context.py`, `fact_extractor.py`)。
- 完整的单元测试套件。
- 一份简要的API文档，说明如何使用这三个模块。

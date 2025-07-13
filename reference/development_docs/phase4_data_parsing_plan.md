# Phase 4 开发计划：核心业务逻辑与数据解析

**目标：从原始报告文件中提取、解析并持久化核心业务数据，实现平台的真正价值。**

## 📋 Phase 3 成果回顾

我们已成功构建了一个稳定、可靠的后端基础设施，具备以下能力：
- ✅ **生产级的API**: 提供“搜索、创建、查询”的异步任务流程。
- ✅ **可靠的下载能力**: 能够稳定地获取基金报告的原始文件。
- ✅ **持久化的任务管理**: 所有下载任务的状态都被可靠地存储在数据库中。

## 🎯 Phase 4 核心目标

将平台从一个“文件下载器”升级为一个“数据引擎”。我们将聚焦于从已下载的 XBRL/HTML 文件中提取关键信息，并将其结构化地存入数据库，为后续的数据分析和前端展示提供弹药。

## 💡 设计原则

1.  **模型驱动**: 数据模型（Schema）是核心，应优先设计和评审。
2.  **职责分离**: 解析逻辑（Parser）、存储逻辑（Service）和任务流程（Flow）应严格分离。
3.  **可扩展性**: 解析器应能方便地扩展，以支持未来可能出现的新报告格式或数据项。
4.  **幂等性与重试**: 数据处理流程应具备幂等性，重复处理同一个文件不应产生副作用（如重复数据）。

## 🏗️ 实施步骤

### 步骤 1: 设计核心数据模型 (高优先级)

**目标**: 在数据库中为已解析的数据设计好“家”。

**任务**:
1.  在 `src/models/` 目录下，创建新的 SQLAlchemy 模型文件，或在现有文件中追加。
2.  根据 PRD 和 XBRL 的通用结构，定义以下核心模型：
    *   **`FundReport` (基金报告主表)**: 存储报告的基本信息（如报告期、基金规模、净值等），并作为所有其他解析数据的外键关联中心。
    *   **`AssetAllocation` (资产配置表)**: 存储股票、债券、现金等大类资产的配置比例和金额。
    *   **`TopHolding` (前十大持仓表)**: 存储前十大重仓股或重仓债券的详细信息（名称、代码、市值、占净值比等）。
    *   **`IndustryAllocation` (行业配置表)**: 存储基金在不同行业的投资分布情况。
3.  确保模型之间的关联关系（`relationship`）被正确设置。

**验收标准**:
- [ ] 已创建上述 SQLAlchemy 模型，并通过 `alembic` 生成了新的数据库迁移脚本。
- [ ] 成功执行迁移，在数据库中创建了新的表结构。

### 步骤 2: 实现 XBRL 解析器 (高优先级)

**目标**: 构建一个能从 XBRL 文件中“读懂”财务数据的核心解析器。

**任务**:
1.  在 `src/parsers/` 目录下，创建 `xbrl_parser.py`。
2.  引入 `arelle` 或 `beautifulsoup4`/`lxml` 库（对于 XBRL 的 XML 结构，后两者可能更灵活）。
3.  创建一个 `XBRLParser` 类，其核心方法 `parse(file_path: str) -> ParsedData` 接收一个文件路径。
4.  在 `parse` 方法中，实现以下逻辑：
    *   加载并解析 XBRL/XML 文件。
    *   根据标准的 XBRL 标签或自定义的规则，提取出“资产负债表”、“利润表”、“投资组合”等关键部分。
    *   从这些部分中，定位并提取出资产配置、前十大持仓、行业分布等具体数据。
5.  `parse` 方法的返回值应该是一个结构化的数据对象（如 Pydantic 模型或字典），清晰地包含所有解析出的信息。

**验收标准**:
- [ ] `XBRLParser` 能够成功解析您在 `tests/test_downloads_real/` 目录下的一个真实 XBRL 文件。
- [ ] 解析器的 `parse` 方法能返回一个包含正确数据（例如，至少能提取出5个持仓股）的结构化对象。
- [ ] 为解析器的核心提取逻辑编写至少一个单元测试。

### 步骤 3: 创建数据持久化服务 (中优先级)

**目标**: 创建一个专门负责将解析数据写入数据库的服务。

**任务**:
1.  在 `src/services/` 目录下，创建 `data_persistence_service.py`。
2.  创建一个 `DataPersistenceService` 类，它依赖于数据库会话 (`db_session`)。
3.  实现核心方法 `save_parsed_data(report_info: dict, parsed_data: ParsedData)`。
4.  该方法将执行以下操作：
    *   根据 `report_info`（包含 `fund_code`, `report_year` 等）在 `FundReport` 表中创建或获取主记录。
    *   将 `parsed_data` 中的资产配置、持仓等信息，分别存入 `AssetAllocation`, `TopHolding` 等关联表中，并与 `FundReport` 主记录建立外键关系。
    *   整个保存过程应在一个数据库事务中完成，确保数据的一致性。

**验收标准**:
- [ ] `DataPersistenceService` 能够将一个模拟的 `ParsedData` 对象成功存入数据库的所有相关表中。

### 步骤 4: 集成解析与持久化流程 (高优先级)

**目标**: 将下载、解析、存储三个环节彻底打通，形成自动化数据处理流水线。

**任务**:
1.  修改 `src/api/routes/downloads.py` 中的后台任务函数 `execute_download_task`。
2.  在 `fund_service.batch_download` 成功下载完一个文件后，增加以下调用流程：
    ```python
    # ... file downloaded successfully to `file_path` ...

    # 1. 调用解析器
    xbrl_parser = XBRLParser()
    parsed_data = xbrl_parser.parse(file_path)

    # 2. 调用持久化服务
    persistence_service = DataPersistenceService(db_session=...)
    await persistence_service.save_parsed_data(
        report_info=report_details, # 包含基金代码、报告年份等
        parsed_data=parsed_data
    )

    # 3. 更新下载任务的子任务状态为“已解析”
    ... 
    ```
3.  完善错误处理：在解析或存储失败时，应能捕获异常，并将该文件的处理标记为“失败”，记录下错误信息。

**验收标准**:
- [ ] 触发一次完整的“搜索->下载->查询”流程后，能在数据库的 `asset_allocation` 或 `top_holding` 表中，查到由该流程自动解析并存入的真实数据。

## 🚀 Phase 4 预期成果

完成 Phase 4 后，我们的平台将实现质的飞跃：
- ✅ **自动化的数据流水线**: 从一个报告的 `upload_info_id` 开始，全自动地完成下载、解析和结构化入库。
- ✅ **核心价值数据**: 数据库中将积累起真正有价值、可供分析的结构化基金数据。
- ✅ **坚实的数据基础**: 为未来所有的数据分析、策略回测、前端可视化功能提供了坚实可靠的数据源。
